"""
The test module for the sarif output generator.
"""

import unittest
import unittest.mock
import pathlib
from coguard_cli.output_generators.output_generator_markdown import \
    translate_result_to_markdown

class TestTranslateToMarkdown(unittest.TestCase):
    """
    The unit tests for the output generator Markdown module.
    """

    def test_translate_result_to_markdown_empty_path(self):
        """
        The test that an empty path will throw an exception.
        """
        with self.assertRaises(ValueError):
            translate_result_to_markdown(
                {},
                "",
                ""
            )
        with self.assertRaises(ValueError):
            translate_result_to_markdown(
                {},
                "",
                None
            )

    def test_translate_result_to_markdown_none_result(self):
        """
        The test that an empty path will throw an exception.
        """
        with self.assertRaises(ValueError):
            translate_result_to_markdown(
                None,
                "foo",
                pathlib.Path("foo")
            )

    def test_translate_result_to_markdown_empty_result(self):
        """
        The test that an empty path writes nothing.
        """
        with unittest.mock.patch(
                'pathlib.Path.open',
                unittest.mock.mock_open()
        ) as write_res:
            translate_result_to_markdown(
                {},
                "foo",
                pathlib.Path("foo")
            )
            write_res().write.assert_called_once()

    def test_translate_result_to_markdown_non_empty_result(self):
        """
        The test that an empty path writes nothing.
        """
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
        with unittest.mock.patch(
                'pathlib.Path.open',
                unittest.mock.mock_open()
        ) as write_op, \
        unittest.mock.patch(
            'importlib.metadata.version',
            new_callable=lambda: lambda x: "0.0.0"
        ):
            translate_result_to_markdown(
                coguard_output,
                "foo",
                pathlib.Path("bar")
            )
            # pylint: disable=unnecessary-dunder-call
            write_op().write.assert_called_once_with(
                """
# CoGuard evaluation of `foo`
CoGuard CLI version: 0.0.0
# Findings

## kerberos_default_tgs_enctypes
**Severity:** 3

One should avoid the legacy TGS...

**Remediation:**

`libdefaults` has a key called ...


**Sources:**

 - https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html

**Affected files:**

 - ./krb5.conf
""")

    def test_translate_result_to_markdown_non_empty_result_compliance(self):
        """
        The test that an empty path writes nothing.
        """
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
                            ],
                            "scenarios": [
                                "example_scenario"
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
                            ],
                            "scenarios": [
                                "example_scenario"
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
        with unittest.mock.patch(
                'pathlib.Path.open',
                unittest.mock.mock_open()
        ) as write_op, \
        unittest.mock.patch(
            'importlib.metadata.version',
            new_callable=lambda: lambda x: "0.0.0"
        ):
            translate_result_to_markdown(
                coguard_output,
                "foo",
                pathlib.Path("bar")
            )
            # pylint: disable=unnecessary-dunder-call
            write_op().write.assert_called_once_with(
                f"""
# CoGuard evaluation of `foo`
CoGuard CLI version: 0.0.0
# Findings

## kerberos_default_tgs_enctypes
**Severity:** 3

One should avoid the legacy TGS...

**Remediation:**

`libdefaults` has a key called ...

**References for your specific requirements:**

 - example_scenario

**Sources:**

 - https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html

**Affected files:**

 - ./krb5.conf
""")
