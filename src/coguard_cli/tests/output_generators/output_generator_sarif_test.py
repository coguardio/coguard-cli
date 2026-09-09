"""
The test module for the sarif output generator.
"""

import unittest
import unittest.mock
from coguard_cli.output_generators.output_generator_sarif import \
    severity_band, translate_result_to_sarif
from importlib.metadata import version, PackageNotFoundError

class TestTranslateToSarif(unittest.TestCase):
    """
    The unit tests for the output generator Sarif module.
    """

    def test_severity_band(self):
        """
        The bands are the ones the formatted output uses, so that a finding does
        not change its severity by being looked at somewhere else.
        """
        self.assertEqual(severity_band(5), ("error", "8.0"))
        self.assertEqual(severity_band(4), ("error", "8.0"))
        self.assertEqual(severity_band(3), ("warning", "5.0"))
        self.assertEqual(severity_band(2), ("note", "2.0"))
        self.assertEqual(severity_band(1), ("note", "2.0"))

    def test_severity_band_unreadable_severity(self):
        """
        A severity which is not a number is treated as the middle band, rather
        than failing the translation of the whole report.
        """
        self.assertEqual(severity_band(None), ("warning", "5.0"))
        self.assertEqual(severity_band("high"), ("warning", "5.0"))

    def test_translate_result_to_sarif_rule_described_once(self):
        """
        A rule which failed for more than one file is described once, and a rule
        with a readable name is described under it.
        """
        to_safe_path = unittest.mock.MagicMock()
        coguard_output = {
            "failed": [
                {
                    "rule": {
                        "name": "ozone_grpc_tls_enabled",
                        "humanReadableName": "Ozone gRPC TLS enabled",
                        "severity": 5,
                        "documentation": {
                            "documentation": "gRPC without TLS...",
                            "remediation": "Set it to true.",
                            "sources": []
                        }
                    },
                    "fromLine": 0,
                    "toLine": 1,
                    "service": "ozone_manager",
                    "config_file": {
                        "fileName": "ozone-site.xml",
                        "subPath": ".",
                        "configFileType": "xml"
                    }
                },
                {
                    "rule": {
                        "name": "ozone_grpc_tls_enabled",
                        "humanReadableName": "Ozone gRPC TLS enabled",
                        "severity": 5,
                        "documentation": {
                            "documentation": "gRPC without TLS...",
                            "remediation": "Set it to true.",
                            "sources": []
                        }
                    },
                    "fromLine": 0,
                    "toLine": 1,
                    "service": "ozone_datanode",
                    "config_file": {
                        "fileName": "ozone-site.xml",
                        "subPath": ".",
                        "configFileType": "xml"
                    }
                }
            ]
        }
        with unittest.mock.patch(
                'json.dump',
                new_callable=unittest.mock.MagicMock()
        ) as json_dump:
            translate_result_to_sarif(coguard_output, to_safe_path)
            written = json_dump.call_args[0][0]
        rules = written["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["shortDescription"]["text"],
                         "Ozone gRPC TLS enabled")
        self.assertEqual(rules[0]["properties"]["security-severity"], "8.0")
        self.assertEqual(len(written["runs"][0]["results"]), 2)
        self.assertEqual(
            [result["level"] for result in written["runs"][0]["results"]],
            ["error", "error"]
        )

    def test_translate_result_to_sarif_empty_path(self):
        """
        The test that an empty path will throw an exception.
        """
        with self.assertRaises(ValueError):
            translate_result_to_sarif(
                {},
                ""
            )
        with self.assertRaises(ValueError):
            translate_result_to_sarif(
                {},
                None
            )

    def test_translate_result_to_sarif_none_result(self):
        """
        The test that an empty path will throw an exception.
        """
        with self.assertRaises(ValueError):
            translate_result_to_sarif(
                None,
                "foo"
            )

    def test_translate_result_to_sarif_empty_result(self):
        """
        The test that an empty path writes nothing.
        """
        to_safe_path = unittest.mock.MagicMock()
        with unittest.mock.patch(
                'json.dump',
                new_callable=unittest.mock.MagicMock()
        ) as json_dump:
            translate_result_to_sarif(
                {},
                to_safe_path
            )
            json_dump.assert_called_once()

    def test_translate_result_to_sarif_non_empty_result(self):
        """
        The test that an empty path writes nothing.
        """
        to_safe_path = unittest.mock.MagicMock()
        to_safe_path.open = unittest.mock.MagicMock()
        coguard_output = {
            "failed": [
                {
                    "rule": {
                        "name": "kerberos_default_tgs_enctypes",
                        "severity": 3,
                        "documentation": {
                            "documentation": "One should avoid the legacy TGS...",
                            "remediation": "`libdefaults` has a key called ...",
                            "sources": [
                                ("https://web.mit.edu/kerberos/krb5-1.12/"
                                 "doc/admin/conf_files/krb5_conf.html")
                            ]
                        }
                    },
                    "fromLine": 0,
                    "toLine": 1,
                    "machine": "Azure-VM-1",
                    "service": "Kerberos Client",
                    "config_file": {
                        "fileName": "krb5.conf",
                        "subPath": ".",
                        "configFileType": "krb"
                    }
                },
                {
                    "rule": {
                        "name": "kerberos_default_tgs_enctypes",
                        "severity": 3,
                        "documentation": {
                            "documentation": "One should avoid the legacy TGS ...",
                            "remediation": "`libdefaults` has a key called ...",
                            "sources": [
                                ("https://web.mit.edu/kerberos/krb5-1.12/doc/"
                                 "admin/conf_files/krb5_conf.html")
                            ]
                        }
                    },
                    "fromLine": 0,
                    "toLine": 1,
                    "machine": "Azure-VM-Kerberos",
                    "service": "Kerberos Server",
                    "config_file": {
                        "fileName": "krb5.conf",
                        "subPath": ".",
                        "configFileType": "krb"
                    }
                }
            ]
        }
        try:
            coguard_version = version("coguard-cli")
        except PackageNotFoundError:
            coguard_version = "0.0.0"
        with unittest.mock.patch(
                'json.dump',
                new_callable= unittest.mock.MagicMock()
        ) as json_dump:
            translate_result_to_sarif(
                coguard_output,
                to_safe_path
            )
            # pylint: disable=unnecessary-dunder-call
            json_dump.assert_called_once_with(
                {
                    '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',
                    'version': '2.1.0',
                    'runs': [
                        {
                            'tool': {
                                'driver': {
                                    'name': 'CoGuard',
                                    'version': f'{coguard_version}',
                                    "informationUri": "https://www.coguard.io",
                                    'rules': [
                                        {
                                            'id': 'kerberos_default_tgs_enctypes',
                                            'name': 'kerberos_default_tgs_enctypes',
                                            'shortDescription': {
                                                'text': 'kerberos_default_tgs_enctypes'
                                            },
                                            'fullDescription': {
                                                'text': ('One should avoid the '
                                                         'legacy TGS...')
                                            },
                                            'defaultConfiguration': {
                                                'level': 'warning'
                                            },
                                            'properties': {
                                                'severity': 3,
                                                'security-severity': '5.0'
                                            }
                                        }
                                    ]
                                }
                            },
                            'results': [
                                {'ruleId': 'kerberos_default_tgs_enctypes',
                                 'level': 'warning',
                                 'message': {
                                     'text': (
                                         'Description: One should '
                                         'avoid the legacy TGS...\n        '
                                         'Remediation: `libdefaults` has a '
                                         'key called ...\n        Sources: \n '
                                         '- https://web.mit.edu/kerberos/krb5-'
                                         '1.12/doc/admin/conf_files/'
                                         'krb5_conf.html'
                                     )
                                 },
                                 'locations': [
                                     {'physicalLocation': {
                                         'artifactLocation': {
                                             'uri': 'krb5.conf'
                                         },
                                         'region': {
                                             'startLine': 1, 'endLine': 2
                                         }
                                    }}]
                                },
                                {
                                    'ruleId': 'kerberos_default_tgs_enctypes',
                                    'level': 'warning',
                                    'message': {
                                        'text': ('Description: One should avoid the '
                                                 'legacy TGS ...\n        Remediation: '
                                                 '`libdefaults` has a key called ...\n        '
                                                 'Sources: \n - https://web.mit.edu/kerberos/'
                                                 'krb5-1.12/doc/admin/conf_files/krb5_conf.html')
                                    },
                                    'locations': [
                                        {
                                            'physicalLocation': {
                                                'artifactLocation': {
                                                    'uri': 'krb5.conf'
                                                },
                                                'region': {
                                                    'startLine': 1, 'endLine': 2
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                to_safe_path.open().__enter__(),
                indent=2
            )
