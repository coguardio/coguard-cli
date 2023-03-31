"""
This module contains the direct access the docker interface on the machine.
"""

import json
import re
import tempfile
import subprocess
import uuid
import logging
import tarfile
import os
from typing import Optional, Dict, List, Tuple

DOCKER_CALL_TIMEOUT_S = 300

def is_image_name_from_custom_repo(image_name: str) -> bool:
    """
    Checks if the image name is coming from a custom repository,
    and returns the respective result.

    :param image_name: The image name to be checked.
    :returns: The result of the check if the image came from a custom repo or not.
    """
    complete_split = image_name.split("/")
    if len(complete_split) <= 1:
        return False
    potential_domain_part = complete_split[0]
    return ('.' in potential_domain_part) or (':' in potential_domain_part)

def check_docker_version() -> Optional[str]:
    """
    This function checks if Docker is installed or not.

    :returns: Returns the Docker version as returned by the command `docker --version`,
              or None if there was an error running that command.
    """
    try:
        return subprocess.run(
            'docker --version',
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        ).stdout.decode().strip()
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to check the Docker version: %s", str(exception))
        return None
    return None

def create_docker_image(image_name: str) -> Optional[str]:
    """
    This function loads a Docker image and returns its created name, or None,
    if an error occurred.
    It returns the temporary folder location as string where the contents of the container
    is stored, or None if an error occurred.

    There is an extra parameter called custom_repo_allowed. If the user is trying
    to pull an image from a custom repository, and this flag is false, None is returned.

    Keep in mind that it is the caller's responsibility to delete the image.

    :param image_name: The name of the image where we wish to create a container from.
    :param custom_repo_allowed: Indicates whether or not a custom repository is allowed.
    :returns: The name of the image, if it could be created, or None.
    """
    temporary_image_name = str(uuid.uuid4())
    try:
        subprocess.run(
            f'docker create --name="{temporary_image_name}" {image_name}',
            check=True,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_CALL_TIMEOUT_S
        )
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to create the docker image: %s", str(exception))
        return None
    return temporary_image_name

# pylint: disable=broad-except
def store_image_file_system(temporary_container_name: str) -> Optional[str]:
    """
    This is the function which, given a container id, stores the file system in
    a random location. The location is returned by this function, or None, if
    something went wrong.

    Keep in mind that it is the responsibility of the caller to delete the folder
    once it is not used any more.

    :param temporary_container_name: The name of the container after we created it.
    :returns: The path where the filesystem of the image is stored, or None, if an
              error occurred.
    """
    if temporary_container_name is None:
        return None
    tmpdir_path = tempfile.mkdtemp(prefix="coguard-cli-")
    content_tar = os.path.join(tmpdir_path, "contents.tar")
    try:
        subprocess.run(
            f'docker export --output {content_tar} {temporary_container_name}',
            check=True,
            shell=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        )
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to extract the filesystem from the image: %s", str(exception))
        return None
    try:
        with tarfile.open(content_tar) as tarf:
            members_to_extract = [tar_info for tar_info in tarf.getmembers()
                                  if not tar_info.isdev()]
            tarf.extractall(path=tmpdir_path, members=members_to_extract)
    except Exception as exception:
        logging.error("Failed to extract the image filesystem: %s",
                      str(exception))
        return None
    os.remove(content_tar)
    return tmpdir_path

def get_inspect_result(temporary_container_name: Optional[str]) -> Optional[Dict]:
    """
    This is the function which, given a container id, retrieves the JSON
    that would be returned by `docker inspect temporary_container_name`.

    :param temporary_container_name: The temporary name we gave the container after creation.
    :returns: The JSON-parsed output of `docker inspect` with the respective image name.
    """
    if temporary_container_name is None:
        return None
    try:
        config_string = subprocess.run(
            f'docker inspect "{temporary_container_name}"',
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        ).stdout
        config_object = json.loads(config_string)
        if not isinstance(config_object, list) or len(config_object) == 0:
            logging.debug("Somehow, the output of docker inspect was not a list or empty: %s",
                          config_object)
            return None
        return config_object[0]
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to inspect the container of the image: %s", str(exception))
        return None
    except json.JSONDecodeError as exception:
        logging.error("The docker inspect command did not return a valid JSON: %s", str(exception))
        return None
    return None

def rm_temporary_container_name(temporary_container_name: Optional[str]) -> None:
    """
    The helper function to remove a temporary container created for our purposes.

    :param temporary_container_name: The temporary container name after creation.
    """
    if temporary_container_name is None:
        return
    try:
        subprocess.run(
            f'docker rm "{temporary_container_name}"',
            check=True,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_CALL_TIMEOUT_S
        )
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to remove the container or image: %s", str(exception))

def extract_docker_file(image_name: str) -> Optional[str]:
    """
    The extraction of the Docker file from a given image name

    :param image_name: The name of the image.
    :returns: The extracted Dockerfile from the history as string, or None.
    """
    try:
        outp = subprocess.run(
            f'docker history --no-trunc --format \'{{{{.CreatedBy}}}}\' "{image_name}"',
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        ).stdout
        lines = outp.decode().split('\n')
        lines.reverse()
        lines = [re.sub(r"^.*#\(nop\)", "", line) for line in lines]
        # The following is currently an issue with docker history,
        #where the labels are not surrounded by quotations.
        lines = [line for line in lines if not re.match(r"^\s*label\s+.*$", line.lower())]
        return "\n".join(lines)
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to inspect the container of the image: %s", str(exception))
        return None
    return None

def extract_all_installed_docker_images() -> List[str]:
    """
    If we want a list of all installed Docker images, this function produces it.

    :returns: A list of strings, where the strings are names of locally installed Docker images.
    """
    try:
        outp = subprocess.run(
            "docker image ls --format '{{.Repository}}:{{.Tag}}'",
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        ).stdout
        lines = outp.decode().split('\n')
        lines = [line.strip() for line in lines if "<none>" not in line]
        return lines
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to list all images: %s", str(exception))
        return []
    return []

def get_kubernetes_translation_from_helm(helm_dir: str) -> Optional[str]:
    """
    Helper function to call HELM and translate the directory directives
    into kubernetes yamls. Returns the output of the command
    `helm template <helm_dir>`
    """
    try:
        return subprocess.run(
            f"docker run --rm -v \"{helm_dir}\":/opt/infra alpine/helm template /opt/infra/",
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        ).stdout.decode()
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to run the helm_image extraction: %s", str(exception))
        return None
    return None

def terraformer_wrapper(location_to_mount: str,
                        environment_variables: Dict[str, str],
                        mounts: List[Tuple[str, str]],
                        cloud_provider_name: str,
                        cloud_provider_alt_name: str) -> bool:
    """
    This function builds and runs the terraformer wrapper we built for CoGuard.
    """
    terraformer_wrapper_image_name = f"terraformer_coguard_wrapper_{cloud_provider_name}"
    terraformer_container_name = f"coguard_terraformer_extract_{cloud_provider_name}"
    working_dir_of_this_file = os.path.dirname(os.path.abspath(__file__))
    try:
        logging.info("Creating cloud extraction image on this machine.")
        subprocess.run(
            f"docker build --platform linux/amd64 -t {terraformer_wrapper_image_name} " + \
            os.path.join(working_dir_of_this_file,
                         "discovery",
                         "cloud_discovery",
                         "terraformer_extract_image_helper") + \
            f" --build-arg USER_ID={os.getuid()} --build-arg GROUP_ID={os.getgid()}" + \
            f" --build-arg PROVIDER={cloud_provider_name}" + \
            f" --build-arg PROVIDER_ALT={cloud_provider_alt_name}",
            check=True,
            shell=True,
            capture_output=True,
            timeout=DOCKER_CALL_TIMEOUT_S
        )
        logging.info("Extracting your cloud configurations. This may take a while.")
        subprocess.run(
            f"docker container stop {terraformer_container_name} || true && " + \
            f"docker container rm {terraformer_container_name} || true && " + \
            f"docker run --name={terraformer_container_name} " + \
            f"-v \"{location_to_mount}\":/opt/terraformer_export_data " + \
            " ".join(f"-v \"{k}\":\"{v}\"" for k, v in mounts) + \
            " ".join(f"-e \"{k}\"='{v}'" for k, v in environment_variables.items()) + \
            f" {terraformer_wrapper_image_name}",
            check=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DOCKER_CALL_TIMEOUT_S * 100
        )
        return True
    except subprocess.CalledProcessError as exception:
        logging.error("Failed to run the terraformer wrapper: %s", str(exception))
        return False
    return False
