"""
This module provides functionality to translate a CoGuard result into SARIF format.
"""

from typing import Dict, Tuple
import pathlib
import json
import logging
from importlib.metadata import version, PackageNotFoundError

# The three bands CoGuard reports findings in, as the level SARIF calls them and
# the number GitHub code scanning ranks them by. The bands are the same ones the
# formatted output uses, so that a finding does not change its severity by being
# looked at in a different place.
SARIF_LEVELS = {
    "high": ("error", "8.0"),
    "medium": ("warning", "5.0"),
    "low": ("note", "2.0")
}

def severity_band(severity) -> Tuple[str, str]:
    """
    The SARIF level and the code scanning severity of a CoGuard severity.
    """
    try:
        numeric = int(severity)
    except (TypeError, ValueError):
        numeric = 3
    if numeric > 3:
        return SARIF_LEVELS["high"]
    if numeric == 3:
        return SARIF_LEVELS["medium"]
    return SARIF_LEVELS["low"]

def describe_rule(failed_rule: Dict, description: str) -> Dict:
    """
    The description of a violated rule for the driver of the report, so that
    whoever reads it sees the name and the severity of a finding and not only its
    location.
    """
    rule = failed_rule.get("rule", {})
    rule_id = rule.get("name")
    severity = rule.get("severity")
    level, security_severity = severity_band(severity)
    return {
        "id": rule_id,
        "name": rule_id,
        "shortDescription": {
            "text": rule.get("humanReadableName") or rule_id
        },
        "fullDescription": {
            "text": description or ""
        },
        "defaultConfiguration": {
            "level": level
        },
        "properties": {
            "severity": severity,
            "security-severity": security_severity
        }
    }

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
    rules = result_blueprint.get("runs")[0].get("tool").get("driver").get("rules")
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
        level, _ = severity_band(failed_rule.get("rule", {}).get("severity"))
        # A rule commonly fails for more than one file, and is described once.
        if not any(rule.get("id") == rule_id for rule in rules):
            rules.append(describe_rule(failed_rule, description))
        result_blueprint.get(
            "runs"
        )[0].get("results").append(
            {
                "ruleId": rule_id,
                "level": level,
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
