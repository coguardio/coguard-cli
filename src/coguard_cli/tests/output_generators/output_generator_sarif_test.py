"""
The test module for the sarif output generator.
"""

import unittest
import unittest.mock
from coguard_cli.output_generators.output_generator_sarif import \
    translate_result_to_sarif
from importlib.metadata import version, PackageNotFoundError

class TestTranslateToSarif(unittest.TestCase):
    """
    The unit tests for the output generator Sarif module.
    """

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
                                    'rules': []
                                }
                            },
                            'results': [
                                {'ruleId': 'kerberos_default_tgs_enctypes',
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
