"""
This module extracts a CoGuard cluster representation from a running Cloudera
deployment, by querying the Cloudera Manager API.

Cloudera's model of a cluster containing services which in turn contain roles
maps almost directly onto CoGuard's model of a cluster containing services. Each
(Cloudera service, Cloudera role type) pair becomes one CoGuard cluster service,
and the *generated* configuration files of a representative role instance of
that type become its configuration file list.
"""

import json
import logging
import os
import pathlib
import tempfile
from typing import Dict, List, Optional, Tuple

from coguard_cli.check_common_util import replace_special_chars_with_underscore
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError
from coguard_cli.discovery.cloudera_discovery.cloudera_service_mapping import \
    config_file_type, coguard_service_name, create_cluster_service_identifier, \
    unreviewed_service_types
from coguard_cli.print_colors import COLOR_CYAN, COLOR_YELLOW, COLOR_TERMINATION
from coguard_cli.util import convert_string_to_posix_path

# The state a role is in when it is running, and hence the state in which its
# generated configuration is the one currently in effect.
RUNNING_ROLE_STATE = "STARTED"


def determine_cluster_name(api: ClouderaManagerApi,
                           requested_cluster_name: Optional[str] = None
                           ) -> Optional[str]:
    """
    Determines which cluster to extract. If a cluster name was requested, it is
    validated against the clusters known to Cloudera Manager. Otherwise, the
    single existing cluster is used, and `None` is returned if the choice is
    ambiguous.
    """
    clusters = api.list_clusters()
    cluster_names = [
        cluster.get("name") for cluster in clusters if cluster.get("name")
    ]
    if not cluster_names:
        logging.error(
            "Cloudera Manager did not report any cluster. Please check the "
            "credentials and the permissions of the user being used."
        )
        return None
    if requested_cluster_name:
        if requested_cluster_name not in cluster_names:
            logging.error(
                "The cluster `%s` is not managed by this Cloudera Manager. "
                "Available clusters: %s",
                requested_cluster_name,
                ", ".join(cluster_names)
            )
            return None
        return requested_cluster_name
    if len(cluster_names) > 1:
        logging.error(
            "This Cloudera Manager instance manages multiple clusters. Please "
            "specify the one to scan using `--cloudera-cluster`. Available "
            "clusters: %s",
            ", ".join(cluster_names)
        )
        return None
    return cluster_names[0]


def group_roles_by_type(roles: List[Dict]) -> Dict[str, Dict]:
    """
    Groups the roles of a service by their role type and picks one
    representative role instance per type.

    A role which is currently running is preferred, since its generated
    configuration is the one in effect. Among equal candidates, the
    lexicographically smallest role name is chosen, so that repeated runs of
    the CLI produce a stable result.
    """
    representatives = {}
    for role in sorted(roles, key=lambda entry: entry.get("name") or ""):
        role_type = role.get("type")
        if not role_type:
            continue
        incumbent = representatives.get(role_type)
        if incumbent is None:
            representatives[role_type] = role
            continue
        if incumbent.get("roleState") != RUNNING_ROLE_STATE and \
           role.get("roleState") == RUNNING_ROLE_STATE:
            representatives[role_type] = role
    return representatives


def resolve_inside_destination(destination: str,
                               config_file_name: str) -> Optional[pathlib.Path]:
    """
    Resolves the name of a generated configuration file, as reported by Cloudera
    Manager, to the path it is to be stored under inside `destination`, and
    returns `None` if that path would not end up below `destination`.

    The names come from an API response and are used to build file system paths,
    so a name such as `../../../../etc/crontab` or `/etc/crontab` must not be
    written where it says.
    """
    destination_root = pathlib.Path(destination).resolve()
    candidate = destination_root.joinpath(config_file_name).resolve()
    if destination_root not in candidate.parents:
        return None
    return candidate


def collect_config_files_for_role(
        api: ClouderaManagerApi,
        cluster_name: str,
        service_name: str,
        role: Dict,
        destination: str) -> List[Dict]:
    """
    Retrieves all generated configuration files of a role which CoGuard is able
    to consume, stores them inside `destination`, and returns the resulting
    `configFileList` entries for the manifest.
    """
    role_name = role.get("name")
    process = api.get_role_process(cluster_name, service_name, role_name)
    if not process:
        logging.info(
            "No process information available for role %s. It has most likely "
            "never been started, and hence has no generated configuration.",
            role_name
        )
        return []
    config_file_names = process.get("configFiles", []) or []
    logging.debug("Role %s reported %s configuration files.",
                  role_name,
                  len(config_file_names))
    config_file_list = []
    for config_file_name in sorted(config_file_names):
        file_type = config_file_type(config_file_name)
        if file_type is None:
            continue
        target_file = resolve_inside_destination(destination, config_file_name)
        if target_file is None:
            logging.warning(
                "Skipping the configuration file `%s` of role %s: the name does "
                "not describe a location inside the extraction folder.",
                config_file_name,
                role_name
            )
            continue
        content = api.get_config_file(
            cluster_name,
            service_name,
            role_name,
            config_file_name
        )
        if content is None:
            logging.warning("Could not retrieve %s of role %s.",
                            config_file_name,
                            role_name)
            continue
        relative_path = pathlib.PurePosixPath(config_file_name)
        sub_path = str(relative_path.parent)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding='utf-8')
        config_file_list.append({
            "fileName": relative_path.name,
            "defaultFileName": relative_path.name,
            "subPath": f"./{convert_string_to_posix_path(sub_path)}"
                       if sub_path != "." else ".",
            "configFileType": file_type
        })
    return config_file_list


# pylint: disable=too-many-locals
def report_unreviewed_service_types(api: ClouderaManagerApi,
                                    cluster_name: str) -> List[str]:
    """
    Asks Cloudera Manager which service types exist for the cluster, and reports
    the ones this integration does not know about. The types are returned for the
    benefit of the tests.

    This is a diagnostic step rather than a part of the extraction: the mapping
    from a Cloudera service type to a CoGuard service name is only ever as
    complete as the release of Cloudera it was written against, and this is what
    turns a type it has never seen into a visible message instead of a silent
    assumption. Failure to determine the vocabulary is not treated as an error,
    since none of the extraction depends on it.
    """
    try:
        unreviewed = unreviewed_service_types(
            api.list_service_types(cluster_name)
        )
    except (ClouderaManagerApiError, TypeError, AttributeError) as exception:
        logging.debug(
            "Could not determine the service types of the cluster %s: %s",
            cluster_name,
            exception
        )
        return []
    if unreviewed:
        print(
            f"{COLOR_YELLOW}Cloudera Manager offers service types which this "
            f"version of CoGuard has not been told about: "
            f"{', '.join(unreviewed)}. Services of these types are reported "
            f"under their Cloudera type name.{COLOR_TERMINATION}"
        )
    return unreviewed


def extract_cloudera_cluster_representation(
        api: ClouderaManagerApi,
        customer_id: str,
        requested_cluster_name: Optional[str] = None
) -> Optional[Tuple[str, Dict]]:
    """
    Builds a CoGuard infrastructure description of a Cloudera cluster by
    querying the Cloudera Manager API, and returns a tuple of the folder it was
    written to and the manifest dictionary. `None` is returned if nothing could
    be extracted.

    Keep in mind that whoever is calling this function is in charge of deleting
    the generated folder afterwards.
    """
    cluster_name = determine_cluster_name(api, requested_cluster_name)
    if not cluster_name:
        return None
    services = api.list_services(cluster_name)
    if not services:
        logging.error("No services found in the cluster %s.", cluster_name)
        return None
    print(f"{COLOR_CYAN}Found {len(services)} services in cluster "
          f"{COLOR_TERMINATION}{cluster_name}")
    report_unreviewed_service_types(api, cluster_name)
    final_location = tempfile.mkdtemp(prefix="coguard-cli-cloudera")
    manifest_blueprint = {
        "name": replace_special_chars_with_underscore(cluster_name),
        "customerId": customer_id,
        "clusterServices": {}
    }
    cluster_services = manifest_blueprint["clusterServices"]
    for service in sorted(services, key=lambda entry: entry.get("name") or ""):
        service_name = service.get("name")
        service_type = service.get("type")
        if not service_name or not service_type:
            continue
        roles = api.list_roles(cluster_name, service_name)
        if not roles:
            logging.info("Service %s has no roles. Skipping.", service_name)
            continue
        for role_type, role in sorted(group_roles_by_type(roles).items()):
            identifier = create_cluster_service_identifier(service_name, role_type)
            while identifier in cluster_services:
                identifier = f"{identifier}_0"
            service_folder = os.path.join(
                final_location,
                "clusterServices",
                identifier
            )
            os.makedirs(service_folder, exist_ok=True)
            config_file_list = collect_config_files_for_role(
                api,
                cluster_name,
                service_name,
                role,
                service_folder
            )
            if not config_file_list:
                logging.info(
                    "No consumable configuration files found for %s. Skipping.",
                    identifier
                )
                os.rmdir(service_folder)
                continue
            print(f"{COLOR_CYAN} Extracted {len(config_file_list)} "
                  f"configuration files for{COLOR_TERMINATION} {identifier}")
            cluster_services[identifier] = {
                "version": "1.0",
                "serviceName": coguard_service_name(service_type),
                "configFileList": config_file_list,
                "complimentaryFileList": []
            }
    if not cluster_services:
        print(f"{COLOR_YELLOW}No configuration files could be extracted from "
              f"the cluster {cluster_name}.{COLOR_TERMINATION}")
        return None
    with open(os.path.join(final_location, "manifest.json"), "w",
              encoding='utf-8') as manifest_file:
        json.dump(manifest_blueprint, manifest_file)
    return (final_location, manifest_blueprint)
