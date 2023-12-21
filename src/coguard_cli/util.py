"""
Common utilities throughout the project.
"""

import os
import json
import logging
import re
import pathlib
from enum import Enum

import shutil
from typing import Set, Dict, Optional, Tuple

class CiCdProviderNames(Enum):
    """
    The enumeration capturing the different CI/CD Provider Names.
    """
    GITHUB = "github"

def replace_special_chars_with_underscore(string: str, keep_spaces=False) -> str:
    """
    Helper function remove any special character with underscore.
    """
    return re.sub(
        "_+",
        "_",
        re.sub(
            "[^a-zA-Z1-9- ]" if keep_spaces else "[^a-zA-Z1-9]",
            "_",
            string
        )
    ).strip("_ ")

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
