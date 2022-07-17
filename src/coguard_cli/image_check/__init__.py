"""
Some of the main functionality gluing all the pieces in this
repo will get here.
"""

import json
import os
import shutil
import stat
import tempfile
from typing import Optional, Dict, Tuple
import zipfile
import urllib.parse
from coguard_cli.auth import DealEnum
from coguard_cli.image_check import docker_dao
import coguard_cli.image_check.config_file_finder_factory as factory
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
        docker_config: Dict) -> Optional[str]:
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
                discovered_config_files
    dockerfile_entry = extract_docker_file_and_store(image_name)
    if dockerfile_entry is not None:
        collected_service_results_dicts["dockerfile"] = [dockerfile_entry]
    if not collected_service_results_dicts:
        return None
    manifest_blueprint = {
        "name": urllib.parse.quote_plus(image_name),
        "customerId": customer_id,
        "machines": {
            "container": {
                "id": "container",
                "services": {}
            }
        }
    }
    final_location = tempfile.mkdtemp(prefix="coguard-cli-folder")
    machine_location = os.path.join(final_location, "container")
    os.mkdir(machine_location)
    for (service_id, tuple_list) in collected_service_results_dicts.items():
        for idx, (tuple_instance, tuple_dir) in enumerate(tuple_list):
            new_service_custom_identifier = f"{service_id}_{idx}"
            manifest_blueprint["machines"]\
                ["container"]\
                ["services"]\
                [new_service_custom_identifier] = tuple_instance
            service_folder = os.path.join(machine_location, new_service_custom_identifier)
            os.mkdir(service_folder)
            shutil.copytree(tuple_dir, service_folder, dirs_exist_ok=True)
    with open(os.path.join(final_location, "manifest.json"), "w", encoding='utf-8') \
         as manifest_file:
        json.dump(manifest_blueprint, manifest_file)
    # cleanup
    for _, tuple_list in collected_service_results_dicts.items():
        for (_, directory_to_delete) in tuple_list:
            shutil.rmtree(directory_to_delete, ignore_errors=True)
    return final_location

def create_zip_to_upload_from_docker_image(
        customer_id,
        image_name: str,
        deal_identifier: DealEnum) -> Optional[str]:
    """
    This function creates a zip file from a given image name which is
    ready to be uploaded to the CoGuard back-end. If something goes wrong,
    the output will be None; otherwise, it will be the path to the zip file.

    Keep in mind that whoever is calling this function is in charge of deleting
    the zip file afterwards.
    """
    temp_image_name = docker_dao.create_docker_image(image_name, deal_identifier != DealEnum.FREE)
    if temp_image_name is None:
        print(
            f"{COLOR_RED}Unable to extract image name. Make sure you "
            "have provided the correct tag "
            f"and/or the image digest.{COLOR_TERMINATION}"
        )
        return None
    inspect_result = docker_dao.get_inspect_result(temp_image_name)
    if inspect_result is None:
        return None
    file_system_store_location = docker_dao.store_image_file_system(temp_image_name)
    if file_system_store_location is None:
        return None
    collected_location = find_configuration_files_and_collect(
        image_name,
        customer_id,
        file_system_store_location,
        inspect_result
    )
    if collected_location is None:
        return None
    (file_handle, temp_zip) = tempfile.mkstemp(prefix="coguard_cli_zip_to_upload", suffix=".zip")
    os.close(file_handle)
    with zipfile.ZipFile(temp_zip, "w") as upload_zip:
        for (dir_path, _, file_names) in os.walk(collected_location):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                upload_zip.write(file_path, arcname=file_path[len(collected_location):])
    #cleanup
    shutil.rmtree(collected_location, ignore_errors=True)
    for (dir_loc, _, _) in os.walk(file_system_store_location):
        # This is to ensure that all folders can be written. We noticed some issues there
        # before.
        os.chmod(dir_loc, os.stat(dir_loc).st_mode | stat.S_IWRITE)
    shutil.rmtree(file_system_store_location, ignore_errors=True)
    docker_dao.rm_temporary_container_name(temp_image_name)
    return temp_zip
