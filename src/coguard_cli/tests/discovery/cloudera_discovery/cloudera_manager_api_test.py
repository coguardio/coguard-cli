"""
Tests for the ClouderaManagerApi class
"""

import unittest
import unittest.mock
import requests
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError, DEFAULT_EVENT_PAGE_SIZE, \
    FALLBACK_API_VERSION, build_url, event_attribute, validate_path_segment, \
    validate_query_parameter_name

def _create_api(**kwargs) -> ClouderaManagerApi:
    """
    Helper to create an api object with a mocked out session.
    """
    api = ClouderaManagerApi(
        base_url=kwargs.get("base_url", "https://cm.example.com"),
        username="admin",
        password="admin",
        verify_tls=kwargs.get("verify_tls", True),
        ca_cert=kwargs.get("ca_cert")
    )
    api._session = unittest.mock.MagicMock()
    api._api_version = kwargs.get("api_version", "v58")
    return api

def _create_response(status_code=200, json_value=None, text=""):
    """
    Helper producing a mocked requests response object.
    """
    response = unittest.mock.MagicMock()
    response.status_code = status_code
    response.ok = status_code < 400
    response.text = text
    if json_value is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = json_value
    return response

class TestClouderaManagerApi(unittest.TestCase):
    """
    The class for testing the Cloudera Manager api client
    """

    def test_normalize_base_url_variants(self):
        """
        Host, host with port and full urls are all reduced to scheme+authority.
        """
        # pylint: disable=protected-access
        normalize = ClouderaManagerApi._normalize_base_url
        self.assertEqual(normalize("cm.example.com"), "https://cm.example.com")
        self.assertEqual(normalize("cm.example.com:7183"),
                         "https://cm.example.com:7183")
        self.assertEqual(normalize("http://cm.example.com:7180"),
                         "http://cm.example.com:7180")
        self.assertEqual(normalize("https://cm.example.com/api/v58"),
                         "https://cm.example.com")
        self.assertEqual(normalize("https://cm.example.com/"),
                         "https://cm.example.com")

    def test_normalize_base_url_empty(self):
        """
        An empty url raises the dedicated exception.
        """
        with self.assertRaises(ClouderaManagerApiError):
            # pylint: disable=protected-access
            ClouderaManagerApi._normalize_base_url("")

    def test_normalize_base_url_invalid(self):
        """
        Urls without a host, and urls with a scheme which cannot address a
        Cloudera Manager instance, are refused.
        """
        for url in ["https://", "//cm.example.com", "file:///etc/passwd",
                    "ftp://cm.example.com"]:
            with self.assertRaises(ClouderaManagerApiError):
                # pylint: disable=protected-access
                ClouderaManagerApi._normalize_base_url(url)

    def test_validate_path_segment(self):
        """
        Valid segments are returned unchanged, and segments which are empty,
        relative or contain a separator are refused.
        """
        self.assertEqual(validate_path_segment("kafka-1"), "kafka-1")
        self.assertEqual(validate_path_segment("my cluster"), "my cluster")
        for segment in ["", "   ", ".", "..", "a/b", "a\\b", "/etc/passwd"]:
            with self.assertRaises(ClouderaManagerApiError):
                validate_path_segment(segment)

    def test_constructor_with_ca_cert(self):
        """
        A provided CA certificate is used as the verification setting.
        """
        api = ClouderaManagerApi(
            "https://cm.example.com", "admin", "admin", ca_cert="/tmp/ca.pem"
        )
        # pylint: disable=protected-access
        self.assertEqual(api._session.verify, "/tmp/ca.pem")

    def test_constructor_without_tls_verification(self):
        """
        Disabling TLS verification is reflected on the session.
        """
        api = ClouderaManagerApi(
            "https://cm.example.com", "admin", "admin", verify_tls=False
        )
        # pylint: disable=protected-access
        self.assertFalse(api._session.verify)

    def test_get_api_version(self):
        """
        The version reported by the api is used and cached.
        """
        api = _create_api(api_version=None)
        api._session.get.return_value = _create_response(text="v58\n")
        self.assertEqual(api.get_api_version(), "v58")
        # The second call must be served from the cache.
        self.assertEqual(api.get_api_version(), "v58")
        self.assertEqual(api._session.get.call_count, 1)

    def test_get_api_version_request_failure(self):
        """
        A failing version request results in the fallback version.
        """
        api = _create_api(api_version=None)
        api._session.get.side_effect = requests.RequestException("boom")
        self.assertEqual(api.get_api_version(), FALLBACK_API_VERSION)

    def test_get_api_version_unexpected_value(self):
        """
        A response which is not a version string results in the fallback.
        """
        api = _create_api(api_version=None)
        api._session.get.return_value = _create_response(text="Not Found")
        self.assertEqual(api.get_api_version(), FALLBACK_API_VERSION)

    def test_api_url(self):
        """
        The versioned api url is assembled from the individual path segments.
        """
        api = _create_api()
        # pylint: disable=protected-access
        self.assertEqual(
            api._api_url("clusters"),
            "https://cm.example.com/api/v58/clusters"
        )
        self.assertEqual(
            api._api_url("clusters", "my cluster", "services"),
            "https://cm.example.com/api/v58/clusters/my%20cluster/services"
        )

    def test_api_url_rejects_traversal_segments(self):
        """
        A path segment which navigates the path instead of addressing a
        resource is refused.
        """
        api = _create_api()
        for segment in ["..", ".", "", "clusters/other", "back\\slash"]:
            with self.assertRaises(ClouderaManagerApiError):
                # pylint: disable=protected-access
                api._api_url("clusters", segment)

    def test_build_url_does_not_allow_query_injection(self):
        """
        Characters which would otherwise start a query string or a fragment are
        encoded, and the query and fragment of the result stay empty.
        """
        self.assertEqual(
            build_url("https://cm.example.com", "clusters", "c?admin=1#x"),
            "https://cm.example.com/clusters/c%3Fadmin%3D1%23x"
        )

    def test_build_url_ignores_the_path_of_the_base_url(self):
        """
        Only the scheme and the authority of the base url are used.
        """
        self.assertEqual(
            build_url("https://cm.example.com/somewhere?a=b#c", "tools", "echo"),
            "https://cm.example.com/tools/echo"
        )

    def test_build_url_with_query_parameters(self):
        """
        Query parameters are percent-encoded, so that a value can neither
        introduce a further parameter nor a fragment. The comparison operator of
        the event query language survives this, since the server decodes it
        again.
        """
        self.assertEqual(
            build_url(
                "https://cm.example.com",
                "api", "v58", "events",
                query_parameters={
                    "query": "attributes.EVENTCODE==EV_REVISION_CREATED",
                    "maxResults": 50
                }
            ),
            "https://cm.example.com/api/v58/events"
            "?query=attributes.EVENTCODE%3D%3DEV_REVISION_CREATED&maxResults=50"
        )
        self.assertEqual(
            build_url(
                "https://cm.example.com",
                "api", "v58", "events",
                query_parameters={"query": "a=1&admin=true#f"}
            ),
            "https://cm.example.com/api/v58/events"
            "?query=a%3D1%26admin%3Dtrue%23f"
        )

    def test_build_url_leaves_out_query_parameters_without_a_value(self):
        """
        A parameter which was not provided is not sent as an empty one.
        """
        self.assertEqual(
            build_url(
                "https://cm.example.com",
                "api", "v58", "events",
                query_parameters={"query": "category==AUDIT_EVENT",
                                  "maxResults": None}
            ),
            "https://cm.example.com/api/v58/events?query=category%3D%3DAUDIT_EVENT"
        )

    def test_validate_query_parameter_name(self):
        """
        Only plain identifiers are accepted as query parameter names.
        """
        self.assertEqual(validate_query_parameter_name("maxResults"),
                         "maxResults")
        for name in ["", None, "max results", "max=results", "a&b", "1st",
                     "query#fragment"]:
            with self.assertRaises(ClouderaManagerApiError):
                validate_query_parameter_name(name)

    def test_list_events(self):
        """
        The events of an event query are returned, and the query reaches
        Cloudera Manager as a query parameter of the events resource.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(
            json_value={"items": [{"id": "1"}], "totalResults": 1}
        )
        self.assertEqual(
            api.list_events("attributes.EVENTCODE==EV_REVISION_CREATED"),
            [{"id": "1"}]
        )
        requested = api._session.get.call_args.args[0]
        self.assertIn("/api/v58/events?", requested)
        self.assertIn("EV_REVISION_CREATED", requested)
        self.assertIn(f"maxResults={DEFAULT_EVENT_PAGE_SIZE}", requested)

    def test_list_events_without_events(self):
        """
        A query which matches nothing is an empty list, not a failure.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(
            json_value={"items": None, "totalResults": 0}
        )
        self.assertEqual(api.list_events("attributes.EVENTCODE==EV_NONE"), [])

    def test_list_events_which_cannot_be_retrieved(self):
        """
        An events resource which does not answer, or does not answer with json,
        results in `None`, which is not the same as a cluster without events.
        """
        api = _create_api()
        api._session.get.side_effect = requests.exceptions.ConnectTimeout()
        self.assertIsNone(api.list_events("attributes.EVENTCODE==EV_X"))
        api = _create_api()
        api._session.get.side_effect = None
        api._session.get.return_value = _create_response()
        self.assertIsNone(api.list_events("attributes.EVENTCODE==EV_X"))

    def test_event_attribute(self):
        """
        The single value of a named event attribute is read, and an attribute
        which is not there results in `None`.
        """
        event = {
            "attributes": [
                {"name": "EVENTCODE", "values": ["EV_REVISION_CREATED"]},
                {"name": "REVISION", "values": ["1546338003"]},
                {"name": "MESSAGE_CODES", "values": []}
            ]
        }
        self.assertEqual(event_attribute(event, "EVENTCODE"),
                         "EV_REVISION_CREATED")
        self.assertEqual(event_attribute(event, "REVISION"), "1546338003")
        self.assertIsNone(event_attribute(event, "MESSAGE_CODES"))
        self.assertIsNone(event_attribute(event, "SERVICE"))
        self.assertIsNone(event_attribute({}, "SERVICE"))

    def test_check_connection_success(self):
        """
        A reachable api with valid credentials results in True.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="hello")
        self.assertTrue(api.check_connection())

    def test_check_connection_unauthorized(self):
        """
        A 401 results in False.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(status_code=401)
        self.assertFalse(api.check_connection())

    def test_check_connection_unreachable(self):
        """
        A connection error results in False.
        """
        api = _create_api()
        api._session.get.side_effect = requests.RequestException("boom")
        self.assertFalse(api.check_connection())

    def test_list_clusters(self):
        """
        The items envelope is unwrapped.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(
            json_value={"items": [{"name": "ozone-base-cluster"}]}
        )
        self.assertEqual(api.list_clusters(), [{"name": "ozone-base-cluster"}])

    def test_list_clusters_request_failure(self):
        """
        A failed request results in an empty list.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(status_code=500)
        api._session.get.return_value.raise_for_status.side_effect = \
            requests.HTTPError("500")
        self.assertEqual(api.list_clusters(), [])

    def test_list_clusters_undecodable_response(self):
        """
        A response which is not JSON results in an empty list.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="not json")
        self.assertEqual(api.list_clusters(), [])

    def test_list_clusters_null_items(self):
        """
        An explicit null items entry results in an empty list.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(json_value={"items": None})
        self.assertEqual(api.list_clusters(), [])

    def test_list_services_and_roles_url(self):
        """
        Cluster and service names are quoted inside the request url.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(json_value={"items": []})
        api.list_services("my cluster")
        self.assertIn(
            "clusters/my%20cluster/services",
            api._session.get.call_args[0][0]
        )
        api.list_roles("my cluster", "kafka")
        self.assertIn(
            "clusters/my%20cluster/services/kafka/roles",
            api._session.get.call_args[0][0]
        )

    def test_list_service_types(self):
        """
        The service type vocabulary of a cluster is returned as a list of
        strings, and anything else in the response is left out.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(
            json_value={"items": ["KAFKA", "HIVE_ON_TEZ", None, {"name": "x"}]}
        )
        self.assertEqual(
            api.list_service_types("my cluster"),
            ["KAFKA", "HIVE_ON_TEZ"]
        )
        self.assertIn(
            "clusters/my%20cluster/serviceTypes",
            api._session.get.call_args[0][0]
        )

    def test_get_role_process(self):
        """
        The process resource is returned as parsed JSON.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(
            json_value={"configFiles": ["kafka.properties"]}
        )
        self.assertEqual(
            api.get_role_process("cluster", "kafka", "role"),
            {"configFiles": ["kafka.properties"]}
        )

    def test_get_role_process_not_available(self):
        """
        A role without a process results in None.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(status_code=404)
        api._session.get.return_value.raise_for_status.side_effect = \
            requests.HTTPError("404")
        self.assertIsNone(api.get_role_process("cluster", "kafka", "role"))

    def test_get_role_process_undecodable(self):
        """
        A non-JSON process response results in None.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="not json")
        self.assertIsNone(api.get_role_process("cluster", "kafka", "role"))

    def test_get_config_file(self):
        """
        The raw text of a configuration file is returned.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="broker.id=1")
        self.assertEqual(
            api.get_config_file("cluster", "kafka", "role", "kafka.properties"),
            "broker.id=1"
        )

    def test_get_config_file_preserves_path_separators(self):
        """
        Slashes inside a configuration file name stay path separators, while
        the individual segments are quoted.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="a=b")
        api.get_config_file(
            "cluster", "kafka", "role", "kraft conf/kraft-configs.properties"
        )
        requested_url = api._session.get.call_args[0][0]
        self.assertIn(
            "process/configFiles/kraft%20conf/kraft-configs.properties",
            requested_url
        )

    def test_get_config_file_with_traversing_name(self):
        """
        A configuration file name which does not stay below the process
        directory is not requested at all.
        """
        api = _create_api()
        api._session.get.return_value = _create_response(text="a=b")
        for config_file_name in ["../../../../etc/shadow",
                                 "/etc/shadow",
                                 "conf/../../secrets",
                                 ""]:
            self.assertIsNone(api.get_config_file(
                "cluster", "kafka", "role", config_file_name
            ))
        api._session.get.assert_not_called()

    def test_get_config_file_failure(self):
        """
        A failing configuration file request results in None.
        """
        api = _create_api()
        api._session.get.side_effect = requests.RequestException("boom")
        self.assertIsNone(
            api.get_config_file("cluster", "kafka", "role", "kafka.properties")
        )
