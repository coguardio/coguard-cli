"""
This is the module containing checks for the common functions in the
CoGuard CLI module.
"""

import unittest
import unittest.mock
from io import StringIO
from coguard_cli import print_failed_check, COLOR_RED, output_result_json_from_coguard

class TestCommonFunctions(unittest.TestCase):
    """
    The class to test the functions in coguard_cli.__init__
    """

    def print_failed_check_test(self):
        """
        Prints a failed check entry.
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            print_failed_check(COLOR_RED, {
                "rule": {
                    "name": "foo_bar_baz",
                    "severity": 5,
                    "documentation": "Let's not even talk about it"
                }
            })
            self.assertIn("not even talk", new_stdout.getvalue())

    def print_output_result_json_from_coguard_test(self):
        """
        Prints a failed check entry.
        """
        new_stdout = StringIO()
        result_json = {
            "failed": [
                {
                    "rule": {
                        "name": "kerberos_default_tgs_enctypes",
                        "severity": 3,
                        "documentation": "libdefaults has a key called \"default_tgs_enctypes\". If this value is set, custom cryptographic mechanisms are set instead of default secure ones. The value should only be set for legacy systems.\nSource: https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html"
                    },
                    "machine": "us-jfk-001",
                    "service": "Kerberos"
                },
                {
                    "rule": {
                        "name": "kerberos_dns_lookup_kdc",
                        "severity": 1,
                        "documentation": "libdefaults has a key called \"dns_lookup_kdc\". If this value is set to true, the local DNS server is used to look up KDCs and other servers in the realm. Setting this value to true opens up a type of denial of service attack.\nSource: https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html"
                    },
                    "machine": "us-jfk-001",
                    "service": "Kerberos"
                },
                {
                    "rule": {
                        "name": "nginx_server_tokens_off",
                        "severity": 2,
                        "documentation": "Knowing what NGINX version you are running may make you vulnerable if there is a known vulnerability for a specific version. There is a parameter to turn the display of the version on the error pages off. Our checking mechanism looks into each http-directive and ensures it is disabled on the top level.\nRemediation: Set `server_tokens` to `off` on the http-level of the configuration.\nSource: https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_one_root_outside_of_location_block",
                        "severity": 1,
                        "documentation": "One can define a root directory inside of a location block. However, one also needs a root directory for all directives that do not match any given location.\nRemediation: Either have a top-level root directive, or ensure that there is one in every `location` directive.\nSource: https://www.nginx.com/resources/wiki/start/topics/tutorials/config_pitfalls/"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_upstream_servers_https",
                        "severity": 4,
                        "documentation": "NGINX is popular to be used as load balancer. The communication to the upstream servers should exclusively be done via HTTPS, because otherwise there is unencrypted communication going on.\nRemediation: Every server in the upstream directive should be starting with `https://`."
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_avoid_if_directives",
                        "severity": 1,
                        "documentation": "NGINX has an article called \"If is Evil\". Even though it is possible that there are uses where if makes sense, but in general, one should avoid using it.\nRemediation: Do not use the `if`-directive anywhere in your configuration file.\nSource: https://www.nginx.com/resources/wiki/start/topics/tutorials/config_pitfalls/\nhttps://www.nginx.com/resources/wiki/start/topics/depth/ifisevil/"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                }
            ]
        }
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            output_result_json_from_coguard(result_json)
            self.assertIn("1 High", new_stdout.getvalue())
            self.assertIn("1 Medium", new_stdout.getvalue())
            self.assertIn("4 Low", new_stdout.getvalue())
