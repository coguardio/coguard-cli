"""
Common utilities throughout the project.
"""

import os
import logging
import re
from typing import Set, Dict, Optional

def replace_special_chars_with_underscore(string: str) -> str:
    """
    Helper function remove any special character with underscore.
    """
    return re.sub("[^a-zA-Z1-9]", "_", string)

def create_service_identifier(prefix: str,
                              currently_used_service_names: Set[str],
                              service_instance: Dict) -> Optional[str]:
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
    sub_path_list = [entry["subPath"] for entry in service_instance["configFileList"]]
    common_prefix=os.path.commonpath(sub_path_list).strip(f".{os.sep}").replace(os.sep, "_") \
        if len(sub_path_list) >= 2 else ""
    if common_prefix:
        logging.debug("There was a common prefix: %s",
                      common_prefix)
        candidate = f"{prefix}_{common_prefix}"
    else:
        candidate = prefix
    if candidate not in currently_used_service_names:
        logging.debug("The candidate `%s` was not yet recorded. Adding as is.")
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
