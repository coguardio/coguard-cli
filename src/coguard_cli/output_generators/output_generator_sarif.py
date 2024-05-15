"""
This module provides functionality to translate a CoGuard result into SARIF format.
"""

from typing import Dict
import pathlib
import json

def translate_result_to_sarif(
        coguard_result: Dict[str, str],
        to_safe_path = pathlib.Path("result_sarif.json")) -> None:
    """
    This function takes a result JSON as produced by CoGuard, and stores the sarif version
    in a path as specified by `to_safe_path`.
    """
    if not to_safe_path:
        raise ValueError("The path to save the file has been empty")
    result_blueprint = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CoGuard",
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
        """
        file_uri = pathlib.Path(failed_rule.get("config_file", {}).get("subPath")).joinpath(
            failed_rule.get("config_file", {}).get("fileName")
        )
        service_name = failed_rule.get("service")
        if "machine" in failed_rule:
            file_uri = pathlib.Path(
                failed_rule.get("machine")
            ).joinpath(
                service_name
            ).joinpath(
                file_uri
            )
        else:
            file_uri = pathlib.Path(
                failed_rule.get("clusterServices")
            ).joinpath(
                service_name
            ).joinpath(
                file_uri
            )
        location = {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": str(file_uri)
                },
                "region": {
                    "startLine": failed_rule.get("fromLine", 0),
                    "endline": failed_rule.get("toLine", 1)
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
                ],
                "partialFingerprints": {
                "primaryLocationLineHash": "39fa2ee980eb94b0:1"
                }
            }
        )
    with to_safe_path.open('w', encoding='utf-8') as serif_result_file:
        json.dump(result_blueprint, serif_result_file)
