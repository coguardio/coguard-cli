"""
This module contains the class to find Pulumi configurations
inside a folder structure.
"""

import os
import re
import tempfile
import logging
import subprocess
import copy
import json
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderPulumi(ConfigFileFinder):
    """
    The class to find pulumi configuration files within a file system.
    """

    def _extract_desired_resources(self, preview_json: dict) -> dict:
        """
        Extract a simplified mapping of desired Pulumi resources from a Pulumi preview JSON result.

        This processes the preview JSON and collects all resources that are expected to exist after
        the deployment. Only resources with operations indicating they are being created, updated,
        unchanged, or replaced (`create`, `update`, `same`, `replace`) are included.

        Parameters
        ----------
        preview_json : dict
            The parsed JSON output from `pulumi preview --json`. Expected to contain a
            top-level "steps" list where each step describes an operation on a resource.

        Returns
        -------
        dict
            A mapping of resource URNs to a simplified structure containing:
            - "type": The Pulumi resource type (e.g., "aws:s3/bucket:Bucket")
            - "inputs": The resolved input properties for the resource

            Example:
            {
                "urn:pulumi:stack::project::aws:s3/bucket:Bucket::my-bucket": {
                    "type": "aws:s3/bucket:Bucket",
                    "inputs": { ... }
                }
            }

        Notes
        -----
        - Resources that are being deleted are intentionally excluded.
        - If a step does not contain URN or newState data, it is skipped.
        """
        desired = {}

        for step in preview_json.get("steps", []):
            op = step.get("op")
            urn = step.get("urn")
            new = step.get("newState")

            if not urn or not new:
                continue

            if op in ("create", "update", "same", "replace"):
                desired[urn] = {
                    "type": new.get("type"),
                    "inputs": new.get("inputs", {})
                }

        return desired

    def _merge_pulumi_state_helper(self, old_state: dict, desired: dict, deleted_urns: set) -> dict:
        """
        Merge a set of desired Pulumi resources into an existing Pulumi state snapshot.

        This function takes the currently known Pulumi state (typically from `pulumi stack export`)
        and updates it to reflect what should exist after a planned deployment. It ensures that:
        - Resources in `desired` are added or updated.
        - Resources in `deleted_urns` are removed.
        - Providers and the stack resource are preserved correctly.
        - Inputs are replaced with the desired inputs, while outputs are retained from the old
          state.

        Parameters
        ----------
        old_state : dict
            The current Pulumi state, expected to contain a top-level "deployment" key with a
            "resources" list. Each resource entry must include at least:
            - "urn": Unique resource name
            - "type": Pulumi resource type identifier
            - "inputs"/"outputs" optional structures

        desired : dict
            A mapping of URNs to resource specifications, typically produced by examining a
            `pulumi preview` output. Each entry should contain:
            - "type": The Pulumi resource type
            - "inputs": Desired resource input properties

        deleted_urns : set
            A set of URNs that should no longer exist in the resulting state. These URNs will
            be removed from the resource list unless they represent providers or the stack
            (which are always preserved).

        Returns
        -------
        dict
            A new Pulumi state dict with resources updated to match `desired`, removed entries
            filtered by `deleted_urns`, and necessary provider/stack resources retained.

        Notes
        -----
        - This does not validate inputs for runtime correctness. It assumes `desired` entries
          correspond to valid Pulumi resource types.
        - Outputs are intentionally preserved from the old state to avoid destructive refreshes.
        - Newly created entries get empty outputs as placeholders.

        """
        new_state = copy.deepcopy(old_state)
        deployment = new_state.setdefault("deployment", {})
        resources = deployment.setdefault("resources", [])

        old_resources = {r["urn"]: r for r in resources}
        updated_resources = []

        for urn, res in desired.items():
            if urn in old_resources:
                merged = copy.deepcopy(old_resources[urn])
                merged["inputs"] = res.get("inputs", {})
                merged["outputs"] = old_resources[urn].get("outputs", {})
                merged["custom"] = True
                updated_resources.append(merged)
            else:
                updated_resources.append({
                    "urn": urn,
                    "type": res["type"],
                    "custom": True,
                    "inputs": res.get("inputs", {}),
                    "outputs": {}
                })

        # Preserve providers and stack, exclude deleted URNs
        for urn, res in old_resources.items():
            if urn in deleted_urns:
                continue
            if res["type"].startswith("pulumi:providers:") or res["type"] == "pulumi:pulumi:Stack":
                if urn not in [r["urn"] for r in updated_resources]:
                    updated_resources.append(res)

        deployment["resources"] = updated_resources
        return new_state

    def _merge_pulumi_states(self, stack_export_output, preview_output):
        """
        Produce a synthesized Pulumi state representing the desired post-deployment state.

        This function takes:
        - The current exported Pulumi stack state (from `pulumi stack export`)
        - The Pulumi preview output (from `pulumi preview --json`)

        It extracts the set of resources that *should* exist after deployment, identifies
        which resources are scheduled for deletion, and delegates to `_merge_pulumi_state_helper`
        to construct the final merged state.

        Parameters
        ----------
        stack_export_output : dict
            Parsed JSON from `pulumi stack export`. Expected to contain a `deployment.resources`
            list representing the current known state.

        preview_output : dict
            Parsed JSON from `pulumi preview --json`. Used to determine which resources will be
            created, updated, kept, or deleted.

        Returns
        -------
        dict
            A new Pulumi state JSON structure that reflects the desired state after deployment,
            incorporating new/updated resources, removing deleted resources, and preserving
            providers and stack metadata.

        Notes
        -----
        - This does not apply any changes to the real stack. The returned dict is suitable for
          re-importing via `pulumi stack import` or further inspection.
        - Resources marked with operation `"delete"` in the preview output will be removed.
        """
        desired = self._extract_desired_resources(preview_output)

        # Find resources marked for deletion
        deleted_urns = {
            step["urn"]
            for step in preview_output.get("steps", [])
            if step.get("op") == "delete"
        }
        return self._merge_pulumi_state_helper(stack_export_output, desired, deleted_urns)

    def _process_pulumi_project(self, folder_path):
        """
        Inspect and process a Pulumi project located at a given folder path.

        This function attempts to:
        1. Detect whether the folder contains a Pulumi project (implicitly via the Pulumi CLI).
        2. Ensure at least one stack exists (initializing a default "dev" stack
           if none are present).
        3. Export the current Pulumi stack state.
        4. Run a Pulumi preview to determine the desired resource state.
        5. Merge the preview results with the existing state to produce a synthesized,
           post-deployment state representation.

        Pulumi CLI commands are invoked if available. If the Pulumi CLI is not installed, or
        if any step fails (including invalid JSON output), the function returns `None` gracefully
        without raising exceptions.

        Parameters
        ----------
        folder_path : str
            Path to the directory that may contain a Pulumi project. Expected to be a directory
            where `pulumi stack ...` and `pulumi preview` can be executed.

        Returns
        -------
        dict or None
            A merged Pulumi state representation that reflects the desired state after deployment,
            suitable for inspection or use with `pulumi stack import`.

            Returns `None` if:
            - The Pulumi CLI is not available
            - The folder is not a Pulumi project
            - No export/preview output can be obtained
            - Output JSON cannot be parsed

        Notes
        -----
        - The function does not modify the real stack on disk. It constructs an in-memory
          representation based on CLI output.
        - When initializing a default stack, the secrets provider is set to plaintext.
          This is intentional for offline/state synthesis workflows.
        """
        def run_cmd(cmd, env_extra=None):
            env = os.environ.copy()
            if env_extra:
                env.update(env_extra)
            try:
                result = subprocess.run(
                    cmd,
                    cwd=folder_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                return result.stdout
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Pulumi CLI not installed
                return None
        env_pp = {}
        try:
            stack_list_raw = run_cmd(["pulumi", "stack", "ls", "--json"])
            if stack_list_raw is None:
                return None
            existing_stacks = json.loads(stack_list_raw)
        # pylint: disable=broad-exception-caught
        except Exception:
            existing_stacks = []

        # If no stacks present, initialize default "dev" stack
        if not existing_stacks:
            env_pp = {"PULUMI_CONFIG_PASSPHRASE": ""}
            if run_cmd(
                [
                    "pulumi",
                    "stack",
                    "init",
                    "dev",
                    "--non-interactive",
                    "--secrets-provider=plaintext"]
            ) is None:
                logging.error("Could not init stack in Pulumi project (maybe pulumi "
                              "CLI not installed?)")
                return None

        # only if the user hasn't set it
        if "PULUMI_CONFIG_PASSPHRASE" not in os.environ:
            env_pp["PULUMI_CONFIG_PASSPHRASE"] = ""

        stack_export_raw = run_cmd(["pulumi", "stack", "export"], env_extra=env_pp)
        if stack_export_raw is None:
            return None

        preview_raw = run_cmd(
            ["pulumi", "preview", "--non-interactive", "--json"],
            env_extra=env_pp
        )
        if preview_raw is None:
            return None

        try:
            stack_export_output = json.loads(stack_export_raw)
            preview_output = json.loads(preview_raw)
        except json.JSONDecodeError:
            return None

        merged = self._merge_pulumi_states(stack_export_output, preview_output)
        return merged

    def _create_temp_location_and_manifest_entry(
            self,
            path_to_file_system: str,
            pulumi_file: str) -> Optional[Tuple[Dict, str]]:
        """
        Helper function to create a temp location and CoGuard manifest entry.
        """
        logging.debug("The path to the filesystem is: %s",
                      path_to_file_system)
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-pulumi")
        pulumi_export_file_content = self._process_pulumi_project(
            os.path.dirname(pulumi_file)
        )
        if not pulumi_export_file_content:
            logging.error("Failed to extract pulumi template.")
            return None
        logging.debug("The content to write: %s", pulumi_export_file_content)
        logging.debug("The pulumi file before the replace is %s.",
                      pulumi_file)
        # The reason we added os.sep at the end is because the file location may be
        # at the root of the path_to_file_system. In this case, if there is a separation
        # character at the end of path_to_file_system, the replace may not work.
        # That is why we just add it here.
        loc_within_machine = "."
        logging.debug("The location within the folder is: %s",
                      loc_within_machine)
        file_name = "ExportedPulumiStack.json"
        os.makedirs(os.path.join(temp_location, loc_within_machine), exist_ok=True)
        with open(
                os.path.join(temp_location, loc_within_machine, file_name),
                'w',
                encoding='utf-8'
        ) as pulumi_file_stream:
            json.dump(pulumi_export_file_content, pulumi_file_stream)
        manifest_entry = {
            "version": "1.0",
            "serviceName": self.get_service_name(),
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": "main.json",
                    "subPath": f"./{loc_within_machine}",
                    "configFileType": "json"
                }
            ],
            "complimentaryFileList": []
        }
        return(
            manifest_entry,
            temp_location
        )

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Pulumi files. Returning nothing.
        """
        return None

    def _find_charts_files(self, path_to_file_system: str) -> List[str]:
        """
        Helper function to find Pulumi charts.
        """
        standard_names = ["^Pulumi\\.ya?ml$"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                if matching_file_names:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in matching_file_names
                    ]
                    logging.debug("Found entries: %s",
                                  mapped_file_names)
                    result_files.extend(mapped_file_names)
        return result_files

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        pulumi_chart_files = self._find_charts_files(path_to_file_system)
        for pulumi_chart_file in pulumi_chart_files:
            new_entry_candidate = self._create_temp_location_and_manifest_entry(
                path_to_file_system,
                pulumi_chart_file
            )
            if new_entry_candidate:
                print(
                    f"{COLOR_CYAN}Found file "
                    f"{pulumi_chart_file.replace(path_to_file_system, '')}"
                    f"{COLOR_TERMINATION}"
                )
                result_files.append(new_entry_candidate)
        return result_files

    def check_call_command_in_container(
            self,
            path_to_file_system: str,
            docker_config: Dict
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'pulumi'

    def is_cluster_service(self):
        return True

ConfigFileFinder.register(ConfigFileFinderPulumi)
