"""
Some common functions for config file finding.
"""

import os
import re
import logging
import copy
import shutil
import tempfile
from typing import Optional, Dict, List, Tuple, Union, Callable
import json
import yaml
from flatten_dict import unflatten
from coguard_cli.util import convert_string_to_posix_path
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
        optional_file_ending_regex: str = "",
        default_file_name: str = "") -> None:
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
                else realpath_match.strip() + f".*{optional_file_ending_regex}$"
            logging.debug("Checking if %s matches %s.",
                          abs_path_file,
                          match_regex)
            if re.match(match_regex, abs_path_file):
                alias_entry = adapt_match_to_actual_finds(
                    match,
                    is_dir,
                    abs_path_file,
                    optional_file_ending_regex
                )
                list_to_add = "complimentaryFileList" if not default_file_name else "configFileList"
                if alias_entry in [
                        elem for entry in current_manifest.get(list_to_add, [])
                        for elem in entry.get("aliasList", [])
                ]:
                    continue
                print(f"{COLOR_CYAN}Found included file {alias_entry}.{COLOR_TERMINATION}")
                logging.debug("match %s against %s",
                              realpath_match,
                              abs_path_file)
                (_, tmp_file_location) = tempfile.mkstemp(dir=temp_location)
                to_copy = get_path_behind_symlinks(
                    path_to_file_system,
                    abs_path_file
                )
                if not os.path.exists(to_copy):
                    logging.error("Could not find the file or resolve the symlink at `%s`",
                                  abs_path_file)
                    continue
                shutil.copy(
                    to_copy,
                    tmp_file_location
                )
                to_append = {
                    "fileName": os.path.basename(tmp_file_location),
                    "subPath": ".",
                    "configFileType": config_file_type,
                    "aliasList": [alias_entry]
                }
                if default_file_name:
                    to_append["defaultFileName"] = default_file_name
                current_manifest[list_to_add].append(to_append)
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
        optional_file_ending_regex: str = "",
        default_file_name: str = ""
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
                    optional_file_ending_regex,
                    default_file_name
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
                    optional_file_ending_regex,
                    default_file_name
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
        [os.path.split(entry)[-1] if isinstance(entry, str) else os.path.split(entry[-1])[-1]
         for entry in re.findall(executable_regex, entrypoint_entry)]
    )
    result_files.extend(
        [os.path.split(entry)[-1] if isinstance(entry, str) else os.path.split(entry[-1])[-1]
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
                        os.path.split(entry)[-1] if isinstance(entry, str)
                        else os.path.split(entry[-1])[-1]
                        for entry in re.findall(
                                executable_regex,
                                entrypoint_executable.read(),
                                re.DOTALL
                        )])
            except:
                pass
    return result_files

def _amalgamate_keys(path_dict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Helper function for amalgamating paths if they are direct subpaths from each other.
    This is in assistance to the `group_found_files_by_subpath` function.
    """
    change_done = False
    first_run = True
    result_dict = copy.deepcopy(path_dict)
    while (change_done or first_run):
        first_run = False
        change_done = False
        logging.debug("Current state of dict during amalgamation %s", str(result_dict))
        keys = sorted(result_dict.keys())
        for i, i_itm in enumerate(keys):
            if not i_itm:
                #emtpy string case
                continue
            for j in range(i + 1, len(keys)):
                if keys[j].startswith(i_itm):
                    result_dict[i_itm].extend(result_dict[keys[j]])
                    del result_dict[keys[j]]
                    change_done = True
                    break
            if change_done:
                break
    return result_dict


def group_found_files_by_subpath(
        path_to_file_system: str,
        files: List[str]) -> Dict[str, List[str]]:
    """
    This function takes files that are identified by the system as
    configuration files, and groups them together potentially to belong
    to the same device/cluster. They all have the `path_to_filesystem`
    prefix in common. The output is a dictionary with keys being common prefixes
    and values being a list of files falling under the common prefixes.

    The algorithm to determine these prefixes works as follows.

    All files have the form
    ```
    path_to_file_system/sub_path/file-name
    ```

    The `path_to_file_system` part is being cut out, where only

    ```
    sub_path/file-name
    ```

    remains. If `sub_path` has less than three folders in its path, the first key of subpath is
    the key under which the file is being stored in the end. If there are three or more
    folders, say a/b/c, we are cutting off b/c and assume that
    files which have a in common belong together, and the key in the dictionary
    is `a`. If there are keys in the final dictionary that are prefixes of each other,
    these keys are amalgamated in the end.

    Example:

    Say you have a list of files

    ```
    "/etc/foo/bar/foo.txt",
    "/etc/foo/bar/bar.txt",
    "/etc/foo/bar/baz/biz/foo.txt",
    "/etc/foo/bor/boz/bez/biz.txt",
    "/etc/bla.txt"
    ```

    The resulting dictionary in the end should be

    ```
    {
        "foo": [
            "/etc/foo/bar/foo.txt",
            "/etc/foo/bar/bar.txt",
            "/etc/foo/bar/baz/biz/foo.txt",
            "/etc/foo/bor/boz/bez/biz.txt"
        ],
        "": [
            "/etc/bla.txt"
        ]
    }
    ```
    """
    result = {}
    for result_file in files:
        extracted_subpath = (os.path.dirname(result_file)+os.sep).replace(
            path_to_file_system,
            ''
        )
        extracted_subpath = extracted_subpath.strip(os.sep)
        logging.debug("Extracted subPath for file %s: %s.",
                      result_file,
                      extracted_subpath)
        sub_path_split = [entry for entry in extracted_subpath.split(os.sep)
                          if entry]
        if len(sub_path_split) <= 2:
            key_val = os.sep.join(sub_path_split[0:1]) if sub_path_split else ''
        else:
            key_val = os.sep.join(sub_path_split[:-2])
        list_to_expand = result.setdefault(key_val, [])
        list_to_expand.append(result_file)
    return _amalgamate_keys(result)

def create_grouped_temp_locations_and_manifest_entries(
        path_to_file_system: str,
        files_dict: Dict[str, List[str]],
        service_name,
        default_file_name: Union[str, Callable[[str], str]],
        config_file_type) -> List[Tuple[Dict, str]]:
    """
    This function acts similar to `create_temp_location_and_manifest_entry`,
    with the main difference that it takes the output of `group_found_files_by_subpath`
    and creates a list of temporary folders and manifest entries.
    """
    result = []
    for file_list in files_dict.values():
        temp_location = tempfile.mkdtemp(prefix=f"coguard-cli-{service_name}")
        manifest_entry = {
            "version": "1.0",
            "serviceName": service_name,
            "configFileList": [],
            "complimentaryFileList": []
        }
        for location_on_current_machine in file_list:
            to_copy = get_path_behind_symlinks(
                path_to_file_system,
                location_on_current_machine
            )
            if not os.path.exists(to_copy):
                logging.info("The file was a symlink did not lead to a proper file. Ignoring")
                continue
            # The reason we added os.sep at the end is because the file location may be
            # at the root of the path_to_file_system. In this case, if there is a separation
            # character at the end of path_to_file_system, the replace may not work.
            # That is why we just add it here.
            loc_within_machine = (os.path.dirname(location_on_current_machine)+os.sep).replace(
                path_to_file_system,
                ''
            )
            loc_within_machine = loc_within_machine[1:] \
                if loc_within_machine.startswith(os.sep) \
                   else loc_within_machine
            os.makedirs(os.path.join(temp_location, loc_within_machine), exist_ok=True)
            shutil.copy(
                to_copy,
                os.path.join(
                    temp_location,
                    loc_within_machine,
                    os.path.basename(location_on_current_machine)
                )
            )
            manifest_entry["configFileList"].append(
                {
                    "fileName": os.path.basename(location_on_current_machine),
                    "defaultFileName": default_file_name if isinstance(default_file_name, str)
                    else default_file_name(os.path.basename(location_on_current_machine)),
                    "subPath": f"./{convert_string_to_posix_path(loc_within_machine)}",
                    "configFileType": config_file_type
                }
            )
        result.append((manifest_entry, temp_location))
    return result

def create_temp_location_and_manifest_entry(
            path_to_file_system: str,
            file_name: str,
            location_on_current_machine: str,
            service_name: str,
            default_file_name: str,
            config_file_type: str) -> Optional[Tuple[Dict, str]]:
    """
    Common helper function which creates a temporary folder location for the
    configuration files. It returns
    a tuple containing a manifest for a kubernetes service and the path to the
    temporary location.
    """
    temp_location = tempfile.mkdtemp(prefix=f"coguard-cli-{service_name}")
    to_copy = get_path_behind_symlinks(
        path_to_file_system,
        location_on_current_machine
    )
    # The reason we added os.sep at the end is because the file location may be
    # at the root of the path_to_file_system. In this case, if there is a separation
    # character at the end of path_to_file_system, the replace may not work.
    # That is why we just add it here.
    loc_within_machine = (os.path.dirname(location_on_current_machine)+os.sep).replace(
        path_to_file_system,
        ''
    )
    loc_within_machine = loc_within_machine[1:] \
        if loc_within_machine.startswith(os.sep) \
           else loc_within_machine
    os.makedirs(os.path.join(temp_location, loc_within_machine), exist_ok=True)
    if not os.path.exists(to_copy):
        logging.error("Could not find the file or resolve the symlink at `%s`",
                      location_on_current_machine)
        return None
    shutil.copy(
        to_copy,
        os.path.join(
            temp_location,
            loc_within_machine,
            os.path.basename(location_on_current_machine)
        )
    )
    manifest_entry = {
        "version": "1.0",
        "serviceName": service_name,
        "configFileList": [
            {
                "fileName": file_name,
                "defaultFileName": default_file_name,
                "subPath": f"./{convert_string_to_posix_path(loc_within_machine)}",
                "configFileType": config_file_type
            }
        ],
        "complimentaryFileList": []
    }
    return (
        manifest_entry,
        temp_location
    )

def create_temp_location_and_manifest_entry_same_service(
            path_to_file_system: str,
            file_tuples: Tuple[str, str, str, str],
            service_name: str) -> Optional[Tuple[Dict, str]]:
    """
    Common helper function which creates a temporary folder location for the
    configuration files. It returns
    a tuple containing a manifest for a kubernetes service and the path to the
    temporary location.
    Difference to the create_temp_location_and_manifest_entry is that it has
    a bunch of files for the same service, with different configuration file types.
    The file-tuples cotain
    """
    temp_location = tempfile.mkdtemp(prefix=f"coguard-cli-{service_name}")
    manifest_entry = {
        "version": "1.0",
        "serviceName": service_name,
        "configFileList": [
        ],
        "complimentaryFileList": []
    }
    config_file_list = manifest_entry["configFileList"]
    for file_name, location_on_current_machine, default_file_name, config_file_type \
            in file_tuples:
        to_copy = get_path_behind_symlinks(
            path_to_file_system,
            location_on_current_machine
        )
        # The reason we added os.sep at the end is because the file location may be
        # at the root of the path_to_file_system. In this case, if there is a separation
        # character at the end of path_to_file_system, the replace may not work.
        # That is why we just add it here.
        loc_within_machine = (os.path.dirname(location_on_current_machine)+os.sep).replace(
            path_to_file_system,
            ''
        )
        loc_within_machine = loc_within_machine[1:] \
            if loc_within_machine.startswith(os.sep) \
               else loc_within_machine
        os.makedirs(os.path.join(temp_location, loc_within_machine), exist_ok=True)
        if not os.path.exists(to_copy):
            logging.error("Could not find the file or resolve the symlink at `%s`",
                          location_on_current_machine)
            return None
        shutil.copy(
            to_copy,
            os.path.join(
                temp_location,
                loc_within_machine,
                os.path.basename(location_on_current_machine)
            )
        )
        config_file_list.append({
            "fileName": file_name,
            "defaultFileName": default_file_name,
            "subPath": f"./{convert_string_to_posix_path(loc_within_machine)}",
            "configFileType": config_file_type
        })
    return (
        manifest_entry,
        temp_location
    )

def does_config_yaml_contain_required_keys(file_path: str, required_fields: List[str]) -> bool:
    """
    Helper function to check if a yaml file as defined by `file_path` contains a set of
    mandatory keys as provided by `required_fields`.
    """
    config = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file_stream:
            config_res = yaml.safe_load_all(file_stream)
            config = [] if config_res is None else [
                (unflatten(config_part, splitter='dot')
                 if not isinstance(config_part, list)
                 else config_part)
                for config_part in config_res
                if config_part is not None
            ]
    #pylint: disable=bare-except
    except:
        logging.debug(
            "Failed to load %s",
            file_path
        )
        return False
    logging.debug("The config object looks like: %s",
                  str(config))
    return config and all(config_instance and required_field in config_instance
                          for config_instance in config
                          for required_field in required_fields)

def does_config_json_contain_required_keys(file_path: str, required_fields: List[str]) -> bool:
    """
    Helper function to check if a yaml file as defined by `file_path` contains a set of
    mandatory keys as provided by `required_fields`.
    """
    config = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file_stream:
            config_res = json.load(file_stream)
            config = {} if config_res is None else config_res
        config = unflatten(config, splitter='dot')
    #pylint: disable=bare-except
    except:
        logging.debug(
            "Failed to load %s",
            file_path
        )
        return False
    logging.debug("The config object looks like: %s",
                  str(config))
    return config and all(required_field in config
                          for required_field in required_fields)
