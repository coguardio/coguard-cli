"""
Tests for the functions in the cloudera_service_mapping module
"""

import unittest
from coguard_cli.discovery.cloudera_discovery.cloudera_service_mapping import \
    CLOUDERA_SERVICE_TYPE_TO_SOFTWARE, KNOWN_SOFTWARE_NAMES, \
    REVIEWED_CLOUDERA_SERVICE_TYPES, _without_major_version, \
    coguard_service_name, config_file_type, create_cluster_service_identifier, \
    is_scannable_config_file, unreviewed_service_types

class TestClouderaServiceMapping(unittest.TestCase):
    """
    The class for testing the Cloudera service mapping module
    """

    def test_coguard_service_name_lower_cases_the_service_type(self):
        """
        The Cloudera service type, lower-cased, is the CoGuard service name.
        """
        self.assertEqual(coguard_service_name("KAFKA"), "kafka")
        self.assertEqual(coguard_service_name("ZOOKEEPER"), "zookeeper")
        self.assertEqual(coguard_service_name("OZONE"), "ozone")
        self.assertEqual(coguard_service_name("RANGER_KMS"), "ranger_kms")
        self.assertEqual(coguard_service_name(" kafka "), "kafka")

    def test_coguard_service_name_translates_cloudera_specific_types(self):
        """
        The service types under which Cloudera packages software of a different
        name are translated to that software.
        """
        self.assertEqual(coguard_service_name("HIVE_ON_TEZ"), "hive")
        self.assertEqual(coguard_service_name("HIVE_LLAP"), "hive")
        self.assertEqual(coguard_service_name("SPARK3_ON_YARN"), "spark")
        self.assertEqual(coguard_service_name("SPARK2_ON_YARN"), "spark")
        self.assertEqual(coguard_service_name("LIVY_FOR_SPARK3"), "livy")
        self.assertEqual(coguard_service_name("SQOOP_CLIENT"), "sqoop")
        self.assertEqual(coguard_service_name(" hive_on_tez "), "hive")

    def test_coguard_service_name_of_a_future_major_version(self):
        """
        A major version Cloudera has not released yet is recognized, because the
        version is what it carries in the type.
        """
        self.assertEqual(coguard_service_name("SPARK4_ON_YARN"), "spark")
        self.assertEqual(coguard_service_name("SPARK10_ON_YARN"), "spark")
        self.assertEqual(coguard_service_name("LIVY_FOR_SPARK4"), "livy")

    def test_a_relaxed_lookup_resolves_to_a_known_service_name(self):
        """
        Neither removing the version nor splitting a composite type widens which
        service names exist; both only widen which types find one of them.
        """
        for cloudera_service_type in [
                "SPARK4_ON_YARN", "SPARK4_ON_MESOS", "HIVE4_ON_FLINK",
                "LIVY_FOR_SPARK4"
        ]:
            self.assertIn(
                coguard_service_name(cloudera_service_type),
                KNOWN_SOFTWARE_NAMES,
                f"{cloudera_service_type} resolved to a name nothing describes"
            )

    def test_the_versionless_lookup_table_is_unambiguous(self):
        """
        No two service types collapse onto the same versionless form while
        naming different software, which is what makes the relaxed lookup safe.
        """
        collapsed = {}
        for service_type, software in CLOUDERA_SERVICE_TYPE_TO_SOFTWARE.items():
            versionless = _without_major_version(service_type)
            self.assertIn(
                collapsed.setdefault(versionless, software),
                [software],
                f"{service_type} collapses onto {versionless}, which already "
                f"names {collapsed[versionless]}"
            )

    def test_coguard_service_name_of_a_new_engine_combination(self):
        """
        A composite type which is new, but whose software is not, is resolved to
        that software.
        """
        self.assertEqual(coguard_service_name("HIVE_ON_FLINK"), "hive")
        self.assertEqual(coguard_service_name("SPARK5_ON_KUBERNETES"), "spark")
        self.assertEqual(coguard_service_name("LIVY_FOR_SPARK4"), "livy")
        self.assertEqual(coguard_service_name("IMPALA_ON_OZONE"), "impala")

    def test_splitting_a_type_cannot_invent_a_service_name(self):
        """
        A composite type is only resolved to a service name Cloudera's own
        vocabulary establishes. Where it does not, the type keeps its own name,
        because the descriptor reference does not promise that the part before
        `_ON_` is a piece of software.
        """
        self.assertEqual(coguard_service_name("VENDOR_ON_CALL"),
                         "vendor_on_call")
        self.assertEqual(coguard_service_name("WIDGET_ON_YARN"),
                         "widget_on_yarn")
        self.assertEqual(coguard_service_name("_ON_YARN"), "_on_yarn")
        self.assertEqual(coguard_service_name("HIVE_ON_"), "hive_on_")

    def test_coguard_service_name_does_not_decompose_a_plain_type(self):
        """
        A type without a qualifier is not taken apart at all.
        """
        self.assertEqual(coguard_service_name("METERINGV2"), "meteringv2")
        self.assertEqual(coguard_service_name("AWS_S3"), "aws_s3")
        self.assertEqual(coguard_service_name("QUERY_PROCESSOR"),
                         "query_processor")

    def test_translated_types_are_not_listed_as_needing_no_translation(self):
        """
        The two tables describe disjoint sets of service types: a type either
        names its software, or is translated.
        """
        self.assertEqual(
            REVIEWED_CLOUDERA_SERVICE_TYPES.intersection(
                CLOUDERA_SERVICE_TYPE_TO_SOFTWARE.keys()
            ),
            set()
        )

    def test_unreviewed_service_types(self):
        """
        A service type the integration does not know about is pointed out, and a
        known one is not.
        """
        self.assertEqual(
            unreviewed_service_types([
                "KAFKA", "HIVE_ON_TEZ", "SOMETHING_NEW", " another_new "
            ]),
            ["ANOTHER_NEW", "SOMETHING_NEW"]
        )

    def test_unreviewed_service_types_of_a_translatable_new_version(self):
        """
        A new major version of software the table describes is translated, and
        hence is not something to point out. A new version of a type which is
        only known to need no translation is pointed out, since it may well be
        something else.
        """
        self.assertEqual(unreviewed_service_types(["SPARK4_ON_YARN"]), [])
        self.assertEqual(unreviewed_service_types(["HIVE_ON_FLINK"]), [])
        self.assertEqual(
            unreviewed_service_types(["METERINGV3", "WIDGET_ON_YARN"]),
            ["METERINGV3", "WIDGET_ON_YARN"]
        )

    def test_unreviewed_service_types_of_the_known_vocabulary(self):
        """
        The vocabulary the tables were written against is fully covered.
        """
        self.assertEqual(
            unreviewed_service_types(
                sorted(REVIEWED_CLOUDERA_SERVICE_TYPES) +
                sorted(CLOUDERA_SERVICE_TYPE_TO_SOFTWARE.keys())
            ),
            []
        )

    def test_unreviewed_service_types_without_input(self):
        """
        No declared service type means nothing to point out.
        """
        self.assertEqual(unreviewed_service_types([]), [])
        self.assertEqual(unreviewed_service_types(None), [])
        self.assertEqual(unreviewed_service_types(["", "  "]), [])

    def test_coguard_service_name_empty(self):
        """
        An empty service type results in an empty service name.
        """
        self.assertEqual(coguard_service_name(""), "")
        self.assertEqual(coguard_service_name(None), "")

    def test_create_cluster_service_identifier_strips_redundant_prefix(self):
        """
        A role type repeating the service name does not lead to a repetition.
        """
        self.assertEqual(
            create_cluster_service_identifier("kafka", "KAFKA_BROKER"),
            "kafka_broker"
        )
        self.assertEqual(
            create_cluster_service_identifier("ranger", "RANGER_ADMIN"),
            "ranger_admin"
        )

    def test_create_cluster_service_identifier_distinct_role_type(self):
        """
        A role type which does not repeat the service name is appended.
        """
        self.assertEqual(
            create_cluster_service_identifier("hdfs", "NAMENODE"),
            "hdfs_namenode"
        )
        self.assertEqual(
            create_cluster_service_identifier("kafka", "KRAFT"),
            "kafka_kraft"
        )

    def test_create_cluster_service_identifier_edge_cases(self):
        """
        Missing service or role names do not produce dangling separators.
        """
        self.assertEqual(create_cluster_service_identifier("hdfs", ""), "hdfs")
        self.assertEqual(create_cluster_service_identifier("", "NAMENODE"), "namenode")
        self.assertEqual(create_cluster_service_identifier("knox", "KNOX"), "knox")

    def test_config_file_type_by_extension(self):
        """
        Known configuration file extensions are mapped to CoGuard types.
        """
        self.assertEqual(config_file_type("kafka.properties"), "properties")
        self.assertEqual(config_file_type("hdfs-site.xml"), "xml")
        self.assertEqual(config_file_type("redaction-rules.json"), "json")
        self.assertEqual(config_file_type("zoo.cfg"), "properties")
        self.assertEqual(config_file_type("some.yaml"), "yaml")

    def test_config_file_type_by_name_takes_precedence(self):
        """
        An exact name match wins over the extension based lookup.
        """
        self.assertEqual(config_file_type("krb5.conf"), "krb")
        self.assertEqual(config_file_type("etc/krb5.conf"), "krb")
        # A generic `.conf` is not assumed to be a key-value file.
        self.assertEqual(config_file_type("atlas.conf"), "custom")

    def test_config_file_type_nested_path(self):
        """
        Configuration files inside a sub-directory are still recognized.
        """
        self.assertEqual(
            config_file_type("kraft-conf/kraft-configs.properties"),
            "properties"
        )

    def test_config_file_type_excludes_non_config_extensions(self):
        """
        Scripts, templates, key material and tabular data are excluded.
        """
        for file_name in [
                "altscript.sh",
                "topology.py",
                "creds.localjceks",
                "zk_client_keystore.key",
                "service-usernames.csv",
                "topology.map"
        ]:
            self.assertIsNone(config_file_type(file_name), msg=file_name)

    def test_config_file_type_excludes_non_config_paths(self):
        """
        Everything inside a helper script or template directory is excluded.
        """
        self.assertIsNone(config_file_type("scripts/control.sh"))
        self.assertIsNone(config_file_type("scripts/kraft_configs.py"))
        self.assertIsNone(
            config_file_type("aux/templates/kafka-monitoring.properties.j2")
        )
        # Even a file which would otherwise be a valid configuration file.
        self.assertIsNone(config_file_type("scripts/some.properties"))

    def test_config_file_type_unknown_and_empty(self):
        """
        Unknown extensions and empty inputs yield None.
        """
        self.assertIsNone(config_file_type("something.unknown"))
        self.assertIsNone(config_file_type("no_extension"))
        self.assertIsNone(config_file_type(""))
        self.assertIsNone(config_file_type(None))

    def test_is_scannable_config_file(self):
        """
        The convenience predicate matches the config_file_type outcome.
        """
        self.assertTrue(is_scannable_config_file("kafka.properties"))
        self.assertFalse(is_scannable_config_file("scripts/control.sh"))
