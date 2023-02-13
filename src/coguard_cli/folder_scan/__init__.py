"""
This is the area where common functionality for scanning folders is collected.
"""

import json
import os
import tempfile
import shutil
import zipfile
from typing import Optional, Tuple, Dict

import coguard_cli.discovery.config_file_finder_factory as factory
from coguard_cli.util import replace_special_chars_with_underscore, \
    create_service_identifier

# pylint: disable=too-many-locals
def find_configuration_files_and_collect(
        folder_path: str,
        customer_id: str,
        manifest_name: Optional[str] = None
) -> Optional[Tuple[str, Dict]]:
    """
    This function consumes a file_system store location,
    and extracts services and files from that, and stores it at a common location
    with a manifest file as acceptable by CoGuard. If nothing was possible to be
    extracted, None is returned.
    """
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
    manifest_blueprint = {
        "name": replace_special_chars_with_underscore(
            os.path.basename(
                os.path.dirname(
                    folder_path + os.sep
                )
            )
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
    for (_, tuple_list) in collected_service_results_dicts.values():
        for (_, directory_to_delete) in tuple_list:
            shutil.rmtree(directory_to_delete, ignore_errors=True)
    return (final_location, manifest_blueprint)

def create_zip_to_upload_from_file_system(
        folder_path: str,
        customer_id: str,
        cluster_name: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
    """
    This function creates a zip file from a given image name which is
    ready to be uploaded to the CoGuard back-end. If something goes wrong,
    the output will be None; otherwise, it will be the path to the zip file.

    Keep in mind that whoever is calling this function is in charge of deleting
    the zip file afterwards.
    """
    if folder_path is None:
        return None
    collected_location_manifest_tuple = find_configuration_files_and_collect(
        folder_path,
        customer_id,
        cluster_name
    )
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
    #cleanup
    shutil.rmtree(collected_location, ignore_errors=True)
    return (temp_zip, manifest_dict)
