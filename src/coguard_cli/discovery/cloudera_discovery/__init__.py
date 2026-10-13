"""
This module extracts a CoGuard cluster representation from a running Cloudera
deployment, by querying the Cloudera Manager API.

Cloudera's model of a cluster containing services which in turn contain roles
maps almost directly onto CoGuard's model of a cluster containing services. Each
(Cloudera service, Cloudera role type) pair becomes one CoGuard cluster service,
and the *generated* configuration files of a representative role instance of
that type become its configuration file list. The files in there which configure
a different piece of software -- the `ozone-site.xml` an HBase master is handed,
for instance -- are split off into a cluster service of that software of their
own, so that they are scanned with the rules which apply to them.
"""

import json
import logging
import os
import pathlib
import posixpath
import re
import tempfile
from typing import Dict, List, Optional, Tuple

import yaml

from coguard_cli.check_common_util import replace_special_chars_with_underscore
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError
from coguard_cli.discovery.cloudera_discovery.cloudera_templates import \
    TemplateContext, neutralize_placeholders, render_template
from coguard_cli.discovery.cloudera_discovery.cloudera_service_mapping import \
    config_file_type, coguard_service_name, create_cluster_service_identifier, \
    owning_software, unreviewed_service_types
from coguard_cli.print_colors import COLOR_CYAN, COLOR_YELLOW, COLOR_TERMINATION
from coguard_cli.util import convert_string_to_posix_path

# The state a role is in when it is running, and hence the state in which its
# generated configuration is the one currently in effect.
RUNNING_ROLE_STATE = "STARTED"

# The state of a role which does not run a process by design: a gateway, which
# only holds the client configuration of a host, or the HDFS balancer, which
# runs as a command when it is asked to.
NO_PROCESS_ROLE_STATE = "NA"

# The states of a role which runs as a daemon, but is not running. A role in a
# transitional state (`STARTING`, `STOPPING`, `BUSY`) is not counted, and
# neither is one whose state Cloudera Manager does not know the history of.
NOT_RUNNING_ROLE_STATES = ("STOPPED", "UNKNOWN")

# The cluster rule of the CoGuard back-end which reports those roles, and the
# file in the root of the upload through which the CLI reports cluster rules.
ROLES_NOT_RUNNING_RULE = "cluster_cloudera_roles_not_running"
FAILED_RULES_FILE_NAME = "failed_rules.json"

# The two forms of placeholder Cloudera leaves in the files it hands out.
#
#     scrape_interval: {{SCRAPE_INTERVAL}}
#     PROXYUSER_BLOCK,
#     "PROXYUSER_BLOCK",
#
# The second form is a token standing in for a whole block, on a line of its own,
# quoted or not — Knox writes it both ways in the same folder. It has to contain
# an underscore, or be followed by a comma, so that a lone word in a file of a
# free-form type is not mistaken for one. A loose match is affordable here because
# a placeholder only ever matters for a file which does not parse anyway; see
# `unreadable_template`.
MUSTACHE_PLACEHOLDER = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
BARE_PLACEHOLDER = re.compile(
    r'^[ \t]*"?([A-Z][A-Z0-9_]{2,})"?[ \t]*(,?)[ \t]*$',
    re.MULTILINE
)

# The configuration file types for which a placeholder can destroy the syntax of
# the file, together with what it takes to read one. Everything else — a
# properties file, an XML value, a free-form `.conf` — takes a placeholder in its
# stride, which is exactly why the presence of a placeholder is not by itself a
# reason to skip anything.
PLACEHOLDER_BREAKABLE_TYPES = {
    "json": json.loads,
    "yaml": yaml.safe_load,
}


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


def unresolved_placeholder(content: str) -> Optional[str]:
    """
    Returns the first unresolved placeholder found in the content of a file, and
    `None` if there is none.
    """
    mustache = MUSTACHE_PLACEHOLDER.search(content)
    if mustache:
        return mustache.group(0)
    for token, comma in BARE_PLACEHOLDER.findall(content):
        if "_" in token or comma:
            return token
    return None


def unreadable_template(content: str, file_type: str) -> Optional[str]:
    """
    Returns the placeholder which makes a file unreadable, and `None` if the file
    is readable or has no placeholder in it.

    A placeholder alone means nothing. Cloudera leaves `{{CMF_CONF_DIR}}` inside
    the *values* of files which are as deployed as it gets — `hdfs-site.xml`,
    `ozone-site.xml`, `kafka.properties`, 148 of the 532 files of one live
    cluster — and the agent expands it when it starts the process. Those files are
    the point of this integration and all of their other parameters are real.

    What is worth skipping is the handful of files where the placeholder sits in a
    structural position and takes the syntax of the file with it: the Prometheus
    files of the Ozone roles, whose `{{SCRAPE_INTERVAL}}` in value position is not
    YAML, and the shared providers and descriptors of Knox, whose bare
    `PROXYUSER_BLOCK,` is not JSON. Those are the input of a templating step
    rather than a configuration any process reads, and no rule can evaluate them
    anyway — all they produce is a parse error against a service whose real
    configuration was fine.

    Both conditions are required, so that a deployed file which is malformed for
    some *other* reason is still uploaded and still reported. A parse error about
    a file which was really deployed is a finding; one about a template is noise.
    """
    placeholder = unresolved_placeholder(content)
    if placeholder is None:
        return None
    parse = PLACEHOLDER_BREAKABLE_TYPES.get(file_type)
    if parse is None:
        return None
    try:
        parse(content)
    except (ValueError, yaml.YAMLError):
        return placeholder
    return None


def readable_content(content: str,
                     file_type: str,
                     config_file_name: str,
                     role_name: str) -> Optional[str]:
    """
    Returns the content of a file in a form its syntax accepts, and `None` if
    there is none.

    A file whose placeholders break its syntax, which a renderer of
    `cloudera_templates` did not take care of, has its placeholders neutralized:
    a block placeholder is removed and an inline one is quoted. Only if the file
    is still unreadable after that is it skipped, since a parse error about a
    template is noise rather than a finding.
    """
    placeholder = unreadable_template(content, file_type)
    if placeholder is None:
        return content
    neutralized = neutralize_placeholders(content, file_type)
    remaining_placeholder = unreadable_template(neutralized, file_type)
    if remaining_placeholder is None:
        logging.info(
            "The placeholder `%s` of %s of role %s has no value Cloudera Manager "
            "exposes, and was replaced by a neutral one to keep the file "
            "readable as %s.",
            placeholder,
            config_file_name,
            role_name,
            file_type
        )
        return neutralized
    logging.info(
        "Skipping %s of role %s: the unresolved placeholder `%s` leaves it "
        "unreadable as %s, even with neutral values in place of the "
        "placeholders.",
        config_file_name,
        role_name,
        remaining_placeholder,
        file_type
    )
    return None


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def collect_config_files_for_role(
        api: ClouderaManagerApi,
        cluster_name: str,
        service_name: str,
        role: Dict,
        destination: str,
        cloudera_service_type: str = "") -> List[Dict]:
    """
    Retrieves all generated configuration files of a role which CoGuard is able
    to consume, stores them inside `destination`, and returns the resulting
    `configFileList` entries for the manifest.

    All files are retrieved before any is rendered, since a template may draw
    on another file of the role -- the Ozone Prometheus configuration in `aux/`
    on the peer files in `ozone-conf/`, which sort after it.
    """
    role_name = role.get("name")
    process = api.get_role_process(cluster_name, service_name, role_name)
    if not process:
        if role.get("roleState") == NO_PROCESS_ROLE_STATE:
            logging.debug(
                "Role %s does not run a process, and hence has no generated "
                "configuration of its own.",
                role_name
            )
        else:
            logging.info(
                "No process information available for role %s. It has most "
                "likely never been started, and hence has no generated "
                "configuration.",
                role_name
            )
        return []
    config_file_names = process.get("configFiles", []) or []
    logging.debug("Role %s reported %s configuration files.",
                  role_name,
                  len(config_file_names))
    retrieved_files: Dict[str, Tuple[str, pathlib.Path, str]] = {}
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
        retrieved_files[config_file_name] = (file_type, target_file, content)
    context = TemplateContext(
        api,
        cluster_name,
        service_name,
        role,
        {name: content for name, (_, _, content) in retrieved_files.items()}
    )
    config_file_list = []
    for config_file_name, (file_type, target_file, content) in \
            retrieved_files.items():
        content = readable_content(
            render_template(cloudera_service_type,
                            config_file_name,
                            content,
                            context),
            file_type,
            config_file_name,
            role_name
        )
        if content is None:
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


def unique_identifier(base_identifier: str,
                      cluster_services: Dict[str, Dict]) -> str:
    """
    Returns `base_identifier`, or, if a cluster service of that name exists
    already, the first of `base_identifier_0`, `base_identifier_1`, ... which
    does not.
    """
    identifier = base_identifier
    duplicate_index = 0
    while identifier in cluster_services:
        identifier = f"{base_identifier}_{duplicate_index}"
        duplicate_index += 1
    return identifier


def split_by_owning_software(config_file_list: List[Dict],
                             role_software: str) -> Dict[str, List[Dict]]:
    """
    Groups the `configFileList` entries of a role by the software they configure.
    Files which do not identify any software belong to the role itself, and are
    listed under `role_software`, which always comes first if present.

    Cloudera hands a role the client configuration of every service it talks to,
    so an HBase master carries an `ozone-site.xml`, and an Atlas server carries
    the `hbase-site.xml` of the HBase it stores its data in. Left in the cluster
    service of the role, those files would only ever be looked at with the rules
    of the role's software.
    """
    result = {role_software: []}
    for entry in config_file_list:
        software = owning_software(entry["fileName"]) or role_software
        result.setdefault(software, []).append(entry)
    if not result[role_software]:
        del result[role_software]
    return result


def relocate_config_files(config_file_list: List[Dict],
                          source_folder: str,
                          destination_folder: str) -> List[Dict]:
    """
    Moves the files of the given `configFileList` entries from the folder of one
    cluster service to the one of another, keeping their sub paths, removes the
    directories left empty behind, and returns the entries which were moved.

    The sub paths and file names are those Cloudera Manager reported, so both
    ends are resolved inside their folder once more, rather than relying on the
    check the files passed when they were written.
    """
    relocated = []
    for entry in config_file_list:
        relative_path = posixpath.join(entry["subPath"], entry["fileName"])
        source = resolve_inside_destination(source_folder, relative_path)
        destination = resolve_inside_destination(destination_folder,
                                                 relative_path)
        if source is None or destination is None:
            logging.warning(
                "Not moving `%s`: it does not describe a location inside the "
                "extraction folder.",
                relative_path
            )
            continue
        os.renames(source, destination)
        relocated.append(entry)
    return relocated


def roles_not_running(roles: List[Dict]) -> List[str]:
    """
    Returns the names of the roles which run as a daemon, but are not running.

    Every instance counts, not only the one chosen to represent its role type:
    one stopped DataNode out of four still has its configuration out of sight,
    and the cluster below the redundancy it was planned with.
    """
    return sorted(
        role.get("name") for role in roles
        if role.get("name") and role.get("roleState") in NOT_RUNNING_ROLE_STATES
    )


def report_roles_not_running(final_location: str,
                             not_running: List[str]) -> None:
    """
    Points out the roles which are not running, and reports the cluster rule
    for them through the `failed_rules.json` in the root of the extraction, which
    becomes the root of the upload. The rule itself can only carry a fixed text,
    which is why the roles are listed here.
    """
    if not not_running:
        return
    print(f"{COLOR_YELLOW}The following roles are not running, so their "
          f"configuration as deployed could not be verified:{COLOR_TERMINATION}")
    for role_name in not_running:
        print(f"{COLOR_YELLOW} - {role_name}{COLOR_TERMINATION}")
    with open(os.path.join(final_location, FAILED_RULES_FILE_NAME), "w",
              encoding='utf-8') as failed_rules_file:
        json.dump([ROLES_NOT_RUNNING_RULE], failed_rules_file)


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


# pylint: disable=too-many-branches
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
    not_running = []
    for service in sorted(services, key=lambda entry: entry.get("name") or ""):
        service_name = service.get("name")
        service_type = service.get("type")
        if not service_name or not service_type:
            continue
        roles = api.list_roles(cluster_name, service_name)
        if not roles:
            logging.info("Service %s has no roles. Skipping.", service_name)
            continue
        not_running.extend(roles_not_running(roles))
        for role_type, role in sorted(group_roles_by_type(roles).items()):
            identifier = unique_identifier(
                create_cluster_service_identifier(service_name, role_type),
                cluster_services
            )
            service_folder = resolve_inside_destination(
                os.path.join(final_location, "clusterServices"),
                identifier
            )
            if service_folder is None:
                logging.warning("Skipping %s: not a valid folder name.",
                                identifier)
                continue
            os.makedirs(service_folder, exist_ok=True)
            config_file_list = collect_config_files_for_role(
                api,
                cluster_name,
                service_name,
                role,
                service_folder,
                service_type
            )
            if not config_file_list:
                # A role which does not run a process has nothing to report.
                log = logging.debug \
                    if role.get("roleState") == NO_PROCESS_ROLE_STATE \
                    else logging.info
                log("No consumable configuration files found for %s. Skipping.",
                    identifier)
                os.rmdir(service_folder)
                continue
            role_software = coguard_service_name(service_type)
            files_by_software = split_by_owning_software(config_file_list,
                                                         role_software)
            for software, software_file_list in files_by_software.items():
                if software == role_software:
                    software_identifier = identifier
                else:
                    software_identifier = unique_identifier(
                        f"{identifier}_{software}",
                        cluster_services
                    )
                    software_file_list = relocate_config_files(
                        software_file_list,
                        service_folder,
                        os.path.join(final_location,
                                     "clusterServices",
                                     software_identifier)
                    )
                    if not software_file_list:
                        continue
                print(f"{COLOR_CYAN} Extracted {len(software_file_list)} "
                      f"configuration files for{COLOR_TERMINATION} "
                      f"{software_identifier}")
                cluster_services[software_identifier] = {
                    "version": "1.0",
                    "serviceName": software,
                    "configFileList": software_file_list,
                    "complimentaryFileList": []
                }
    if not cluster_services:
        print(f"{COLOR_YELLOW}No configuration files could be extracted from "
              f"the cluster {cluster_name}.{COLOR_TERMINATION}")
        return None
    report_roles_not_running(final_location, not_running)
    with open(os.path.join(final_location, "manifest.json"), "w",
              encoding='utf-8') as manifest_file:
        json.dump(manifest_blueprint, manifest_file)
    return (final_location, manifest_blueprint)
