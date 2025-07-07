"""
Common utilities throughout the project.
"""

import os
import sys
import json
import logging
import pathlib
import tempfile
from enum import Enum
import textwrap
from zipfile import ZipFile

import shutil
from typing import Set, Dict, Optional, Tuple, List
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_RED, COLOR_CYAN, COLOR_YELLOW, COLOR_GRAY
from coguard_cli import api_connection
from coguard_cli.output_generators.output_generator_sarif import \
    translate_result_to_sarif
from coguard_cli.output_generators.output_generator_markdown import \
    translate_result_to_markdown
from coguard_cli.auth.token import Token
from coguard_cli.auth.enums import DealEnum
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CiCdProviderNames(Enum):
    """
    The enumeration capturing the different CI/CD Provider Names.
    """
    GITHUB = "github"

def create_service_identifier(prefix: str,
                              currently_used_service_names: Set[str],
                              service_instance: Optional[Dict]) -> Optional[str]:
    """
    This is a helper function to determine the service name as it appears in
    the manifest file. The algorithm works as follows.

    If the subPath fields of the config files in the manifest entry for each service
    have a common prefix, then this common prefix p is appended to the prefix parameter.
    If they do not have a common prefix, then the prefix parameter is used by itself.

    If the name chosen in this way appears inside the `currently_used_service_names`
    set, then a postfix in form of an increasing number is chosen.

    By the end, the contents of `currently_used_service_names` is being altered.
    """
    if not service_instance:
        sub_path_list = []
    else:
        sub_path_list = [entry["subPath"] for entry in service_instance["configFileList"]]
    common_prefix=os.path.commonpath(sub_path_list).strip("./").replace("/", "_") \
        if len(sub_path_list) >= 2 else ""
    if common_prefix:
        logging.debug("There was a common prefix: %s",
                      common_prefix)
        candidate = f"{prefix}_{common_prefix}"
    else:
        candidate = prefix
    if candidate not in currently_used_service_names:
        logging.debug("The candidate `%s` was not yet recorded. Adding as is.", candidate)
        currently_used_service_names.add(candidate)
        return candidate
    postfix = 0
    # We are putting a high cut-off index to ensure a non-infinite loop
    while postfix < 10**5:
        new_candidate = f"{candidate}_{postfix}"
        if new_candidate not in currently_used_service_names:
            currently_used_service_names.add(new_candidate)
            return new_candidate
        postfix += 1
    # This line should never be reached
    return None

def merge_coguard_infrastructure_description_folders(
        prefix: str,
        tuple_to_merge_into: Optional[Tuple[str, Dict]],
        tuple_to_merge_from: Optional[Tuple[str, Dict]]) -> None:
    """
    This function takes two tuples (folder, manifest) and
    merges them together into one. The first tuple is going to be
    altered for that purpose.
    """
    result_folder, result_manifest = tuple_to_merge_into
    to_merge_folder, to_merge_manifest = tuple_to_merge_from
    for machine in to_merge_manifest.get("machines", {}):
        result_machines = result_manifest.setdefault("machines", {})
        result_machine = result_machines.setdefault(machine, {})
        machine_dict = to_merge_manifest.get("machines", {}).get(machine, {})
        result_machine["id"] = machine_dict["id"]
        for service in machine_dict.get("services", {}):
            result_services = result_machine.setdefault("services", {})
            new_service_name = create_service_identifier(
                f"{prefix}_{service}",
                set(result_services.keys()),
                None
            )
            result_services[new_service_name] = to_merge_manifest.get(
                "machines", {}
            ).get(
                machine, {}
            ).get(
                "services",
                {}
            ).get(service)
            os.makedirs(os.path.join(
                result_folder,
                machine,
                new_service_name
            ), exist_ok=True)
            shutil.copytree(
                os.path.join(
                    to_merge_folder,
                    machine,
                    service
                ),
                os.path.join(
                    result_folder,
                    machine,
                    new_service_name
                ),
                dirs_exist_ok=True
            )
    for service in to_merge_manifest.get("clusterServices", {}):
        result_services = result_manifest.setdefault("clusterServices", {})
        new_service_name = create_service_identifier(
            f"{prefix}_{service}",
            set(result_services.keys()),
            None
        )
        result_services[new_service_name] = to_merge_manifest.get(
            "clusterServices", {}
        ).get(service)
        os.makedirs(os.path.join(
            "clusterServices",
            new_service_name
        ), exist_ok=True)
        shutil.copytree(
            os.path.join(
                to_merge_folder,
                "clusterServices",
                service
            ),
            os.path.join(
                result_folder,
                "clusterServices",
                new_service_name
            ),
            dirs_exist_ok=True
        )
    logging.debug("The new manifest looks like: %s", result_manifest)
    with open(os.path.join(result_folder, "manifest.json"), 'w', encoding='utf-8') as manifest_file:
        json.dump(result_manifest, manifest_file)

def convert_string_to_posix_path(input_str: str) -> str:
    """
    This function has the goal to ensure that any input path is converted to Linux style.
    This is important, since the manifest file for the CoGuard engine expects Posix-paths.
    """
    return "/".join(pathlib.Path(input_str).parts)

def convert_posix_path_to_os_path(input_str: str) -> str:
    """
    This function takes in a string in posix-path format and converts it into whatever the
    current path separator is.
    """
    return os.sep.join(pathlib.PurePosixPath(input_str).parts)

def retrieve_coguard_ignore_values(
        folder_name: str) -> List[str]:
    """
    Helper function to return the coguard_ignore_values
    """
    folder_name_path = pathlib.Path(folder_name)
    coguard_ignore_path = folder_name_path.joinpath(".coguardignore")
    if not coguard_ignore_path.exists():
        return []
    result = []
    with coguard_ignore_path.open(encoding='utf-8') as ignore_stream:
        result = ignore_stream.readlines()
    return [elem for elem in result if elem.strip() and not elem.startswith("#")]

def dry_run_outp(zip_candidate: Tuple[str, Dict]):
    """
    The function to output the location of the zip for the
    dry-run to the user.
    """
    if zip_candidate is None:
        print("No file generated")
        return
    zip_location, _ = zip_candidate
    print("Dry-run complete. You can find the upload-candidate "
          f"in the following location: {zip_location}")

def upload_and_evaluate_zip_candidate(
        zip_candidate: Optional[Tuple[str, Dict]],
        auth_config: Optional[CoGuardCliConfig],
        deal_type,
        token: Token,
        coguard_api_url: str,
        scan_identifier: str,
        output_format: str,
        fail_level: int,
        organization: Optional[str],
        ruleset: str):
    """
    The common function to upload a zip file, as generated by the
    helper functions, and evaluate the returned result.
    """
    if zip_candidate is None:
        print(
            f"{COLOR_YELLOW}Unable to identify any known configuration files.{COLOR_TERMINATION}"
        )
        return
    zip_file, _ = zip_candidate
    result = api_connection.send_zip_file_for_scanning(
        zip_file,
        auth_config.get_username(),
        token,
        coguard_api_url,
        scan_identifier,
        organization,
        ruleset
    )
    if result is None:
        print(
            f"{COLOR_RED} An error occurred while scanning. Please file a "
            f"bug report, and include the file located at {zip_file}, if possible. "
            f"{COLOR_TERMINATION}"
        )
        sys.exit(1)
    logging.debug("The result from the api is: %s",
                  str(result))
    print(f"{COLOR_CYAN}SCANNING OF{COLOR_TERMINATION} {scan_identifier}"
          f" {COLOR_CYAN}COMPLETED{COLOR_TERMINATION}")
    if 'formatted' in output_format:
        output_result_json_from_coguard(
            result or {},
            token,
            coguard_api_url,
            auth_config.get_username(),
            organization
        )
    if 'json' in output_format:
        with pathlib.Path("result.json").open('w', encoding='utf-8') as result_file:
            json.dump(result or {}, result_file, indent=2)
            print("JSON file written to `result.json`")
    if 'markdown' in output_format:
        translate_result_to_markdown(result, scan_identifier)
        print("Markdown file written to `result.md`")
    if 'sarif' in output_format:
        translate_result_to_sarif(
            result or {},
            pathlib.Path('result.sarif.json')
        )
        print("Sarif file written to `result.sarif.json`")
    if deal_type != DealEnum.ENTERPRISE:
        print("""
        🔧 Save time. Automatically find and fix vulnerabilities.
           Upgrade to auto-remediate issues.
        """)
    os.remove(zip_file)
    max_fail_severity = max(
        entry["rule"]["severity"] for entry in result.get("failed", [])
    ) if (result and result.get("failed", [])) else 0
    if max_fail_severity >= fail_level:
        sys.exit(1)

def output_result_json_from_coguard(
        result_json: Dict,
        token: Token,
        coguard_api_url: str,
        user_name: Optional[str],
        organization: Optional[str]):
    """
    The function which outputs the result json in a pretty format to the screen.

    :param result_json: The output from the API call to CoGuard.
    """
    high_checks = [entry for entry in result_json.get("failed", []) \
                   if entry["rule"]["severity"] > 3]
    high_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    medium_checks = [entry for entry in result_json.get("failed", []) \
                     if entry["rule"]["severity"] == 3]
    medium_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    low_checks = [entry for entry in result_json.get("failed", []) if entry["rule"]["severity"] < 3]
    low_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    fixable_check_list = api_connection.get_fixable_rule_list(
        token,
        coguard_api_url,
        user_name,
        organization
    )
    fixable_checks = [entry for entry in result_json.get("failed", []) \
                      if entry["rule"]["name"] in fixable_check_list]
    summary = (f'Scan result: {len(result_json.get("failed", []))} checks failed, '
               f"{COLOR_RED}{len(high_checks)} High{COLOR_TERMINATION}/"
               f"{COLOR_YELLOW}{len(medium_checks)} Medium{COLOR_TERMINATION}/"
               f"{COLOR_GRAY}{len(low_checks)} Low{COLOR_TERMINATION} "
               f"(🔧 {len(fixable_checks)} candidates for auto-remediation)")
    print(summary)
    for entry in high_checks:
        print_failed_check(COLOR_RED, entry, fixable_check_list)
    for entry in medium_checks:
        print_failed_check(COLOR_YELLOW, entry, fixable_check_list)
    for entry in low_checks:
        print_failed_check(COLOR_GRAY, entry, fixable_check_list)
    print(summary)

def print_failed_check(color: str,
                       entry: Dict,
                       fixable_checks: List[str]):
    """
    This is the function to print a failed check entry, given a color.

    :param color: The color to use. see e.g. :const:`COLOR_RED`
    :param entry: The entry as returned by the CoGuard API.
    """
    reference = extract_reference_string(entry)
    fix_icon = "🔧 " if entry["rule"]["name"] in fixable_checks else ""
    print(
        f'{fix_icon}{color} X Severity {entry["rule"]["severity"]}: '
        f'{entry["rule"]["name"]}{COLOR_TERMINATION}'
        f'{reference}'
    )
    prefix = "Documentation: "
    try:
        terminal_size = os.get_terminal_size().columns
    except OSError:
        terminal_size = 80
    wrapper = textwrap.TextWrapper(
        initial_indent=prefix,
        width=max(80, terminal_size//2),
        subsequent_indent=' '*len(prefix)
    )
    documentation_candidate = entry["rule"]["documentation"]
    logging.debug("The candidate for the documentation presentation is: %s",
                  documentation_candidate)
    if isinstance(documentation_candidate, str):
        print(wrapper.fill(entry["rule"]["documentation"]))
    else:
        description = documentation_candidate["documentation"]
        remediation = documentation_candidate["remediation"]
        sources = ",\n".join(documentation_candidate["sources"])
        if "scenarios" in documentation_candidate:
            scenario_string = "\nReferences for the specific ruleset: " + ",\n".join(
                documentation_candidate["scenarios"]
            )
        else:
            scenario_string = ''
        documentation_string = f"""
        {description}

        Remediation: {remediation}
        {scenario_string}

        Source:
        {sources}
        """.replace("        ", "")
        print(wrapper.fill(documentation_string))

def extract_reference_string(entry_dict: Dict):
    """
    This is a helper function to extract the respective file in the manifest
    corresponding to an entry in the failed rules.
    """
    config_file_in_entry = entry_dict.get("config_file", {})
    from_line = entry_dict.get("fromLine", None)
    to_line = entry_dict.get("toLine", None)
    if (from_line is not None and to_line is not None) and (from_line != 0 and to_line != 1):
        from_to_line = f", {from_line}-{to_line}"
    else:
        from_to_line = ""
    if not config_file_in_entry:
        return ""
    reference_path = pathlib.Path(
        config_file_in_entry.get("subPath", ".")
    ).joinpath(
        config_file_in_entry.get("fileName", ".")
    )
    return f" (affected files: {reference_path}{from_to_line})"

def upload_and_fix_zip_candidate(
        zip_candidate: Optional[Tuple[str, Dict]],
        folder_path: str,
        token: Token,
        coguard_api_url: str,
        organization: Optional[str]) -> None:
    """
    The common function to upload and a zip file, as generated by the
    helper functions.
    """
    if zip_candidate is None:
        print(
            f"{COLOR_YELLOW}Unable to identify any known configuration files.{COLOR_TERMINATION}"
        )
        return
    zip_file, zip_manifest = zip_candidate
    api_result = api_connection.send_zip_file_for_fixing(
        zip_file,
        token,
        coguard_api_url,
        organization
    )
    os.remove(zip_file)
    if api_result is None:
        print(f"{COLOR_RED} There was an error uploading the zip candidate.{COLOR_TERMINATION}")
        return
    print(f'{COLOR_CYAN} Applying the changes.{COLOR_TERMINATION}')
    temp_folder = tempfile.mkdtemp(prefix="coguard_cli_fix_extract")
    with ZipFile(api_result, 'r') as zip_stream:
        zip_stream.extractall(temp_folder)
    os.remove(api_result)
    apply_fixes_to_folder(temp_folder, folder_path, zip_manifest)
    print(f'{COLOR_CYAN} Done applying the changes. {COLOR_TERMINATION}')

def apply_fixes_to_folder(fix_folder: str, target_folder: str, zip_manifest: Dict):
    """
    The helper function to apply the fixes found in fix_folder to the target folder.

    It identifies all configuration files, tries to map them in the target folder
    using the manifest information, and then performs the move.

    If everything weng according to plan, the fix_folder will be deleted. Otherwise,
    it will be left for the purpose of review.
    """
    files_to_move = []
    different_services_objects = []
    for service_name, service in zip_manifest.get('clusterServices', {}).items():
        different_services_objects.append((os.path.join('clusterServices', service_name), service))
    for machine_name, machine in zip_manifest.get('machines', {}).items():
        for service_name, service in machine.get('services', {}).items():
            different_services_objects.append(
                (os.path.join(machine_name, service_name), service)
            )
    for pth, service in different_services_objects:
        for config_file in service.get("configFileList", []):
            files_to_move.append(
                (
                    os.path.join(
                        pth,
                        convert_posix_path_to_os_path(config_file.get("subPath")),
                        config_file.get("fileName")
                    ),
                    os.path.join(
                        convert_posix_path_to_os_path(config_file.get("subPath")),
                        config_file.get("fileName")
                    )
                )
            )
        for config_file in service.get("complimentaryFileList", []):
            files_to_move.append(
                (
                    os.path.join(
                        pth,
                        convert_posix_path_to_os_path(config_file.get("subPath")),
                        config_file.get("fileName")
                    ),
                    os.path.join(
                        convert_posix_path_to_os_path(config_file.get("subPath")),
                        config_file.get("fileName")
                    )
                )
            )
    all_files_found = True
    for file_pth_fix, file_pth_folder in files_to_move:
        if not os.path.exists(os.path.join(target_folder, file_pth_folder)):
            logging.error("File %s did not exist in %s", file_pth_folder, target_folder)
            all_files_found = False
            continue
        try:
            shutil.copyfile(
                os.path.join(fix_folder, file_pth_fix),
                os.path.join(target_folder, file_pth_folder)
            )
        except OSError as err:
            all_files_found = False
            logging.error("Could not copy %s to %s: %s",
                          file_pth_fix,
                          file_pth_folder,
                          err)
    if not all_files_found:
        print(f"{COLOR_RED} Not all files were possible to be fixed.")
        print(f"You can review the extracted and fixed files at {fix_folder}.{COLOR_TERMINATION}")
    else:
        shutil.rmtree(fix_folder)

def merge_external_scan_results_with_final_folder(
        collected_config_file_tuple: Tuple[str, Dict],
        external_results_to_send: Optional[Dict]) -> None:
    """
    Helper function to merge a tuple of a file-path and a manifest
    dictionary with the external scan results.
    """
    if not external_results_to_send:
        return
    coguard_folder_path, manifest_dict = collected_config_file_tuple
    manifest_dict["externalResults"] = []
    external_results_list = manifest_dict["externalResults"]
    for ext_name, ext_path in external_results_to_send.items():
        external_results_list.append(ext_name)
        for subfolder in pathlib.Path(ext_path).iterdir():
            dest=pathlib.Path(coguard_folder_path).joinpath("externalResults").joinpath(ext_name)
            dest.mkdir(parents=True, exist_ok=True)
            if subfolder.is_dir():
                shutil.copytree(subfolder, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(subfolder, dest)
    # Update the manifest file
    with open(
            os.path.join(coguard_folder_path,
                         "manifest.json"),
            "w",
            encoding='utf-8') \
         as manifest_file:
        json.dump(manifest_dict, manifest_file)
