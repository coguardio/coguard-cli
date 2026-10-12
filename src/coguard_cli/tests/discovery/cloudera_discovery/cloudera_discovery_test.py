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
    report_unreviewed_service_types, roles_not_running, unreadable_template, \
    unresolved_placeholder
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

    def test_collect_config_files_for_role_unreadable_template(self):
        """
        A file whose placeholder leaves it unreadable, and which no renderer
        knows, is collected with the placeholder neutralized.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {
            "configFiles": ["aux/ozone-prometheus.yml",
                            "ozone-conf/log4j.properties"]
        }
        api.get_config_file.side_effect = lambda *args: (
            "scrape_interval: {{SCRAPE_INTERVAL}}"
            if args[-1].endswith(".yml")
            else "log4j.appender.file={{CMF_CONF_DIR}}/out.log"
        )
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-template-test")
        try:
            result = collect_config_files_for_role(
                api, "cluster", "ozone", {"name": "role"}, temp_dir
            )
            self.assertEqual(
                [entry["fileName"] for entry in result],
                ["ozone-prometheus.yml", "log4j.properties"]
            )
            with open(os.path.join(temp_dir, "aux", "ozone-prometheus.yml"),
                      encoding='utf-8') as template_file:
                self.assertEqual(template_file.read(),
                                 'scrape_interval: "{{SCRAPE_INTERVAL}}"')
            # A placeholder which does not break the syntax is left alone.
            with open(os.path.join(temp_dir, "ozone-conf", "log4j.properties"),
                      encoding='utf-8') as properties_file:
                self.assertEqual(properties_file.read(),
                                 "log4j.appender.file={{CMF_CONF_DIR}}/out.log")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_collect_config_files_for_role_still_unreadable_template(self):
        """
        A template which is unreadable even with neutral values in place of its
        placeholders is not collected.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {"configFiles": ["aux/broken.json"]}
        api.get_config_file.return_value = '{"a": {{VALUE}} "b": 1}'
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-template-test")
        try:
            result = collect_config_files_for_role(
                api, "cluster", "knox", {"name": "role"}, temp_dir
            )
            self.assertEqual(result, [])
            self.assertFalse(
                os.path.exists(os.path.join(temp_dir, "aux", "broken.json"))
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_collect_config_files_for_role_renders_known_template(self):
        """
        A template a renderer knows is rendered from the configuration of the
        role, which may draw on a file listed after the template.
        """
        api = unittest.mock.MagicMock()
        api.get_role_process.return_value = {"configFiles": [
            "aux/ozone-prometheus.yml",
            "ozone-conf/ozone-om.properties"
        ]}
        api.get_config_file.side_effect = lambda *args: (
            "scrape_interval: {{SCRAPE_INTERVAL}}\n"
            "scheme: {{SCHEME}}\n"
            "targets:\n{{TARGETS}}"
            if args[-1].endswith(".yml")
            else "om-1.example.com:ozone.om.http-port=9874"
        )
        api.list_role_config_groups.return_value = [
            {"name": "ozone-OZONE_PROMETHEUS-BASE",
             "roleType": "OZONE_PROMETHEUS",
             "base": True}
        ]
        api.get_role_config_group_config.return_value = {
            "ozone.prometheus.scrape.interval": {"default": "15s"},
            "ssl_enabled": {"value": "false", "default": "false"}
        }
        api.get_service_config.return_value = {}
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-template-test")
        try:
            result = collect_config_files_for_role(
                api, "cluster", "ozone", {"name": "role"}, temp_dir, "OZONE"
            )
            self.assertEqual(len(result), 2)
            with open(os.path.join(temp_dir, "aux", "ozone-prometheus.yml"),
                      encoding='utf-8') as template_file:
                self.assertEqual(
                    template_file.read(),
                    'scrape_interval: 15s\nscheme: http\ntargets:\n'
                    '        - "om-1.example.com:9874"\n'
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_unresolved_placeholder_forms(self):
        """
        Both the mustache form and the bare token form are recognized, quoted or
        not, and an ordinary word is not.
        """
        self.assertEqual(
            unresolved_placeholder("scrape_interval: {{SCRAPE_INTERVAL}}"),
            "{{SCRAPE_INTERVAL}}"
        )
        self.assertEqual(
            unresolved_placeholder('  "a": "b",\n  PROXYUSER_BLOCK,\n'),
            "PROXYUSER_BLOCK"
        )
        self.assertEqual(
            unresolved_placeholder('  "PROXYUSER_BLOCK",\n'),
            "PROXYUSER_BLOCK"
        )
        self.assertEqual(
            unresolved_placeholder("  CUSTOMIZABLE_AZURE_CAB_CONTENT\n"),
            "CUSTOMIZABLE_AZURE_CAB_CONTENT"
        )
        self.assertIsNone(unresolved_placeholder("broker.id=1"))
        self.assertIsNone(unresolved_placeholder("  EOF\n"))
        self.assertIsNone(unresolved_placeholder("{{lowercase}}"))

    def test_unreadable_template_needs_both_conditions(self):
        """
        A placeholder inside the value of a file which still parses is what
        Cloudera leaves in the configuration it really deployed, and is kept. Only
        a placeholder which destroys the syntax marks a template.
        """
        self.assertIsNone(unreadable_template(
            '<property><value>{{CMF_CONF_DIR}}/x.jks</value></property>', "xml"
        ))
        self.assertIsNone(unreadable_template(
            'log4j.appender.file={{CMF_CONF_DIR}}/out.log', "properties"
        ))
        self.assertIsNone(unreadable_template(
            '{"path": "{{CMF_CONF_DIR}}/x"}', "json"
        ))
        self.assertEqual(
            unreadable_template("scrape_interval: {{SCRAPE_INTERVAL}}", "yaml"),
            "{{SCRAPE_INTERVAL}}"
        )
        self.assertEqual(
            unreadable_template('{"a": "b",\n PROXYUSER_BLOCK,\n "c": "d"}',
                                "json"),
            "PROXYUSER_BLOCK"
        )

    def test_unreadable_template_keeps_a_broken_deployed_file(self):
        """
        A file which is malformed for a reason other than a placeholder is still
        collected, so that the parse error is reported rather than hidden.
        """
        self.assertIsNone(unreadable_template('{"a": ', "json"))
        self.assertIsNone(unreadable_template("a:\n- b\n  c: d\n", "yaml"))

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

    def test_extract_cloudera_cluster_representation_splits_foreign_files(self):
        """
        The configuration files of other software a role is handed are listed
        as cluster services of that software, rather than of the role.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [{"name": "hbase", "type": "HBASE"}]
        api.list_roles.return_value = [
            {"name": "hbase-MASTER-a", "type": "MASTER"}
        ]
        api.get_role_process.return_value = {"configFiles": [
            "hbase-site.xml",
            "ssl-client.xml",
            "ozone-site.xml",
            "core-site.xml",
            "hadoop-conf/core-site.xml",
            "hadoop-conf/ozone-site.xml"
        ]}
        api.get_config_file.return_value = "<configuration/>"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            services = manifest["clusterServices"]
            self.assertEqual(
                sorted(services.keys()),
                ["hbase_master", "hbase_master_hadoop", "hbase_master_ozone"]
            )
            self.assertEqual(services["hbase_master"]["serviceName"], "hbase")
            self.assertEqual(
                services["hbase_master_hadoop"]["serviceName"], "hadoop"
            )
            self.assertEqual(
                services["hbase_master_ozone"]["serviceName"], "ozone"
            )
            self.assertEqual(
                sorted(entry["fileName"]
                       for entry in services["hbase_master"]["configFileList"]),
                ["hbase-site.xml", "ssl-client.xml"]
            )
            self.assertEqual(
                sorted((entry["subPath"], entry["fileName"])
                       for entry
                       in services["hbase_master_ozone"]["configFileList"]),
                [(".", "ozone-site.xml"), ("./hadoop-conf", "ozone-site.xml")]
            )
            for identifier, service in services.items():
                for entry in service["configFileList"]:
                    self.assertTrue(os.path.exists(os.path.join(
                        folder, "clusterServices", identifier,
                        entry["subPath"], entry["fileName"]
                    )))
            # Nothing is left behind in the folder of the role.
            self.assertFalse(os.path.exists(os.path.join(
                folder, "clusterServices", "hbase_master", "hadoop-conf"
            )))
            self.assertFalse(os.path.exists(os.path.join(
                folder, "clusterServices", "hbase_master", "ozone-site.xml"
            )))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_extract_cloudera_cluster_representation_only_foreign_files(self):
        """
        A role which only carries the configuration of other software does not
        produce an empty cluster service of its own.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [{"name": "kafka", "type": "KAFKA"}]
        api.list_roles.return_value = [
            {"name": "kafka-GATEWAY-a", "type": "GATEWAY"}
        ]
        api.get_role_process.return_value = {
            "configFiles": ["atlas-application.properties"]
        }
        api.get_config_file.return_value = "a=b"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            self.assertEqual(
                list(manifest["clusterServices"].keys()),
                ["kafka_gateway_atlas"]
            )
            self.assertEqual(
                manifest["clusterServices"]["kafka_gateway_atlas"]["serviceName"],
                "atlas"
            )
            self.assertFalse(os.path.exists(os.path.join(
                folder, "clusterServices", "kafka_gateway"
            )))
            self.assertTrue(os.path.exists(os.path.join(
                folder, "clusterServices", "kafka_gateway_atlas",
                "atlas-application.properties"
            )))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_roles_not_running(self):
        """
        Every stopped instance of a daemon counts, while a role which does not
        run a process by design, or one in a transitional state, does not.
        """
        roles = [
            {"name": "hdfs-DATANODE-b", "type": "DATANODE", "roleState": "STOPPED"},
            {"name": "hdfs-DATANODE-a", "type": "DATANODE", "roleState": "STARTED"},
            {"name": "hdfs-DATANODE-c", "type": "DATANODE", "roleState": "UNKNOWN"},
            {"name": "hdfs-BALANCER-a", "type": "BALANCER", "roleState": "NA"},
            {"name": "hdfs-GATEWAY-a", "type": "GATEWAY", "roleState": "NA"},
            {"name": "hdfs-NAMENODE-a", "type": "NAMENODE", "roleState": "STARTING"},
            {"type": "NAMENODE", "roleState": "STOPPED"},
        ]
        self.assertEqual(roles_not_running(roles),
                         ["hdfs-DATANODE-b", "hdfs-DATANODE-c"])

    def test_extract_cloudera_cluster_representation_roles_not_running(self):
        """
        A daemon which is not running is reported via the failed_rules.json in
        the root of the extraction, while a gateway without a process is not.
        """
        api = unittest.mock.MagicMock()
        api.list_clusters.return_value = [{"name": "cluster"}]
        api.list_services.return_value = [{"name": "hdfs", "type": "HDFS"}]
        api.list_roles.return_value = [
            {"name": "hdfs-NAMENODE-a", "type": "NAMENODE", "roleState": "STARTED"},
            {"name": "hdfs-DATANODE-a", "type": "DATANODE", "roleState": "STOPPED"},
            {"name": "hdfs-GATEWAY-a", "type": "GATEWAY", "roleState": "NA"}
        ]
        api.get_role_process.side_effect = lambda cluster, service, role: \
            None if "GATEWAY" in role else {"configFiles": ["hdfs-site.xml"]}
        api.get_config_file.return_value = "<configuration/>"
        result = extract_cloudera_cluster_representation(api, "customer")
        self.assertIsNotNone(result)
        folder, manifest = result
        try:
            self.assertEqual(sorted(manifest["clusterServices"]),
                             ["hdfs_datanode", "hdfs_namenode"])
            with open(os.path.join(folder, "failed_rules.json"),
                      encoding='utf-8') as failed_rules_file:
                self.assertEqual(json.load(failed_rules_file),
                                 ["cluster_cloudera_roles_not_running"])
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        # With every daemon running, the gateway alone does not fail the rule.
        api.list_roles.return_value = [
            {"name": "hdfs-NAMENODE-a", "type": "NAMENODE", "roleState": "STARTED"},
            {"name": "hdfs-GATEWAY-a", "type": "GATEWAY", "roleState": "NA"}
        ]
        folder, _ = extract_cloudera_cluster_representation(api, "customer")
        try:
            self.assertFalse(
                os.path.exists(os.path.join(folder, "failed_rules.json"))
            )
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
