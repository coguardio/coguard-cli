"""
This is the module to get the results for CVEs through Trivy and translate them into
the common format for further processing.
"""

import os
import json
from typing import Dict, Optional
import shutil
import tempfile
import coguard_cli.docker_dao
from coguard_cli.discovery.additional_scan_results.additional_scan_result_producer_abc \
    import AdditionalScanResult

class TrivyCveProducer(AdditionalScanResult):
    """
    This is the class adding scan results of Trivy with respect to CVEs to the results.
    This enriches the CoGuard reports with additional functionalities.
    """

    def perform_external_scan(
            self,
            path_to_file_system: str,
            additional_parameters: Optional[Dict]=None) -> Optional[str]:
        """
        Overwriting the function given in the abstract base class.
        """
        tempdir_path = tempfile.mkdtemp(prefix="coguard-cli-external-trivy-")
        external_scan_run = coguard_cli.docker_dao.run_external_scanner_container(
            "aquasec/trivy",
            "0.63.0",
            "filesystem --format cyclonedx --scanners=vuln --output /outp/sbom.json /app",
            {},
            [
                (path_to_file_system, "/app"),
                (tempdir_path, "/outp")
            ]
        )
        if not external_scan_run:
            shutil.rmtree(tempdir_path)
            return None
        return tempdir_path

    def translate_external_scan_result(
            self,
            path_to_scan_result: str) -> Optional[str]:
        """
        Overwriting the function given in the abstract base class.
        """
        tempdir_path = tempfile.mkdtemp(prefix="coguard-cli-external-trivy-")
        with open(
                f"{path_to_scan_result}{os.path.sep}sbom.json",
                'r',
                encoding='utf-8') as sbom_json_stream:
            try:
                trivy_results = json.load(sbom_json_stream)
            except json.decoder.JSONDecodeError:
                trivy_results = {}

        result = {"failed": []}
        res_failed = result["failed"]
        for vuln in trivy_results.get("vulnerabilities", []):
            if not any(rating["severity"] == "high" or rating["severity"] == "critical"
                       for rating in vuln.get("ratings", [])):
                continue
            cog_res = {"rule": {}}
            cog_res_rule = cog_res["rule"]
            cog_res_rule["name"] = "cve_vuln_present"
            cog_res_rule["severity"] = 5
            cog_res_rule["documentation"] = {
                "documentation": ("The present project contained a HIGH or CRITICAL CVE, namely "
                                  f"{vuln['id']}. This affects the packages "
                                  f"{', '.join(pkg['ref'] for pkg in vuln['affects'])}."),
                "remediation": ("Ensure that all of the project's supply chain dependencies "
                                "are kept up to date with the latest version."),
                "sources": [
                    vuln.get("source", {}).get("url", "")
                ]
            }
            if "cwes" in vuln:
                cog_res_rule["documentation"]["documentation"] += (
                     " Directly linked CWEs: "
                     f"{', '.join(str(cwe) for cwe in vuln.get('cwes', []))}."
                )
            res_failed.append(cog_res)
        with open(f"{tempdir_path}{os.path.sep}result.json",
                  'w',
                  encoding='utf-8') as result_json_stream:
            json.dump(result, result_json_stream)
        return tempdir_path

    def get_external_scan_identifier(self) -> str:
        """
        Overwriting the function given in the abstract base class.
        """
        return "trivy_cve_scan"
