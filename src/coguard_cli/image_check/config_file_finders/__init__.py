"""
Some common functions for config file finding.
"""

import os
import re
import logging
import shutil
import tempfile
from typing import Optional, Dict, List
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

def get_path_behind_symlinks(
        path_to_file_system: str,
        path_to_check: str,
        recursion_counter: int=10) -> Optional[str]:
    """
    Sometimes, we encounter a myriad of symlinks inside Docker containers.
    This function is a helper function to avoid duplicate code. It consumes
    a path, and if the path represents a symlink, it resolves the path
    until an actual file is encountered, with a depth of at most recursion_counter.

    :param path_to_file_system: The path to the file-system, as it has been
                                copied to a temporary folder.
    :param path_to_check: The path to resolves
    :param recursion_counter: The recursion_counter, which decreases with every call.
    """
    if recursion_counter < 0:
        return None
    if not os.path.islink(path_to_check):
        return path_to_check
    read_link = os.readlink(path_to_check)
    tail_path = read_link[1:] if read_link.startswith(os.path.sep) \
        else read_link
    return get_path_behind_symlinks(
        path_to_file_system,
        os.path.join(path_to_file_system, tail_path),
        recursion_counter - 1
    )

def adapt_match_to_actual_finds(
        match: str,
        is_dir: bool,
        current_path: str,
        optional_file_ending_regex: str = "") -> Optional[str]:
    """
    This function takes a match object, which can have forms like

    ```
    /etc/mime.types
    ../../nginx.conf.d/*.conf
    ```
    and a current file system find for the local copy of the file system.
    For the above examples, that would be
    ```
    /tmp/foo/etc/mime.types
    /tmp/foo/etc/nginx.conf.d/extra.conf
    ```
    It produces a match object in the same way as it is relative in the
    match object, i.e.
    ```
    /etc/mime.types
    ../../nginx.conf.d/extra.conf
    ```

    :param match: The match object as found in the include directive
    :param is_dir: The indicator that the match is actually a directory
    :param current_path: The current path as found on the file system.
    :param optional_file_ending_regex: Some software require configurations
                                       to have a certain file suffix to be
                                       included. This parameter accounts
                                       for that.
    """
    logging.debug(
        "Trying to adapt match %s, which is %s a directory in current path %s with ending %s",
        match,
        "not" if not is_dir else "",
        current_path,
        optional_file_ending_regex
    )
    truncated_match = re.search(f"[\\.{os.path.sep}]*(.*)", match).group(1)
    prefix = match.replace(truncated_match, "")
    to_search = \
        f".*({truncated_match.strip().replace('*', '.*')}.*{optional_file_ending_regex})$" \
        if not is_dir else f".*({truncated_match.strip()}.*)$"
    finding_truncated_search = re.search(
        to_search,
        current_path
    )
    if not finding_truncated_search:
        logging.error("%s is not to be found in path %s, even though this should be the case",
                      match,
                      current_path)
        return None
    return prefix + finding_truncated_search.group(1)

#pylint: disable=too-many-arguments
#pylint: disable=too-many-locals
def copy_and_populate(
        path_to_file_system,
        starting_point,
        match,
        is_dir,
        temp_location,
        current_manifest,
        config_file_type,
        include_match_single_re,
        include_match_dir_re,
        optional_file_ending_regex: str = "") -> None:
    """
    Helper function for :_extract_include_directives:
    It consumes a starting_point, i.e. the path the match
    is relative to, the temp location where the current
    CoGuard file structure is stored, and the current manifest where
    we are going to capture the manifest entries for all
    complimentary files.

    :param path_to_file_system: The temporary folder where the container's
                                file system is stored.
    :param starting_point: The match that we got from an `include` directive
      has either a path relative to the my.ini file, or it is starting
      from the root directory. This starting point is captured here.
    :param match: The particular match of a file or wildcard we need, relative to the
      starting_point parameter.
    :param is_dir: The flag if we are dealing with a directory or not.
    :param temp_location: That is the location where the my.ini is currently moved
        and where all the other configuration files are supposed to be stored.
    :param current_manifest: The current manifest entries for my.ini, where we
        are going to update things to ensure that we capture all the files.
    :param config_file_type: The configuration file type of the include directive
                             files we expect.
    :param include_match_single_re: The regular expression extracting an include directive
                                    for a single file.
    :param include_match_dir_re: The regular expression extracting an include directive
                                 for a folder.
    :param optional_file_ending_regex: Some software require configurations
                                       to have a certain file suffix to be
                                       included. This parameter accounts
                                       for that.
    """
    logging.debug("working with match %s", match)
    match_without_leading_slash = match[1:] if match.startswith("/") else match
    realpath_match = os.path.abspath(os.path.join(starting_point, match_without_leading_slash))
    for (dir_path, _, file_names) in os.walk(starting_point):
        for file_name in file_names:
            abs_path_file = os.path.abspath(os.path.join(dir_path, file_name))
            match_regex = realpath_match.strip().replace("*", ".*") + "$" if not is_dir \
                else realpath_match.strip() + f"{optional_file_ending_regex}$"
            if re.match(match_regex, abs_path_file):
                alias_entry = adapt_match_to_actual_finds(
                    match,
                    is_dir,
                    abs_path_file,
                    optional_file_ending_regex
                )
                if alias_entry in [
                        elem for entry in current_manifest.get("complimentaryFileList", [])
                        for elem in entry.get("aliasList", [])
                ]:
                    continue
                print(f"{COLOR_CYAN}Found included file {alias_entry}.")
                logging.debug("match %s against %s",
                              realpath_match,
                              abs_path_file)
                (_, tmp_file_location) = tempfile.mkstemp(dir=temp_location)
                to_copy = get_path_behind_symlinks(
                    path_to_file_system,
                    abs_path_file
                )
                shutil.copy(
                    to_copy,
                    tmp_file_location
                )
                current_manifest['complimentaryFileList'].append({
                    "fileName": os.path.basename(tmp_file_location),
                    "subPath": ".",
                    "configFileType": config_file_type,
                    "aliasList": [alias_entry]
                })
                extract_include_directives(
                    path_to_file_system,
                    abs_path_file,
                    temp_location,
                    current_manifest,
                    config_file_type,
                    include_match_single_re,
                    include_match_dir_re,
                    optional_file_ending_regex
                )

def extract_include_directives(
        path_to_file_system: str,
        location_on_current_machine: str,
        temp_location: str,
        current_manifest: Dict,
        config_file_type: str,
        include_match_single_re: str,
        include_match_dir_re: str = "",
        optional_file_ending_regex: str = ""
) -> None:
    """
    The helper function for :check_for_config_files_in_standard_location:.

    It consumes the path to the file-system, i.e. where it is stored,
    current location of the my.ini file called
    `location_on_current_machine`, and the current manifest dictionary, and
    parses the mysql configuration and figures out if there are files
    which need to be included, puts them into the folder with the mysql
    conf and creates the correct alias entries in the current_manifest dictionary.

    :param path_to_file_system: The contents of the image are stored in a folder X,
        and this folder can be viewed like `/` from the perspective of the
        container the image would spin up
    :param location_on_current_machine: The location where the configuration file is
        stored on the current machine, inside the container sub-directory. I.e., this
        file will be somewhere inside path_to_file_system
    :param temp_location: That is the location where the my.ini is currently moved
        and where all the other configuration files are supposed to be stored.
    :param current_manifest: The current manifest entries for mysql, where we
        are going to update things to ensure that we capture all the files.
    :param config_file_type: The configuration file type of the include directive
                             files we expect.
    :param include_match_single_re: The regular expression extracting an include directive
                                    for a single file.
    :param include_match_dir_re: The regular expression extracting an include directive
                                 for a folder.
    :param optional_file_ending_regex: Some software require configurations
                                       to have a certain file suffix to be
                                       included. This parameter accounts
                                       for that.
    """
    service_directory = os.path.dirname(location_on_current_machine)
    to_open = get_path_behind_symlinks(
        path_to_file_system,
        location_on_current_machine
    )
    with open(to_open, 'r', encoding='utf-8') as base_conf:
        lines = base_conf.readlines()
    for line in lines:
        include_match_single = re.findall(include_match_single_re, line)
        include_match_dir = re.findall(include_match_dir_re, line) \
            if include_match_dir_re else None
        if include_match_single:
            logging.debug("Found match: %s", include_match_single)
            for match in set(include_match_single):
                starting_point = path_to_file_system \
                    if match.startswith("/") else service_directory
                copy_and_populate(
                    path_to_file_system,
                    starting_point,
                    match,
                    False,
                    temp_location,
                    current_manifest,
                    config_file_type,
                    include_match_single_re,
                    include_match_dir_re,
                    optional_file_ending_regex
                )
        if include_match_dir:
            logging.debug("Found match: %s", include_match_dir)
            for match in set(include_match_dir):
                starting_point = path_to_file_system \
                    if match.startswith("/") else service_directory
                copy_and_populate(
                    path_to_file_system,
                    starting_point,
                    match,
                    True,
                    temp_location,
                    current_manifest,
                    config_file_type,
                    include_match_single_re,
                    include_match_dir_re,
                    optional_file_ending_regex
                )

def common_call_command_in_container(
        docker_config: Dict,
        executable_regex: str) -> List[str]:
    """
    The common use of the function check_call_command_in_container

    :param docker_config: The output when running `docker inspect <IMAGE NAME>`
    :param executable_regex: We are searching for the call of the executable, which
                             gets passed a custom location for the configuration file.
                             The regex to extract this path is passed here.
    """
    entrypoint_entry = docker_config.get("Config", {}).get("Entrypoint", [])
    if entrypoint_entry is None:
        entrypoint_entry = []
    entrypoint_entry = entrypoint_entry if isinstance(entrypoint_entry, list) \
        else [entrypoint_entry]
    entrypoint_entry = " ".join(entrypoint_entry)
    cmd_entry = docker_config.get("Config", {}).get("Cmd", [])
    if cmd_entry is None:
        cmd_entry = []
    cmd_entry = cmd_entry if isinstance(cmd_entry, list) else [cmd_entry]
    cmd_entry = " ".join(cmd_entry)
    if not (entrypoint_entry or cmd_entry):
        return []
    result_files = []
    #strategy 1: direct entry
    result_files.extend(
        [os.path.split(entry)[-1]
         for entry in re.findall(executable_regex, entrypoint_entry)]
    )
    result_files.extend(
        [os.path.split(entry)[-1]
         for entry in re.findall(executable_regex, cmd_entry)]
    )
    # strategy 2: see if there are executable files in entrypoint or command
    # and potentially extract the kafka regular expression there.
    command_regex = r"(/bin/(sh|bash|zsh)\s+-c\s+)?([^\s]+)"
    executable_entrypoint = re.search(command_regex, entrypoint_entry).groups()[-1] \
        if re.search(command_regex, entrypoint_entry) is not None else None
    executable_cmd = re.search(command_regex, cmd_entry).groups()[-1] \
        if re.search(command_regex, cmd_entry) is not None else None
    working_dir = docker_config.get("WorkingDir", "")
    # pylint: disable=bare-except
    for executable in [executable_entrypoint, executable_cmd]:
        if executable and \
           os.path.exists(os.path.join(working_dir, executable)):
            try:
                with open(
                        os.path.join(working_dir, executable),
                        'r',
                        encoding='utf-8'
                ) as entrypoint_executable:
                    result_files.extend([
                        os.path.split(entry)[-1]
                        for entry in re.findall(
                                executable_regex,
                                entrypoint_executable.read(),
                                re.DOTALL
                        )])
            except:
                pass
    return result_files
