"""
Some of the main functionality gluing all the pieces in this
repo will get here.
"""

import json
import os
import shutil
import stat
import logging
import tempfile
from typing import Optional, Dict, Tuple
import zipfile
from coguard_cli.util import replace_special_chars_with_underscore, \
    create_service_identifier
from coguard_cli.auth.util import DealEnum
from coguard_cli import docker_dao
import coguard_cli.discovery.config_file_finder_factory as factory
from coguard_cli.print_colors import COLOR_RED, COLOR_TERMINATION

def extract_docker_file_and_store(image_name: str) -> Optional[Tuple[Dict, str]]:
    """
    Very similar output as the config file finder factory items. The idea
    is that we will store the Dockerfile on the file-system and scan it as
    well.
    """
    docker_file = docker_dao.extract_docker_file(image_name)
    if docker_file is None:
        return None
    manifest_entry = {
        "version": "1.0",
        "serviceName": "dockerfile",
        "configFileList": [
            {
                "fileName": "Dockerfile",
                "defaultFileName": "Dockerfile",
                "subPath": ".",
                "configFileType": "dockerfile"
            }
        ],
        "complimentaryFileList": []
    }
    temp_location = tempfile.mkdtemp(prefix="coguard-cli-dockerfile")
    with open(os.path.join(temp_location, "Dockerfile"), 'w', encoding='utf-8') as dockerfp:
        dockerfp.write(docker_file)
    return (
        manifest_entry,
        temp_location
    )

# pylint: disable=too-many-locals
def find_configuration_files_and_collect(
        image_name: str,
        customer_id: str,
        file_system_store_location: str,
        docker_config: Dict) -> Optional[Tuple[str, Dict]]:
    """
    This function consumes a file_system store location and the docker_config,
    and extracts services and files from that, and stores it at a common location
    with a manifest file as acceptable by CoGuard. If nothing was possible to be
    extracted, None is returned.
    """
    collected_service_results_dicts = {}
    for finder_instance in factory.config_file_finder_factory():
        discovered_config_files = finder_instance.find_configuration_files(
            file_system_store_location,
            docker_config
        )
        if len(discovered_config_files) > 0:
            collected_service_results_dicts[finder_instance.get_service_name()] = \
                (finder_instance.is_cluster_service(), discovered_config_files)
    dockerfile_entry = extract_docker_file_and_store(image_name)
    image_name_no_special_chars = replace_special_chars_with_underscore(image_name, True)
    if dockerfile_entry is not None:
        collected_service_results_dicts[f"{image_name_no_special_chars}_dockerfile"] = (
            False,
            [dockerfile_entry]
        )
        # collected_service_results_dicts["dockerfile"] = (False, [dockerfile_entry])
    if not collected_service_results_dicts:
        return None
    manifest_blueprint = {
        "name": replace_special_chars_with_underscore(image_name, True),
        "customerId": customer_id,
        "machines": {
            "container": {
                "id": "container",
            }
        },
        "clusterServices": {
        }
    }
    final_location = tempfile.mkdtemp(prefix="coguard-cli-folder")
    machine_location = os.path.join(final_location, "container")
    os.mkdir(machine_location)
    already_used_identifiers = set([f"{image_name_no_special_chars}_dockerfile"])
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
                if "services" not in manifest_blueprint["machines"]["container"]:
                    manifest_blueprint["machines"]["container"]["services"] = {}
                manifest_blueprint["machines"]\
                    ["container"]\
                    ["services"]\
                    [new_service_custom_identifier] = tuple_instance
                service_folder = os.path.join(machine_location, new_service_custom_identifier)
                os.mkdir(service_folder)
                shutil.copytree(tuple_dir, service_folder, dirs_exist_ok=True)
    if not manifest_blueprint["clusterServices"]:
        # Just to match the existing blueprint
        del manifest_blueprint["clusterServices"]
    if "services" not in manifest_blueprint["machines"]["container"]:
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

def extract_image_to_file_system(
        image_name: str) -> Optional[Tuple[str, Dict, str]]:
    """
    This is a helper function to extract the file system of the
    Docker image and put it into a folder. An optional tuple containing
    the path to this folder, the result of a `docker inspect`
    of that image and the temporary docker image created are returned.

    Remark: It is the function's caller's resposibility to delete the generated
    folder afterwards.
    """
    temp_image_name = docker_dao.create_docker_image(image_name)
    if temp_image_name is None:
        print(
            f"{COLOR_RED}Unable to extract image name {image_name}. Make sure you "
            "have provided the correct tag "
            f"and/or the image digest, or that you have the permission "
            f"to pull this specific image.{COLOR_TERMINATION}"
        )
        return None
    inspect_result = docker_dao.get_inspect_result(temp_image_name)
    if inspect_result is None:
        logging.debug("The docker inspect result was empty for %s (%s)",
                      temp_image_name, image_name)
        return None
    file_system_store_location = docker_dao.store_image_file_system(temp_image_name)
    if file_system_store_location is None:
        logging.debug("Could not extract file system location for %s (%s)",
                      temp_image_name, image_name)
        return None
    for (dir_loc, _, _) in os.walk(file_system_store_location):
        # This is to ensure that all folders can be written. We noticed some issues there
        # before.
        os.chmod(dir_loc, os.stat(dir_loc).st_mode | stat.S_IWRITE)
    return (file_system_store_location, inspect_result, temp_image_name)

def create_zip_to_upload_from_docker_image(
        collected_location_manifest_tuple: Optional[Tuple[str, Dict]]
) -> Optional[Tuple[str, Dict]]:
    """
    This function creates a zip file from a given image name which is
    ready to be uploaded to the CoGuard back-end. If something goes wrong,
    the output will be None; otherwise, it will be the path to the zip file.

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
    return (temp_zip, manifest_dict)
