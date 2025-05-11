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
from coguard_cli.check_common_util import replace_special_chars_with_underscore
from coguard_cli.util import create_service_identifier, \
    dry_run_outp, \
    upload_and_evaluate_zip_candidate
from coguard_cli.auth.token import Token
from coguard_cli import docker_dao
from coguard_cli.auth.enums import DealEnum
import coguard_cli.discovery.config_file_finder_factory as factory
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.print_colors import COLOR_RED, COLOR_TERMINATION, COLOR_CYAN, COLOR_YELLOW

def extract_docker_file_and_store(
        image_name: str,
        is_container_scan: bool=False) -> Optional[Tuple[Dict, str]]:
    """
    Very similar output as the config file finder factory items. The idea
    is that we will store the Dockerfile on the file-system and scan it as
    well.
    """
    docker_file = docker_dao.extract_docker_file(image_name, is_container_scan)
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
        docker_config: Dict,
        is_container_scan: bool=False) -> Optional[Tuple[str, Dict]]:
    """
    This function consumes a file_system store location and the docker_config,
    and extracts services and files from that, and stores it at a common location
    with a manifest file as acceptable by CoGuard. If nothing was possible to be
    extracted, None is returned.
    """
    collected_service_results_dicts = {}
    # For now, exclude SystemD
    for finder_instance in [
            entry for entry in factory.config_file_finder_factory()
            if not entry.get_service_name() == 'systemd'
    ]:
        discovered_config_files = finder_instance.find_configuration_files(
            file_system_store_location,
            docker_config
        )
        if len(discovered_config_files) > 0:
            collected_service_results_dicts[finder_instance.get_service_name()] = \
                (finder_instance.is_cluster_service(), discovered_config_files)
    dockerfile_entry = extract_docker_file_and_store(image_name, is_container_scan)
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
    return extract_container_to_filesystem(temp_image_name, image_name)

def extract_container_to_filesystem(
        container_name: str, image_name: Optional[str]=None) -> Optional[Tuple[str, Dict, str]]:
    """
    This is a helper function to extract the file system of the
    Docker container and put it into a folder. An optional tuple containing
    the path to this folder, the result of a `docker inspect`
    of that image and the temporary docker image created are returned.

    Remark: It is the function's caller's resposibility to delete the generated
    folder afterwards.
    """
    inspect_result = docker_dao.get_inspect_result(container_name)
    if inspect_result is None:
        logging.debug("The docker inspect result was empty for %s (%s)",
                      container_name, image_name)
        return None
    file_system_store_location = docker_dao.store_image_file_system(container_name)
    if file_system_store_location is None:
        logging.debug("Could not extract file system location for %s (%s)",
                      container_name, image_name)
        return None
    for (dir_loc, _, _) in os.walk(file_system_store_location):
        # This is to ensure that all folders can be written. We noticed some issues there
        # before.
        os.chmod(dir_loc, os.stat(dir_loc).st_mode | stat.S_IWRITE)
    return (file_system_store_location, inspect_result, container_name)

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

def perform_docker_image_scan(
        docker_image: Optional[str],
        auth_config: CoGuardCliConfig,
        deal_type: DealEnum,
        token: Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int,
        ruleset: str,
        dry_run: bool = False):
    """
    The helper function to run a Docker image scan. It takes in all necessary parameters.
    If the docker-image is None, then all Docker images found on the host system are being
    scanned.
    """
    docker_version = docker_dao.check_docker_version()
    if docker_version is None:
        print(f'{COLOR_RED}Docker is not installed on your system. '
              f'Please install Docker to proceed{COLOR_TERMINATION}')
        return
    print(f'{docker_version} detected.')
    if docker_image:
        images = [docker_image]
    else:
        print(
            f"{COLOR_CYAN}No image name provided, scanning all images "
            f"installed on this machine.{COLOR_TERMINATION}"
        )
        images = docker_dao.extract_all_installed_docker_images()
    for image in images:
        print(f"{COLOR_CYAN}SCANNING IMAGE {COLOR_TERMINATION}{image}")
        temp_folder, temp_inspection, temp_image = extract_image_to_file_system(
            image
        ) or (None, None, None)
        if temp_folder is None or temp_inspection is None or temp_image is None:
            logging.error("Could not extract files from image %s", docker_image)
            continue
        collected_config_file_tuple = find_configuration_files_and_collect(
            image,
            auth_config.get_username(),
            temp_folder,
            temp_inspection
        )
        if collected_config_file_tuple is None:
            print(f"{COLOR_YELLOW}Image {image} - NO CONFIGURATION FILES FOUND.")
            return
        zip_candidate = create_zip_to_upload_from_docker_image(
            collected_config_file_tuple
        )
        # cleanup
        shutil.rmtree(collected_config_file_tuple[0], ignore_errors=True)
        shutil.rmtree(temp_folder, ignore_errors=True)
        docker_dao.rm_temporary_container_name(temp_image)
        if zip_candidate is None:
            print(f"{COLOR_YELLOW}Image {image} - NO CONFIGURATION FILES FOUND.")
            return
        if dry_run:
            dry_run_outp(zip_candidate)
        else:
            upload_and_evaluate_zip_candidate(
                zip_candidate,
                auth_config,
                deal_type,
                token,
                coguard_api_url,
                image,
                output_format,
                fail_level,
                organization,
                ruleset
            )

def perform_docker_container_scan(
        docker_container: Optional[str],
        auth_config: CoGuardCliConfig,
        deal_type: DealEnum,
        token: Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int,
        ruleset: str,
        dry_run: bool = False):
    """
    The helper function to run a Docker image scan. It takes in all necessary parameters.
    If the docker-image is None, then all Docker images found on the host system are being
    scanned.
    """
    docker_version = docker_dao.check_docker_version()
    if docker_version is None:
        print(f'{COLOR_RED}Docker is not installed on your system. '
              f'Please install Docker to proceed{COLOR_TERMINATION}')
        return
    print(f'{docker_version} detected.')
    if docker_container:
        containers = [docker_container]
    else:
        print(
            f"{COLOR_CYAN}No image name provided, scanning all images "
            f"installed on this machine.{COLOR_TERMINATION}"
        )
        containers = docker_dao.extract_all_running_docker_containers()
    for container in containers:
        print(f"{COLOR_CYAN}SCANNING CONTAINER {COLOR_TERMINATION}{container}")
        temp_folder, temp_inspection, _ = extract_container_to_filesystem(
            container
        ) or (None, None, None)
        if temp_folder is None or temp_inspection is None:
            logging.error("Could not extract files from container %s", docker_container)
            continue
        collected_config_file_tuple = find_configuration_files_and_collect(
            container,
            auth_config.get_username(),
            temp_folder,
            temp_inspection,
            True
        )
        if collected_config_file_tuple is None:
            print(f"{COLOR_YELLOW}Container {container} - NO CONFIGURATION FILES FOUND.")
            return
        zip_candidate = create_zip_to_upload_from_docker_image(
            collected_config_file_tuple
        )
        # cleanup
        shutil.rmtree(collected_config_file_tuple[0], ignore_errors=True)
        shutil.rmtree(temp_folder, ignore_errors=True)
        if zip_candidate is None:
            print(f"{COLOR_YELLOW}Container {container} - NO CONFIGURATION FILES FOUND.")
            return
        if dry_run:
            dry_run_outp(zip_candidate)
        else:
            upload_and_evaluate_zip_candidate(
                zip_candidate,
                auth_config,
                deal_type,
                token,
                coguard_api_url,
                container,
                output_format,
                fail_level,
                organization,
                ruleset
            )
