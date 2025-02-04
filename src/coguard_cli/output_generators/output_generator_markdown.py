"""
This module provides functionality to translate a CoGuard result into Markdown format.
"""

from typing import Dict
import pathlib
import os
import logging
import importlib.metadata

def create_unique_result_list(
        failed_rules):
    """
    A helper function to have only unique results presented in a Markdown.
    """
    result = {}
    for failed_rule in failed_rules:
        rule_name = failed_rule.get('rule', {}).get('name', '')
        if rule_name not in result:
            result[rule_name] = failed_rule
    return list(result.values())

def extract_affected_files_by_severity(coguard_result: Dict[str, str]) -> Dict[str, Dict]:
    """
    Helper function to group affected files by rule-identifier.
    """
    affected_files_by_severity = {}
    failed_rules = coguard_result.get("failed", [])
    for rule in failed_rules:
        rule_name = rule.get('rule', {}).get("name", '')
        new_config_file_entry = rule.get("config_file", {})
        if new_config_file_entry:
            new_config_file_name = new_config_file_entry.get('fileName', '')
            new_config_file_subpath = new_config_file_entry.get('subPath', '')
            new_config_file_as_string = f"{new_config_file_subpath}{os.sep}{new_config_file_name}"
            if rule_name not in affected_files_by_severity:
                affected_files_by_severity[rule_name] = [new_config_file_as_string]
            else:
                affected_files_by_severity[rule_name].append(new_config_file_as_string)
    return affected_files_by_severity

def translate_result_to_markdown(
        coguard_result: Dict[str, str],
        scan_identifier: str = "",
        to_safe_path = pathlib.Path("result.md")) -> None:
    """
    This function takes a result JSON as produced by CoGuard, and stores the sarif version
    in a path as specified by `to_safe_path`.
    """
    if to_safe_path is None or not str(to_safe_path):
        raise ValueError("The path to save the file has been empty")
    if coguard_result is None:
        raise ValueError("The path to save the file has been empty")
    try:
        coguard_version =  importlib.metadata.version("coguard-cli")
    except importlib.metadata.PackageNotFoundError:
        logging.error("CoGuard not locally installed")
        coguard_version = "0.0.0"
    markdown_blueprint = f"""
# CoGuard evaluation of `{scan_identifier}`
CoGuard CLI version: {coguard_version}
# Findings
"""
    affected_files_by_severity = extract_affected_files_by_severity(coguard_result)
    failed_rules = coguard_result.get("failed", [])
    failed_rules.sort(key=lambda itm: itm.get("rule", {}).get("severity"), reverse=True)
    failed_rules=create_unique_result_list(failed_rules)
    findings_list = []
    for rule in failed_rules:
        documentation = rule.get('rule', {}).get('documentation', {}).get('documentation', '')
        remediation = rule.get('rule', {}).get('documentation', {}).get('remediation', '')
        severity = rule.get('rule', {}).get('severity')
        source = "\n - ".join(rule.get('rule', {}).get('documentation', {}).get('sources', []))
        if source:
            source = f"\n - {source}"
        affected_files = ""
        rule_name = rule.get('rule', {}).get('name', '')
        if rule_name in affected_files_by_severity:
            unique_affected_files = list(set(affected_files_by_severity.get(rule_name)))
            affected_files = "\n - ".join(unique_affected_files)
            if affected_files:
                affected_files = f"\n - {affected_files}"
        compliance_needs = "\n - ".join(rule.get(
            'rule', {}
        ).get(
            'documentation', {}
        ).get(
            'scenarios', []
        ))
        if compliance_needs:
            compliance_needs = \
                f"\n**References for your specific requirements:**\n\n - {compliance_needs}"
        findings_list.append(
            f"""
## {rule_name}
**Severity:** {severity}

{documentation}

**Remediation:**

{remediation}
{compliance_needs}

**Sources:**
{source}

**Affected files:**
{affected_files}
""")
    with to_safe_path.open('w', encoding='utf-8') as markdown_result_file:
        markdown_result_file.write(markdown_blueprint + "\n".join(findings_list))
