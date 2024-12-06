"""
This module provides functionality to translate a CoGuard result into SARIF format.
"""

from typing import Dict
import pathlib
import json
import logging
from importlib.metadata import version, PackageNotFoundError

def translate_result_to_sarif(
        coguard_result: Dict[str, str],
        to_safe_path = pathlib.Path("result.sarif.json")) -> None:
    """
    This function takes a result JSON as produced by CoGuard, and stores the sarif version
    in a path as specified by `to_safe_path`.
    """
    if to_safe_path is None or not str(to_safe_path):
        raise ValueError("The path to save the file has been empty")
    if coguard_result is None:
        raise ValueError("The path to save the file has been empty")
    try:
        coguard_version = version("coguard-cli")
    except PackageNotFoundError:
        logging.error("CoGuard not locally installed")
        coguard_version = "0.0.0"
    result_blueprint = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CoGuard",
                        "version": f'{coguard_version}',
                        "informationUri": "https://www.coguard.io",
                        "rules": []
                    }
                },
                "results": []
            }
        ]
    }
    for failed_rule in coguard_result.get("failed", []):
        rule_id = failed_rule.get("rule", {}).get("name")
        description = failed_rule.get("rule", {}).get("documentation").get("documentation")
        remediation = failed_rule.get("rule", {}).get("documentation").get("remediation")
        sources = "\n - ".join(
            failed_rule.get("rule", {}).get("documentation").get("sources", [])
        )
        if sources:
            sources = "\n - " + sources
        message = f"""
        Description: {description}
        Remediation: {remediation}
        Sources: {sources}
        """.strip()
        file_uri = pathlib.Path(failed_rule.get("config_file", {}).get("subPath", ".")).joinpath(
            failed_rule.get("config_file", {}).get("fileName", "")
        )
        location = {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": str(file_uri)
                },
                "region": {
                    "startLine": failed_rule.get("fromLine", 0) + 1,
                    "endLine": failed_rule.get("toLine", 1) + 1
                }
            }
        }
        result_blueprint.get(
            "runs"
        )[0].get("results").append(
            {
                "ruleId": rule_id,
                "message": {
                    "text": message
                },
                "locations": [
                    location
                ]
            }
        )
    with to_safe_path.open('w', encoding='utf-8') as sarif_result_file:
        json.dump(result_blueprint, sarif_result_file, indent=2)
