"""
A thin client for the Cloudera Manager REST API, covering the endpoints needed
to build a CoGuard cluster representation from a running Cloudera deployment.

The endpoint flow implemented here is

    GET /api/{version}/clusters
    GET /api/{version}/clusters/{cluster}/services
    GET /api/{version}/clusters/{cluster}/services/{service}/roles
    GET /api/{version}/clusters/{cluster}/services/{service}/roles/{role}/process
    GET /api/{version}/clusters/{cluster}/services/{service}/roles/{role}/process\
/configFiles/{configFileName}

which retrieves the *generated* configuration files, rather than reconstructing
the effective configuration from the service configuration JSON.

In addition,

    GET /api/{version}/events?query=...&maxResults=...

is available for asking Cloudera Manager what has happened to a cluster, which is
what the scheduled check uses to decide whether a scan is due.
"""

import logging
import re
import urllib.parse
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 4
# Used if `/api/version` cannot be reached. v19 is supported by every Cloudera
# Manager release which offers the process/configFiles resource.
FALLBACK_API_VERSION = "v19"
# The shape of the version string as returned by `/api/version`, which is used
# as a path segment for every subsequent request.
API_VERSION_PATTERN = re.compile(r"^v\d+$")
# Only these are ever valid for a Cloudera Manager instance, and restricting the
# scheme keeps a mistyped or hostile url from turning into a `file://` read.
SUPPORTED_URL_SCHEMES = ("http", "https")
# Path segments which do not address a resource but navigate the path itself.
RELATIVE_PATH_SEGMENTS = frozenset([".", ".."])
# The shape of a query parameter name. Cloudera Manager only ever expects plain
# identifiers here, so anything which could introduce a second parameter or a
# fragment is refused rather than encoded and sent.
QUERY_PARAMETER_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
# The number of events asked of the events resource in one request. It is not
# paged through: whether a cluster has changed follows from the newest events,
# and the resource returns them newest first.
DEFAULT_EVENT_PAGE_SIZE = 50


class ClouderaManagerApiError(Exception):
    """
    Raised when the Cloudera Manager API could not be queried successfully.
    """


def validate_path_segment(segment: str) -> str:
    """
    Validates that a string may be used as a single path segment of an API url,
    and returns it unchanged.

    Cluster, service and role names as well as configuration file names are
    values taken from user input or from a Cloudera Manager response, and they
    end up in the path of the requests issued here. Rejecting empty, relative
    and separator-containing segments means that no such value can navigate out
    of the resource it is supposed to address, regardless of the percent
    encoding applied afterwards.
    """
    if not segment or not segment.strip():
        raise ClouderaManagerApiError(
            "An empty path segment cannot be part of a Cloudera Manager API url."
        )
    if segment in RELATIVE_PATH_SEGMENTS:
        raise ClouderaManagerApiError(
            f"The path segment `{segment}` is a relative path reference and "
            "cannot be part of a Cloudera Manager API url."
        )
    if "/" in segment or "\\" in segment:
        raise ClouderaManagerApiError(
            f"The path segment `{segment}` contains a path separator and cannot "
            "be part of a Cloudera Manager API url."
        )
    return segment


def validate_query_parameter_name(name: str) -> str:
    """
    Validates that a string may be used as the name of a query parameter of an
    API url, and returns it unchanged.
    """
    if not QUERY_PARAMETER_NAME_PATTERN.match(name or ""):
        raise ClouderaManagerApiError(
            f"`{name}` is not a usable query parameter name for a Cloudera "
            "Manager API url."
        )
    return name


def build_url(base_url: str,
              *path_segments: str,
              query_parameters: Optional[Dict[str, object]] = None) -> str:
    """
    Assembles a url from a scheme-and-authority base, the individual path
    segments and the query parameters, each of which is validated and
    percent-encoded.

    The url is composed field by field rather than by string concatenation, and
    the fragment is always empty, so that a value ending up in a path segment can
    neither introduce further path elements nor a query string, and a value
    ending up in the query can neither introduce a further parameter nor a
    fragment.
    """
    split_base = urllib.parse.urlsplit(base_url)
    path = "/" + "/".join(
        urllib.parse.quote(validate_path_segment(segment), safe="")
        for segment in path_segments
    )
    query = urllib.parse.urlencode(
        {
            validate_query_parameter_name(name): str(value)
            for name, value in (query_parameters or {}).items()
            if value is not None
        },
        quote_via=urllib.parse.quote,
        safe=""
    )
    return urllib.parse.urlunsplit(
        (split_base.scheme, split_base.netloc, path, query, "")
    )


class ClouderaManagerApi:
    """
    A minimal, retrying Cloudera Manager API client.
    """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 base_url: str,
                 username: str,
                 password: str,
                 verify_tls: bool = True,
                 ca_cert: Optional[str] = None,
                 timeout: int = DEFAULT_TIMEOUT,
                 retries: int = DEFAULT_RETRIES):
        self._base_url = self._normalize_base_url(base_url)
        self._timeout = timeout
        self._api_version = None
        self._session = requests.Session()
        self._session.auth = (username, password)
        if ca_cert:
            self._session.verify = ca_cert
        else:
            self._session.verify = verify_tls
        if not self._session.verify:
            # The reverse proxy in front of Cloudera Manager frequently uses a
            # self-signed certificate. Suppress the per-request noise, since the
            # user opted into this explicitly.
            # pylint: disable=no-member
            requests.packages.urllib3.disable_warnings()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """
        Accepts `host`, `host:port`, `https://host`, and
        `https://host/api/v58` and reduces all of them to a scheme and
        authority, e.g. `https://host:7183`.
        """
        if not base_url:
            raise ClouderaManagerApiError(
                "No Cloudera Manager URL provided."
            )
        candidate = base_url.strip()
        if "://" not in candidate:
            # Default to https, since Cloudera Manager with AutoTLS and any
            # reverse proxy in front of it will be TLS terminated.
            candidate = f"https://{candidate}"
        parsed = urllib.parse.urlsplit(candidate)
        if parsed.scheme not in SUPPORTED_URL_SCHEMES:
            raise ClouderaManagerApiError(
                f"`{parsed.scheme}` is not a supported scheme for a Cloudera "
                f"Manager url. Supported are {', '.join(SUPPORTED_URL_SCHEMES)}."
            )
        if not parsed.netloc:
            raise ClouderaManagerApiError(
                f"Could not determine the host from `{base_url}`."
            )
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "", "", "")
        )

    def get_api_version(self) -> str:
        """
        Retrieves and caches the newest API version supported by this Cloudera
        Manager instance, as reported by `/api/version`.
        """
        if self._api_version:
            return self._api_version
        try:
            response = self._session.get(
                build_url(self._base_url, "api", "version"),
                timeout=self._timeout
            )
            response.raise_for_status()
            reported = response.text.strip()
        except requests.RequestException as err:
            logging.warning(
                "Could not determine the Cloudera Manager API version (%s). "
                "Falling back to %s.",
                err,
                FALLBACK_API_VERSION
            )
            self._api_version = FALLBACK_API_VERSION
            return self._api_version
        if not API_VERSION_PATTERN.match(reported):
            logging.warning(
                "Unexpected API version `%s` reported. Falling back to %s.",
                reported,
                FALLBACK_API_VERSION
            )
            reported = FALLBACK_API_VERSION
        self._api_version = reported
        logging.debug("Using Cloudera Manager API version %s", self._api_version)
        return self._api_version

    def _api_url(self,
                 *path_segments: str,
                 query_parameters: Optional[Dict[str, object]] = None) -> str:
        """
        Builds a fully qualified API url from the path segments relative to the
        versioned API root.
        """
        return build_url(
            self._base_url,
            "api",
            self.get_api_version(),
            *path_segments,
            query_parameters=query_parameters
        )

    def _get(self,
             *path_segments: str,
             query_parameters: Optional[Dict[str, object]] = None
             ) -> Optional[requests.Response]:
        """
        Performs a GET request against the versioned API, returning `None` if
        the request could not be completed.
        """
        url = self._api_url(*path_segments, query_parameters=query_parameters)
        logging.debug("Requesting %s", url)
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as err:
            logging.debug("Request to %s failed: %s", url, err)
            return None

    def _get_items(self, *path_segments: str) -> List[Dict]:
        """
        Performs a GET request and returns the `items` list of the Cloudera
        Manager response envelope.
        """
        response = self._get(*path_segments)
        if response is None:
            return []
        try:
            return response.json().get("items", []) or []
        except ValueError as err:
            logging.error("Could not decode the response of %s: %s",
                          response.url,
                          err)
            return []

    def check_connection(self) -> bool:
        """
        Verifies that the Cloudera Manager API is reachable and the provided
        credentials are accepted.
        """
        try:
            response = self._session.get(
                self._api_url("tools", "echo"),
                timeout=self._timeout
            )
        except requests.RequestException as err:
            logging.error("Could not reach Cloudera Manager at %s: %s",
                          self._base_url,
                          err)
            return False
        if response.status_code == 401:
            logging.error(
                "Cloudera Manager rejected the provided credentials (HTTP 401)."
            )
            return False
        return response.ok

    def list_clusters(self) -> List[Dict]:
        """
        Returns all clusters managed by this Cloudera Manager instance.
        """
        return self._get_items("clusters")

    def list_services(self, cluster_name: str) -> List[Dict]:
        """
        Returns all services of the given cluster.
        """
        return self._get_items("clusters", cluster_name, "services")

    def list_service_types(self, cluster_name: str) -> List[str]:
        """
        Returns the service types which are available for the given cluster, i.e.
        the types Cloudera Manager has a service descriptor for. This is the
        vocabulary the deployed services draw their type from, and it is used to
        point out types this integration has not been told about yet.
        """
        return [
            service_type for service_type in
            self._get_items("clusters", cluster_name, "serviceTypes")
            if isinstance(service_type, str)
        ]

    def list_roles(self, cluster_name: str, service_name: str) -> List[Dict]:
        """
        Returns all roles of the given service.
        """
        return self._get_items(
            "clusters", cluster_name,
            "services", service_name,
            "roles"
        )

    def get_role_process(self,
                         cluster_name: str,
                         service_name: str,
                         role_name: str) -> Optional[Dict]:
        """
        Returns the process resource of a role, which contains the list of
        generated configuration files under the `configFiles` key. `None` is
        returned if the role has no process yet, which is the case for roles
        which have never been started.
        """
        response = self._get(
            "clusters", cluster_name,
            "services", service_name,
            "roles", role_name,
            "process"
        )
        if response is None:
            return None
        try:
            return response.json()
        except ValueError as err:
            logging.error("Could not decode the process resource of %s: %s",
                          role_name,
                          err)
            return None

    def get_config_file(self,
                        cluster_name: str,
                        service_name: str,
                        role_name: str,
                        config_file_name: str) -> Optional[str]:
        """
        Retrieves the content of a single generated configuration file of a
        role. `None` is returned if the file could not be retrieved.
        """
        # A configuration file name may be multi-level (e.g.
        # `kraft-conf/kraft-configs.properties`), in which case each level is a
        # path segment of its own. The name comes from a Cloudera Manager
        # response, so a name which does not describe a location below the
        # process directory is refused rather than requested.
        try:
            file_name_segments = [
                validate_path_segment(segment)
                for segment in config_file_name.split("/")
            ]
        except ClouderaManagerApiError as err:
            logging.error("Not requesting the configuration file `%s`: %s",
                          config_file_name,
                          err)
            return None
        response = self._get(
            "clusters", cluster_name,
            "services", service_name,
            "roles", role_name,
            "process", "configFiles",
            *file_name_segments
        )
        if response is None:
            return None
        return response.text

    def list_events(self,
                    query: str,
                    max_results: int = DEFAULT_EVENT_PAGE_SIZE
                    ) -> Optional[List[Dict]]:
        """
        Returns the newest events matching an event query, newest first. `None`
        is returned if the events resource could not be queried, which is not the
        same thing as a Cloudera Manager without matching events.

        The query is the filter language of the events resource, e.g.
        `attributes.EVENTCODE==EV_REVISION_CREATED`. It is worth knowing that

        * the resource is not cluster scoped and answers for everything this
          Cloudera Manager knows about, so the cluster an event belongs to has to
          be read off its `CLUSTER` attribute,
        * it is served by the Event Server role, i.e. it is unavailable while that
          role is down, and
        * there is no server side time filter. `timeOccurred` is not a queryable
          attribute, and `from` and `to` parameters are accepted but ignored,
          which is why a caller which wants only the new events has to remember
          where it stopped.
        """
        response = self._get(
            "events",
            query_parameters={"query": query, "maxResults": max_results}
        )
        if response is None:
            return None
        try:
            return response.json().get("items", []) or []
        except ValueError as err:
            logging.error("Could not decode the events matching `%s`: %s",
                          query,
                          err)
            return None


def event_attribute(event: Dict, name: str) -> Optional[str]:
    """
    Reads a single attribute of an event. The attributes of an event are a list
    of name and values pairs, and every attribute this integration is interested
    in carries exactly one value.
    """
    for attribute in event.get("attributes", []) or []:
        if attribute.get("name") == name:
            values = attribute.get("values") or []
            return str(values[0]) if values else None
    return None
