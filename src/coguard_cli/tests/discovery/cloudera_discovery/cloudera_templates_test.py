"""
Tests for the functions in the cloudera_templates module. The templates and the
expected renderings are taken from a Cloudera Runtime 7.3.2 cluster: the files
as listed by Cloudera Manager, and the files the control scripts rendered from
them on the host.
"""

import json
import unittest
import unittest.mock
import yaml
from coguard_cli.discovery.cloudera_discovery.cloudera_templates import \
    TemplateContext, neutralize_placeholders, render_template

KERBEROS_PROVIDERS_TEMPLATE = """{
  "providers": [
    {
      "role": "authentication",
      "name": "HadoopAuth",
      "enabled": "true",
      "params": {
        "hadoop.auth.config.type": "kerberos",
        "PROXYUSER_BLOCK",
        "hadoop.auth.config.kerberos.principal": "AUTH_CONFIG_KERBEROS_PRINCIPAL",
        "hadoop.auth.config.kerberos.keytab": "AUTH_CONFIG_KERBEROS_KEYTAB",
        "hadoop.auth.config.kerberos.name.rules": "AUTH_TO_LOCAL_RULES"
      }
    },
    {
       "role": "identity-assertion",
       "name": "HadoopGroupProvider",
       "enabled": "true",
       "params": {
          "CENTRAL_GROUP_CONFIG_PREFIX": "gateway.group.config."
       }
    }
  ]
}"""

KNOXSSO_DESCRIPTOR_TEMPLATE = """{
   "provider-config-ref": "knoxsso",
   "services": [
      {
        "name": "KNOXSSO",
        "params": {
            "knoxsso.token.ttl": "SSO_TOKEN_TTL",
            "knoxsso.token.sigalg": "TOKEN_SIGNATURE_ALGORITHM",
            "knoxsso.redirect.whitelist.regex": "KNOXSSO_REDIRECT_WHITELIST_REGEX",
            "knoxsso.cookie.samesite": "KNOX_SSO_COOKIE_SAMESITE",
            "knox.token.exp.server-managed": "KNOX_SSO_COOKIE_MANAGEMENT_ENABLED"
         }
      }
   ]
}"""

OZONE_PROMETHEUS_TEMPLATE = """global:
  scrape_interval: {{SCRAPE_INTERVAL}} # Set the scrape interval.
scrape_configs:
  - job_name: 'ozone'
    scheme: {{SCHEME}}
    tls_config:
      ca_file: {{CA_FILE}}
      insecure_skip_verify: false
    bearer_token_file: {{TOKEN_FILE}}
    metrics_path: /prom
    static_configs:
      - targets:
{{TARGETS}}"""

PROMETHEUS_WEB_TEMPLATE = """{{TLS_SERVER_CONFIG}}

http_server_config:
  http2: false
"""

KNOX_ROLE = {
    "name": "knox-KNOX_GATEWAY-1",
    "roleConfigGroupRef": {"roleConfigGroupName": "knox-KNOX_GATEWAY-BASE"},
    "hostRef": {"hostId": "1", "hostname": "sdx-01.cldr.internal"}
}

AUTH_TO_LOCAL_RULES = (
    "RULE:[2:$1@$0](atlas@CLDR.INTERNAL)s/(.*)@CLDR.INTERNAL/atlas/\\nDEFAULT"
)


def _mock_api(role_config=None, group_config=None, service_config=None,
              role_config_groups=None):
    api = unittest.mock.MagicMock()
    api.get_role_config.return_value = role_config or {}
    api.get_role_config_group_config.return_value = group_config or {}
    api.get_service_config.return_value = service_config or {}
    api.list_role_config_groups.return_value = role_config_groups or []
    api.get_config_file.return_value = None
    api.get_cloudera_manager_config.return_value = {
        "SECURITY_REALM": {"value": "CLDR.INTERNAL"}
    }
    return api


def _context(api, role_files=None, role=None, service_name="knox"):
    return TemplateContext(api, "cluster", service_name, role or KNOX_ROLE,
                           role_files or {})


class TestClouderaTemplates(unittest.TestCase):
    """
    The class for testing the Cloudera template rendering module
    """

    def test_parameter_most_specific_level_wins(self):
        """
        A value set on the role beats the one set on its group, which beats the
        one set on the service, and a default only applies where nothing is set.
        """
        api = _mock_api(
            role_config={"a": {"value": "role", "default": "d"},
                         "b": {"default": "d"},
                         "c": {"default": "d"},
                         "d": {"default": "role-default"}},
            group_config={"b": {"value": "group"}, "c": {"default": "d"}},
            service_config={"c": {"value": "service"}}
        )
        context = _context(api)
        self.assertEqual(context.parameter("a"), "role")
        self.assertEqual(context.parameter("b"), "group")
        self.assertEqual(context.parameter("c"), "service")
        self.assertEqual(context.parameter("d"), "role-default")
        self.assertIsNone(context.parameter("unknown"))
        api.get_role_config_group_config.assert_called_once_with(
            "cluster", "knox", "knox-KNOX_GATEWAY-BASE"
        )
        # The levels are only retrieved once.
        api.get_role_config.assert_called_once()

    def test_parameter_of_other_role_type(self):
        """
        A parameter of another role type is read from the base group of that
        type, even if no role of the type exists.
        """
        api = _mock_api(
            role_config_groups=[
                {"name": "ozone-OZONE_PROMETHEUS-custom",
                 "roleType": "OZONE_PROMETHEUS", "base": False},
                {"name": "ozone-OZONE_PROMETHEUS-BASE",
                 "roleType": "OZONE_PROMETHEUS", "base": True}
            ],
            group_config={"ozone.prometheus.scrape.interval": {"default": "15s"}}
        )
        context = _context(api, service_name="ozone")
        self.assertEqual(
            context.parameter("ozone.prometheus.scrape.interval",
                              "OZONE_PROMETHEUS"),
            "15s"
        )
        api.get_role_config_group_config.assert_called_once_with(
            "cluster", "ozone", "ozone-OZONE_PROMETHEUS-BASE"
        )
        api.get_role_config.assert_not_called()

    def test_render_knox_kerberos_providers(self):
        """
        The Kerberos provider of Knox is rendered like `setupKerberos.sh` does.
        """
        # The parameter as Cloudera Manager reports it, enclosing quotes and all.
        api = _mock_api(service_config={"hadoop_proxyuser_block": {
            "default": '"hadoop.proxyuser.changeme.hosts": "NONE",'
                       '"hadoop.proxyuser.changeme.groups": "NONE"'
        }})
        context = _context(api, role_files={
            "conf/kerberos_auth_to_local_rules.properties":
                f"kerberos.auth.to.local.rules={AUTH_TO_LOCAL_RULES}\n"
        })
        result = render_template("KNOX",
                                 "aux/shared-providers/kerberos-providers.json",
                                 KERBEROS_PROVIDERS_TEMPLATE,
                                 context)
        params = json.loads(result)["providers"][0]["params"]
        self.assertEqual(params["hadoop.proxyuser.changeme.hosts"], "NONE")
        self.assertEqual(params["hadoop.auth.config.kerberos.principal"],
                         "HTTP/sdx-01.cldr.internal@CLDR.INTERNAL")
        self.assertEqual(params["hadoop.auth.config.kerberos.keytab"],
                         "{{CMF_CONF_DIR}}/knox.keytab")
        self.assertEqual(
            params["hadoop.auth.config.kerberos.name.rules"],
            AUTH_TO_LOCAL_RULES.replace("\\n", "\n")
        )
        # A token the scripts do not replace is left for Knox to resolve.
        self.assertIn('"CENTRAL_GROUP_CONFIG_PREFIX"', result)

    def test_render_knox_removes_line_of_empty_value(self):
        """
        A placeholder whose value is empty has its line removed, as
        `replaceOrRemovePattern` does.
        """
        api = _mock_api(group_config={"hadoop_proxyuser_block": {"default": ""}})
        api.get_cloudera_manager_config.return_value = {}
        result = render_template("KNOX",
                                 "aux/shared-providers/kerberos-providers.json",
                                 KERBEROS_PROVIDERS_TEMPLATE,
                                 _context(api))
        self.assertNotIn("PROXYUSER_BLOCK", result)
        # Neither the rules nor the realm of the principal are known, so those
        # lines go too.
        self.assertNotIn("AUTH_TO_LOCAL_RULES", result)
        self.assertNotIn("AUTH_CONFIG_KERBEROS_PRINCIPAL", result)
        # Like on the host, the last parameter leaves a comma behind, which is
        # what the neutralization of a file which does not parse takes care of.
        params = json.loads(
            neutralize_placeholders(result, "json")
        )["providers"][0]["params"]
        self.assertEqual(params["hadoop.auth.config.type"], "kerberos")

    def test_render_knox_knoxsso_descriptor(self):
        """
        The KnoxSSO descriptor carries the service level parameters, the
        redirect whitelist with the domain of the host and JSON escaping, and an
        empty signature algorithm, which no parameter defines.
        """
        api = _mock_api(service_config={
            "knoxsso_token_ttl": {"default": "86400000"},
            "knoxsso_cookie_samesite": {"default": "Lax"},
            "knoxsso_cookie_management_enabled": {"default": "false"},
            "knoxsso_redirect_whitelist_regex": {
                "default": "^https?:\\/\\/(.*KNOX_GW_DOMAIN)(?::[0-9]+)?$"
            }
        })
        result = render_template("KNOX",
                                 "aux/descriptors/knoxsso.json",
                                 KNOXSSO_DESCRIPTOR_TEMPLATE,
                                 _context(api))
        self.assertIn(
            '"knoxsso.redirect.whitelist.regex": '
            '"^https?:\\\\/\\\\/(.*cldr\\\\.internal)(?::[0-9]+)?$"',
            result
        )
        params = json.loads(result)["services"][0]["params"]
        self.assertEqual(params, {
            "knoxsso.token.ttl": "86400000",
            "knoxsso.token.sigalg": "",
            "knoxsso.redirect.whitelist.regex":
                "^https?:\\/\\/(.*cldr\\.internal)(?::[0-9]+)?$",
            "knoxsso.cookie.samesite": "Lax",
            "knox.token.exp.server-managed": "false"
        })

    def test_render_knox_only_for_knox(self):
        """
        The Knox tables do not apply to a file of the same name of another
        service.
        """
        result = render_template("ATLAS",
                                 "aux/descriptors/knoxsso.json",
                                 KNOXSSO_DESCRIPTOR_TEMPLATE,
                                 _context(_mock_api()))
        self.assertEqual(result, KNOXSSO_DESCRIPTOR_TEMPLATE)

    def test_render_ozone_prometheus_config(self):
        """
        The Ozone Prometheus configuration is rendered like
        `prometheus_config_utils.sh` does, with the targets taken from the peer
        files of the role.
        """
        api = _mock_api(
            role_config_groups=[{"name": "ozone-OZONE_PROMETHEUS-BASE",
                                 "roleType": "OZONE_PROMETHEUS", "base": True}],
            group_config={
                "ozone.prometheus.scrape.interval": {"default": "15s"},
                "ozone.prometheus.ca.file": {"default": "{{AUTO_TLS_CA_FILE}}"},
                "ssl_enabled": {"value": "true", "default": "false"}
            }
        )
        context = _context(api, service_name="ozone", role_files={
            "ozone-conf/ozone-om.properties":
                "om-1:om.id=1\nom-1:ozone.om.https-port=9875\n"
                "om-2:ozone.om.https-port=9875\nom-2:ozone.om.http-port=9874\n",
            "ozone-conf/ozone-recon.properties":
                "recon-1:ozone.recon.https-port=9889\n",
        })
        result = render_template("OZONE", "aux/ozone-prometheus.yml",
                                 OZONE_PROMETHEUS_TEMPLATE, context)
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["global"]["scrape_interval"], "15s")
        scrape_config = parsed["scrape_configs"][0]
        self.assertEqual(scrape_config["scheme"], "https")
        self.assertEqual(scrape_config["tls_config"]["ca_file"],
                         "{{CMF_CONF_DIR}}/cm-auto-global_cacerts.pem")
        self.assertEqual(scrape_config["bearer_token_file"],
                         "{{CMF_CONF_DIR}}/ozone-conf/prometheus-token")
        self.assertEqual(scrape_config["static_configs"][0]["targets"],
                         ["om-1:9875", "om-2:9875", "recon-1:9889"])

    def test_render_ozone_prometheus_config_without_tls(self):
        """
        Without TLS, the scrape targets are the HTTP ports and there is no CA,
        and the interval falls back to the Prometheus default.
        """
        api = _mock_api(role_config_groups=[])
        context = _context(api, service_name="ozone", role_files={
            "ozone-conf/ozone-site.xml":
                "<property><name>ozone.ssl.enabled</name>"
                "<value>false</value></property>",
            "ozone-conf/ozone-om.properties":
                "om-1:ozone.om.https-port=9875\nom-1:ozone.om.http-port=9874\n",
        })
        parsed = yaml.safe_load(render_template(
            "OZONE", "aux/ozone-prometheus.yml", OZONE_PROMETHEUS_TEMPLATE,
            context
        ))
        self.assertEqual(parsed["global"]["scrape_interval"], "1m")
        scrape_config = parsed["scrape_configs"][0]
        self.assertEqual(scrape_config["scheme"], "http")
        self.assertIsNone(scrape_config["tls_config"]["ca_file"])
        self.assertEqual(scrape_config["static_configs"][0]["targets"],
                         ["om-1:9874"])

    def test_render_ozone_prometheus_web_config(self):
        """
        With TLS, the web configuration of Prometheus gets the server TLS
        section, with the Prometheus default protocol versions and ciphers.
        """
        api = _mock_api(
            role_config_groups=[{"name": "ozone-OZONE_PROMETHEUS-BASE",
                                 "roleType": "OZONE_PROMETHEUS", "base": True}],
            group_config={
                "ssl_enabled": {"value": "true"},
                "ssl_server_certificate_location": {"value": "/certs/cert.pem"},
                "ssl_server_privatekey_location": {"value": "/certs/key.pem"},
            }
        )
        parsed = yaml.safe_load(render_template(
            "OZONE", "aux/prometheus-web.yml", PROMETHEUS_WEB_TEMPLATE,
            _context(api, service_name="ozone")
        ))
        self.assertEqual(parsed["tls_server_config"], {
            "cert_file": "/certs/cert.pem",
            "key_file": "/certs/decrypted-server-private-key.pem",
            "min_version": "TLS12",
            "max_version": "TLS13",
            "cipher_suites": []
        })
        self.assertEqual(parsed["http_server_config"], {"http2": False})

    def test_render_ozone_prometheus_web_config_without_tls(self):
        """
        Without TLS, the TLS section is omitted, which disables it.
        """
        api = _mock_api(
            role_config_groups=[{"name": "ozone-OZONE_PROMETHEUS-BASE",
                                 "roleType": "OZONE_PROMETHEUS", "base": True}],
            group_config={"ssl_enabled": {"default": "false"}}
        )
        parsed = yaml.safe_load(render_template(
            "OZONE", "aux/prometheus-web.yml", PROMETHEUS_WEB_TEMPLATE,
            _context(api, service_name="ozone")
        ))
        self.assertEqual(parsed, {"http_server_config": {"http2": False}})

    def test_idbroker_descriptors_are_left_to_the_neutral_values(self):
        """
        The descriptors of the IDBroker, which the Knox gateway ships but never
        deploys, are not rendered, and become readable through the neutral
        values instead.
        """
        template = (
            '{\n  "params": {\n    "a": "b",\n    "PROXYUSER_BLOCK",\n'
            '    "c": "TOKEN_STATE_ENABLED"\n  }\n}'
        )
        api = _mock_api()
        result = render_template("KNOX",
                                 "aux/shared-providers/cab-providers.json",
                                 template,
                                 _context(api))
        self.assertEqual(result, template)
        api.get_role_config.assert_not_called()
        self.assertEqual(
            json.loads(neutralize_placeholders(result, "json")),
            {"params": {"a": "b", "c": "TOKEN_STATE_ENABLED"}}
        )

    def test_render_unknown_file_unchanged(self):
        """
        A file no renderer knows is returned as it is.
        """
        self.assertEqual(
            render_template("OZONE", "ozone-conf/ozone-site.xml", "a{{B}}",
                            _context(_mock_api())),
            "a{{B}}"
        )

    def test_neutralize_placeholders_json_block(self):
        """
        A block placeholder is removed from a JSON file, together with the comma
        it leaves dangling.
        """
        result = neutralize_placeholders(
            '{\n  "params": {\n    "cloud.client.provider": "ADLS2",\n'
            '    CUSTOMIZABLE_AZURE_CAB_CONTENT\n  }\n}',
            "json"
        )
        self.assertEqual(json.loads(result),
                         {"params": {"cloud.client.provider": "ADLS2"}})

    def test_neutralize_placeholders_yaml(self):
        """
        In YAML, a placeholder standing in for a block is removed, and an inline
        one becomes a string, while a quoted one is left as it is.
        """
        result = neutralize_placeholders(
            "{{TLS_CONFIG}}\na: {{VALUE}} # comment\nb: \"{{QUOTED}}\"\n",
            "yaml"
        )
        self.assertEqual(yaml.safe_load(result),
                         {"a": "{{VALUE}}", "b": "{{QUOTED}}"})
