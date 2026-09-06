"""
Tests for the extraction functions in the cloudera_discovery module
"""

import json
import os
import shutil
import tempfile
import unittest
import unittest.mock
from coguard_cli.discovery.cloudera_discovery import \
    collect_config_files_for_role, determine_cluster_name, \
    extract_cloudera_cluster_representation, group_roles_by_type, \
    report_unreviewed_service_types
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApiError

class TestClouderaDiscovery(unittest.TestCase):
    """
    The class for testing the Cloudera discovery module
    """

    def test_determine_cluster_name_single_cluster(self):
        """
        With exactly one cluster, that cluster is chosen.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "ozone-base-cluster"}]
        self.assertEqual(determine_cluster_name(api), "ozone-base-cluster")

    def test_determine_cluster_name_no_clusters(self):
        """
        Without any cluster, None is returned.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = []
        self.assertIsNone(determine_cluster_name(api))

    def test_determine_cluster_name_multiple_clusters_ambiguous(self):
        """
        With multiple clusters and no request, the choice is ambiguous.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "one"}, {"name": "two"}]
        self.assertIsNone(determine_cluster_name(api))

    def test_determine_cluster_name_multiple_clusters_requested(self):
        """
        With multiple clusters, the requested one is used.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "one"}, {"name": "two"}]
        self.assertEqual(determine_cluster_name(api, "two"), "two")

    def test_determine_cluster_name_requested_not_present(self):
        """
        A request for a cluster which does not exist results in None.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "one"}]
        self.assertIsNone(determine_cluster_name(api, "does-not-exist"))

    def test_group_roles_by_type_one_representative_per_type(self):
        """
        Each role type is represented exactly once.
        """
        roles = [
            {"name": "kafka-KAFKA_BROKER-a", "type": "KAFKA_BROKER"},
            {"name": "kafka-KAFKA_BROKER-b", "type": "KAFKA_BROKER"},
            {"name": "kafka-KRAFT-c", "type": "KRAFT"},
        ]
        result = group_roles_by_type(roles)
        self.assertEqual(sorted(result.keys()), ["KAFKA_BROKER", "KRAFT"])
        # Stable choice: the lexicographically smallest name.
        self.assertEqual(result["KAFKA_BROKER"]["name"], "kafka-KAFKA_BROKER-a")

    def test_group_roles_by_type_prefers_started_role(self):
        """
        A running role is preferred over a stopped one.
        """
        roles = [
            {"name": "a", "type": "KAFKA_BROKER", "roleState": "STOPPED"},
            {"name": "b", "type": "KAFKA_BROKER", "roleState": "STARTED"},
        ]
        self.assertEqual(
            group_roles_by_type(roles)["KAFKA_BROKER"]["name"],
            "b"
        )

    def test_group_roles_by_type_keeps_first_started_role(self):
        """
        Once a running role was found, it is not replaced by another one.
        """
        roles = [
            {"name": "a", "type": "KAFKA_BROKER", "roleState": "STARTED"},
            {"name": "b", "type": "KAFKA_BROKER", "roleState": "STARTED"},
        ]
        self.assertEqual(
            group_roles_by_type(roles)["KAFKA_BROKER"]["name"],
            "a"
        )

    def test_group_roles_by_type_ignores_roles_without_type(self):
        """
        A role without a type is skipped.
        """
        self.assertEqual(group_roles_by_type([{"name": "a"}]), {})

    def test_collect_config_files_for_role(self):
        """
        Consumable configuration files are written to disk and listed.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {
            "configFiles": [
                "kafka.properties",
                "kraft-conf/kraft-configs.properties",
                "scripts/control.sh",
                "creds.localjceks"
            ]
        }
        api.get_config_file.return_value = "broker.id=1"
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-collect-test")
        try:
            result = collect_config_files_for_role(
                api,
                "cluster",
                "kafka",
                {"name": "kafka-KAFKA_BROKER-a"},
                temp_dir
            )
            self.assertEqual(len(result), 2)
            file_names = sorted(entry["fileName"] for entry in result)
            self.assertEqual(
                file_names,
                ["kafka.properties", "kraft-configs.properties"]
            )
            sub_paths = sorted(entry["subPath"] for entry in result)
            self.assertEqual(sub_paths, [".", "./kraft-conf"])
            self.assertTrue(
                os.path.exists(os.path.join(temp_dir, "kafka.properties"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(
                    temp_dir, "kraft-conf", "kraft-configs.properties"
                ))
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_collect_config_files_for_role_traversing_name(self):
        """
        A configuration file name pointing outside of the extraction folder is
        neither retrieved nor written.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {
            "configFiles": [
                "../../../../tmp/coguard-cloudera-escape.properties",
                "/tmp/coguard-cloudera-absolute.properties",
                "kafka.properties"
            ]
        }
        api.get_config_file.return_value = "broker.id=1"
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-traversal-test")
        try:
            result = collect_config_files_for_role(
                api,
                "cluster",
                "kafka",
                {"name": "kafka-KAFKA_BROKER-a"},
                os.path.join(temp_dir, "clusterServices", "kafka_broker")
            )
            self.assertEqual(
                [entry["fileName"] for entry in result],
                ["kafka.properties"]
            )
            self.assertFalse(
                os.path.exists("/tmp/coguard-cloudera-escape.properties")
            )
            self.assertFalse(
                os.path.exists("/tmp/coguard-cloudera-absolute.properties")
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_collect_config_files_for_role_no_process(self):
        """
        A role without a process yields an empty list.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = None
        self.assertEqual(
            collect_config_files_for_role(
                api, "cluster", "kafka", {"name": "role"}, "/tmp"
            ),
            []
        )

    def test_collect_config_files_for_role_unretrievable_file(self):
        """
        A configuration file which cannot be retrieved is skipped.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {
            "configFiles": ["kafka.properties"]
        }
        api.get_config_file.return_value = None
        self.assertEqual(
            collect_config_files_for_role(
                api, "cluster", "kafka", {"name": "role"}, "/tmp"
            ),
            []
        )

    def test_report_unreviewed_service_types(self):
        """
        A service type the integration has no knowledge of is pointed out.
        """
        api = unittest.mock.MagicMock()
        api.list_service_types.return_value = ["KAFKA", "SOMETHING_NEW"]
        self.assertEqual(
            report_unreviewed_service_types(api, "cluster"),
            ["SOMETHING_NEW"]
        )

    def test_report_unreviewed_service_types_all_known(self):
        """
        Nothing is pointed out if every declared type is known.
        """
        api = unittest.mock.MagicMock()
        api.list_service_types.return_value = ["KAFKA", "HIVE_ON_TEZ", "OZONE"]
        self.assertEqual(report_unreviewed_service_types(api, "cluster"), [])

    def test_report_unreviewed_service_types_unavailable(self):
        """
        A Cloudera Manager which does not answer the request for its service
        types does not fail the extraction.
        """
        api = unittest.mock.MagicMock()
        api.list_service_types.side_effect = ClouderaManagerApiError("no cluster")
        self.assertEqual(report_unreviewed_service_types(api, "cluster"), [])
        # A response which is not a list of service types is tolerated as well.
        api.list_service_types.side_effect = None
        api.list_service_types.return_value = 42
        self.assertEqual(report_unreviewed_service_types(api, "cluster"), [])

    def test_extract_cloudera_cluster_representation(self):
        """
        The happy path produces a folder and a manifest.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "ozone-base-cluster"}]
        api.list_services.return_value = [
            {"name": "kafka", "type": "KAFKA"},
            {"name": "hive_on_tez", "type": "HIVE_ON_TEZ"}
        ]
        api.list_roles.side_effect = lambda cluster, service: [
            {"name": f"{service}-ROLE-a", "type": "KAFKA_BROKER"}
        ] if service == "kafka" else [
            {"name": f"{service}-ROLE-a", "type": "HIVESERVER2"}
        ]
        api.get_role_process.return_value = {"configFiles": ["some.properties"]}
        api.get_config_file.return_value = "a=b"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            self.assertEqual(manifest["name"], "ozone-base-cluster".replace("-", "_"))
            self.assertEqual(manifest["customerId"], "customer")
            self.assertEqual(
                sorted(manifest["clusterServices"].keys()),
                ["hive_on_tez_hiveserver2", "kafka_broker"]
            )
            self.assertEqual(
                manifest["clusterServices"]["kafka_broker"]["serviceName"],
                "kafka"
            )
            # The identifier keeps the name the service carries in the cluster,
            # while the rule set is the software the Cloudera type packages.
            self.assertEqual(
                manifest["clusterServices"]["hive_on_tez_hiveserver2"]["serviceName"],
                "hive"
            )
            with open(os.path.join(folder, "manifest.json"), 'r',
                      encoding='utf-8') as manifest_stream:
                self.assertEqual(json.load(manifest_stream), manifest)
            self.assertTrue(os.path.exists(os.path.join(
                folder, "clusterServices", "kafka_broker", "some.properties"
            )))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_extract_cloudera_cluster_representation_colliding_identifiers(self):
        """
        Two (service, role type) pairs which produce the same identifier are
        counted up, rather than each suffix being appended to the previous one.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        # Three services whose names only differ in case all produce the
        # identifier `kafka_broker` for their broker role.
        api.list_services.return_value = [
            {"name": "kafka", "type": "KAFKA"},
            {"name": "Kafka", "type": "KAFKA"},
            {"name": "KAFKA", "type": "KAFKA"}
        ]
        api.list_roles.side_effect = lambda cluster, service: [
            {"name": f"{service}-KAFKA_BROKER-a", "type": "KAFKA_BROKER"}
        ]
        api.get_role_process.return_value = {"configFiles": ["some.properties"]}
        api.get_config_file.return_value = "a=b"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            self.assertEqual(
                sorted(manifest["clusterServices"].keys()),
                ["kafka_broker", "kafka_broker_0", "kafka_broker_1"]
            )
            for identifier in manifest["clusterServices"]:
                self.assertTrue(os.path.exists(os.path.join(
                    folder, "clusterServices", identifier, "some.properties"
                )))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_extract_cloudera_cluster_representation_no_cluster(self):
        """
        Without a determinable cluster, None is returned.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = []
        self.assertIsNone(
            extract_cloudera_cluster_representation(api, "customer")
        )

    def test_extract_cloudera_cluster_representation_no_services(self):
        """
        A cluster without services results in None.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = []
        self.assertIsNone(
            extract_cloudera_cluster_representation(api, "customer")
        )

    def test_extract_cloudera_cluster_representation_no_config_files(self):
        """
        If no service yields a configuration file, None is returned and no
        empty service folder is left behind.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [{"name": "tez", "type": "TEZ"}]
        api.list_roles.return_value = [{"name": "tez-GATEWAY-a", "type": "GATEWAY"}]
        api.get_role_process.return_value = None
        self.assertIsNone(
            extract_cloudera_cluster_representation(api, "customer")
        )

    def test_extract_cloudera_cluster_representation_skips_service_without_roles(self):
        """
        A service without any role is skipped, and does not abort the run.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [
            {"name": "CORE_SETTINGS-1", "type": "CORE_SETTINGS"},
            {"name": "kafka", "type": "KAFKA"}
        ]
        api.list_roles.side_effect = lambda cluster, service: [] \
            if service == "CORE_SETTINGS-1" \
            else [{"name": "kafka-KAFKA_BROKER-a", "type": "KAFKA_BROKER"}]
        api.get_role_process.return_value = {"configFiles": ["some.properties"]}
        api.get_config_file.return_value = "a=b"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            self.assertEqual(
                list(manifest["clusterServices"].keys()),
                ["kafka_broker"]
            )
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_extract_cloudera_cluster_representation_skips_incomplete_service(self):
        """
        A service entry without a name or type is skipped.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [{"name": "no-type"}]
        self.assertIsNone(
            extract_cloudera_cluster_representation(api, "customer")
        )
