"""
This is the area where common functionality for scanning folders is collected.
"""

import json
import logging
import os
import tempfile
import shutil
import zipfile
import fnmatch
from typing import Optional, Tuple, Dict, List, Union
import yaml
from flatten_dict import unflatten

import coguard_cli.discovery.config_file_finder_factory as factory
from coguard_cli.util import replace_special_chars_with_underscore, \
    create_service_identifier, \
    convert_posix_path_to_os_path

def filter_config_file_list(
        config_file_list: List[Tuple[Dict, str]],
        ignore_list: List[str]) -> List[Tuple[Dict, str]]:
    """
    Helper function for `filter_collected_service_results`, which filters the list out that contains
    items in the ignore list.
    """
    result = []
    for service_dict, tmp_path in config_file_list:
        new_internal_config_file_list = []
        for config_file_dict in service_dict.get("configFileList", []):
            config_file_path = os.path.join(
                config_file_dict.get("subPath"),
                config_file_dict.get("fileName")
            )
            ignore = False
            for ignore_pattern in ignore_list:
                path_with_dot = config_file_path
                path_without_dot = config_file_path[2:] if config_file_path.startswith("./") \
                    else config_file_path
                if fnmatch.fnmatch(path_with_dot, ignore_pattern) or \
                   fnmatch.fnmatch(path_without_dot, ignore_pattern):
                    ignore = True
                    print(
                        f"Found instruction to ignore {config_file_path} through {ignore_pattern}."
                    )
                    break
            if not ignore:
                new_internal_config_file_list.append(config_file_dict)
            else:
                os.remove(os.path.join(tmp_path, config_file_path))
        if new_internal_config_file_list:
            service_dict["configFileList"] = new_internal_config_file_list
            result.append((service_dict, tmp_path))
        else:
            shutil.rmtree(tmp_path, ignore_errors=True)
    return result


def filter_collected_service_results(
        collected_service_results_dicts: Dict[str, Tuple[bool, List[Tuple[Dict, str]]]],
        ignore_list: List[str]
) -> None:
    """
    The function to filter files found by the config_file_finder.find_configuration-files
    function with respect to the patterns as found in the `ignore_list`.
    """
    if not ignore_list:
        # Nothing to filter
        return
    del_keys = []
    for service_name, (cluster_service_val, config_file_list) in \
            collected_service_results_dicts.items():
        new_filter_config_file_list = filter_config_file_list(config_file_list, ignore_list)
        if new_filter_config_file_list:
            collected_service_results_dicts[service_name] = (
                cluster_service_val,
                new_filter_config_file_list
            )
        else:
            del_keys.append(service_name)
    for service_name in del_keys:
        del collected_service_results_dicts[service_name]


# pylint: disable=too-many-locals
def find_configuration_files_and_collect(
        folder_path: str,
        customer_id: str,
        manifest_name: Optional[str] = None,
        ignore_list: Optional[List[str]] = None
) -> Optional[Tuple[str, Dict]]:
    """
    This function consumes a file_system store location,
    and extracts services and files from that, and stores it at a common location
    with a manifest file as acceptable by CoGuard. If nothing was possible to be
    extracted, None is returned.

    An ignore_list can also be provided, matching the fnmatch function input there
    and telling the parser to ignore certain files.

    Keep in mind that whoever is calling this function is in charge of deleting
    the generated folder afterwards.
    """
    if folder_path is None:
        return None
    collected_service_results_dicts = {}
    for finder_instance in factory.config_file_finder_factory():
        discovered_config_files = finder_instance.find_configuration_files(
            folder_path,
            {}
        )
        if len(discovered_config_files) > 0:
            collected_service_results_dicts[finder_instance.get_service_name()] = \
                (finder_instance.is_cluster_service(), discovered_config_files)
    if not collected_service_results_dicts:
        return None
    filter_collected_service_results(collected_service_results_dicts, ignore_list)
    manifest_blueprint = {
        "name": replace_special_chars_with_underscore(
            os.path.basename(
                os.path.dirname(
                    folder_path + os.sep
                )
            ),
            True
        ) if manifest_name is None else manifest_name,
        "customerId": customer_id,
        "machines": {
            "folder": {
                "id": "folder"
            }
        },
        "clusterServices": {
        }
    }
    final_location = tempfile.mkdtemp(prefix="coguard-cli-folder")
    machine_location = os.path.join(final_location, "folder")
    os.mkdir(machine_location)
    already_used_identifiers = set()
    for (service_id, (is_cluster_service, tuple_list)) in collected_service_results_dicts.items():
        for (tuple_instance, tuple_dir) in tuple_list:
            new_service_custom_identifier = create_service_identifier(
                service_id,
                already_used_identifiers,
                tuple_instance
            )
            if is_cluster_service:
                manifest_blueprint["clusterServices"]\
                    [new_service_custom_identifier] = tuple_instance
                service_folder = os.path.join(
                    final_location,
                    "clusterServices",
                    new_service_custom_identifier)
                os.makedirs(service_folder, exist_ok=True)
                shutil.copytree(tuple_dir, service_folder, dirs_exist_ok=True)
            else:
                if "services" not in manifest_blueprint["machines"]["folder"]:
                    manifest_blueprint["machines"]["folder"]["services"] = {}
                manifest_blueprint["machines"]\
                    ["folder"]\
                    ["services"]\
                    [new_service_custom_identifier] = tuple_instance
                service_folder = os.path.join(machine_location, new_service_custom_identifier)
                os.mkdir(service_folder)
                shutil.copytree(tuple_dir, service_folder, dirs_exist_ok=True)
    if not manifest_blueprint["clusterServices"]:
        # Just to match the existing blueprint
        del manifest_blueprint["clusterServices"]
    if "services" not in manifest_blueprint["machines"]["folder"]:
        del manifest_blueprint["machines"]
    with open(os.path.join(final_location, "manifest.json"), "w", encoding='utf-8') \
         as manifest_file:
        json.dump(manifest_blueprint, manifest_file)
    # cleanup
    directories_to_delete = [
        directory_to_delete
        for (_, tuple_list) in collected_service_results_dicts.values()
        for (_, directory_to_delete) in tuple_list
    ]
    for directory_to_delete in directories_to_delete:
        shutil.rmtree(directory_to_delete, ignore_errors=True)
    return (final_location, manifest_blueprint)

def create_zip_to_upload_from_file_system(
        collected_location_manifest_tuple: Optional[Tuple[str, Dict]],
        additional_failed_rules: List[str] = None) -> Optional[Tuple[str, Dict]]:
    """
    This function creates a zip file from the tuple provided as input, which
    comes from the `find_configuration_files_and_collect` function.

    Keep in mind that whoever is calling this function is in charge of deleting
    the zip file afterwards.
    """
    if collected_location_manifest_tuple is None:
        return None
    collected_location, manifest_dict = collected_location_manifest_tuple
    (file_handle, temp_zip) = tempfile.mkstemp(prefix="coguard_cli_zip_to_upload", suffix=".zip")
    os.close(file_handle)
    with zipfile.ZipFile(temp_zip, "w") as upload_zip:
        for (dir_path, _, file_names) in os.walk(collected_location):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                upload_zip.write(file_path, arcname=file_path[len(collected_location):])
        if additional_failed_rules:
            upload_zip.writestr("failed_rules.json", json.dumps(additional_failed_rules))
    return (temp_zip, manifest_dict)

def _find_images_recursively(
        config: Union[Dict, List]) -> List[str]:
    """
    Helper function for `_find_and_extract_docker_images_from_config_files`.
    It takes in a config object, tries to find keys referencing "image" and returns
    the results as a list.
    """
    result = []
    if isinstance(config, dict):
        if "image" in config and isinstance(config["image"], str):
            result.append(config["image"])
        for sub_vals in config.values():
            result.extend(_find_images_recursively(sub_vals))
    elif isinstance(config, List):
        for sub_vals in config:
            result.extend(_find_images_recursively(sub_vals))
    return result

def _find_and_extract_docker_images_from_config_files(
        config_file_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Helper function to `extract_included_docker_images`. This one consumes a list
    of files which may have docker image references inside, and extractes these names.
    """
    result = []
    for path_to_file_system, file_path in config_file_list:
        try:
            with open(os.path.join(path_to_file_system, file_path),
                      'r',
                      encoding='utf-8') as file_stream:
                config_res = yaml.safe_load_all(file_stream)
                logging.debug("Loaded %s", config_res)
                config = [] if config_res is None else [
                    unflatten(config_part, splitter='dot') for config_part in config_res
                ]
                logging.debug("The unflattened config is %s", config)
            result.extend([(image, file_path) for image in _find_images_recursively(config)])
        #pylint: disable=broad-exception-caught
        except Exception as err:
            logging.debug(
                "Failed to load %s: %s",
                os.path.join(path_to_file_system, file_path),
                err
            )
    return result

def extract_included_docker_images(
        collected_location_manifest_tuple: Optional[Tuple[str, Dict]]) -> List[str]:
    """
    This function takes in a tuple as produced by `find_configuration_files_and_collect`,
    and searches for docker images included in different Kubernetes or docker-compose files.
    The image names and source file names are returned as list of tuples.
    """
    if not collected_location_manifest_tuple:
        return []
    collected_location, collected_manifest = collected_location_manifest_tuple
    extracted_relevant_machine_config_files = [
        (os.path.join(
            collected_location,
            machine_name,
            service_name),
         os.path.join(
            convert_posix_path_to_os_path(config_file["subPath"]),
            config_file["fileName"]
         )) for machine_name, machine_dict in collected_manifest.get("machines", {}).items()
        for service_name, service_dict in machine_dict.get("services", {}).items()
        for config_file in service_dict.get("configFileList", [])
        if service_dict.get("serviceName", "") in ["kubernetes", "docker_compose"]
    ]
    extracted_relevant_cluster_service_config_files = [
        (os.path.join(
            collected_location,
            "clusterServices",
            service_name
        ),
         os.path.join(
            convert_posix_path_to_os_path(config_file["subPath"]),
            config_file["fileName"]
         ))
        for service_name, service_dict in collected_manifest.get("clusterServices", {}).items()
        for config_file in service_dict.get("configFileList", [])
        if service_dict.get("serviceName", "") in ["kubernetes", "docker_compose"]
    ]
    return _find_and_extract_docker_images_from_config_files(
        extracted_relevant_machine_config_files + extracted_relevant_cluster_service_config_files
    )
