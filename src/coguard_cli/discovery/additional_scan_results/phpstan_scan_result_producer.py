"""
This is the module to get the results for code scanning issues using PHPStan.
"""

import os
import pathlib
import json
from typing import Dict, Optional
import shutil
import tempfile
import coguard_cli.docker_dao
from coguard_cli.discovery.additional_scan_results.additional_scan_result_producer_abc \
    import AdditionalScanResult

class PhpStanSastProducer(AdditionalScanResult):
    """
    This is the class adding scan results of Phpstan to the results.
    This enriches the CoGuard reports with additional functionalities.
    """

    def perform_external_scan(
            self,
            path_to_file_system: str,
            additional_parameters: Optional[Dict]=None) -> Optional[str]:
        """
        Overwriting the function given in the abstract base class.
        """
        tempdir_path = tempfile.mkdtemp(prefix="coguard-cli-external-phpstan-")
        external_scan_run = coguard_cli.docker_dao.run_external_scanner_container(
            "ghcr.io/phpstan/phpstan",
            "2.1.17",
            ("analyze --no-progress --error-format=prettyJson --level "
             f"max /app > {tempdir_path}{os.path.sep}result.json || true"),
            {},
            [
                (path_to_file_system, "/app")
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
        tempdir_path = tempfile.mkdtemp(prefix="coguard-cli-external-phpstan-")
        with open(
                f"{path_to_scan_result}{os.path.sep}result.json",
                'r',
                encoding='utf-8') as sast_json_stream:
            try:
                phpstan_results = json.load(sast_json_stream)
            except json.decoder.JSONDecodeError:
                phpstan_results = {}

        result = {"failed": []}
        res_failed = result["failed"]
        for file_name, finding in phpstan_results.get("files", {}).items():
            file_name_without_app = file_name.replace("/app/", "")
            for message in finding.get("messages", []):
                cog_res = {
                    "rule": {},
                    "config_file": {
                        "fileName": str(pathlib.Path(file_name_without_app).name),
                        "subpath": str(pathlib.Path(file_name_without_app).parent),
                        "configFileType": "custom"
                    },
                    "fromLine": int(message.get("line", 0)),
                    "toLine": int(message.get("line", 0)) + 1,
                }
                cog_res_rule = cog_res["rule"]
                cog_res_rule["name"] = "php_sast_scan_flag"
                cog_res_rule["severity"] = 3
                cog_res_rule["documentation"] = {
                    "documentation": ("The given file contained a SAST scanning error:  "
                                      f"{message['message']}"),
                    "remediation": "Change the code in the given file to address this finding.",
                    "sources": [
                        "https://cwe.mitre.org/data/index.html"
                    ]
                }
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
        return "phpstan_sast_scan"
