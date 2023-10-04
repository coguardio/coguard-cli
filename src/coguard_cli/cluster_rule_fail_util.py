"""
This module contains functions to figure out if some cluster rules have failed and if these
need to be communicated to the back-end.
"""

import os
from typing import List

def is_ci_cd_there(
        folder_name: str,
        additional_failed_rules: List[str]
) -> bool:
    """
    We are checking for typical filenames for CI/CD pipelines. If none is found,
    additional_failed_rules will have `cluster_no_ci_cd_tool_used` added.
    """
    # is there a github workflow?
    if os.path.exists(os.path.join(folder_name, ".github", "workflows")):
        return True
    # is there a Jenkinsfile?
    for _, _, filenames in os.walk(folder_name):
        for filename in filenames:
            if "jenkinsfile" in filename.lower():
                return True
    # Is there a bitbucket pipeline? Heuristic method
    for _, _, filenames in os.walk(folder_name):
        for filename in filenames:
            if "pipe" in filename.lower() and filename.endswith("yml"):
                return True
    # Is there a gitlab pipeline
    for _, _, filenames in os.walk(folder_name):
        for filename in filenames:
            if filename == ".gitlab-ci.yml":
                return True
    # Is there a circle-ci pipeline
    if os.path.exists(os.path.join(folder_name, ".circleci")):
        return True
    additional_failed_rules.append("cluster_no_ci_cd_tool_used")
    return False
