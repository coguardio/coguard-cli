"""
This module renders the configuration files Cloudera Manager hands out as
templates, i.e. with placeholders which a control script of the role fills in on
the host before the process reads the file.

Cloudera Manager does not expose the rendered files, nor the environment the
control scripts run in, through its API. What it does expose is the configuration
the environment is made of: a service descriptor defines every environment
variable of a role as a configuration parameter, `HADOOP_PROXYUSER_BLOCK` as
`${hadoop_proxyuser_block}` for instance. The renderers below hence repeat what
the control scripts do, with the values taken from the configuration parameters
the scripts' environment is defined by. Where a script computes a value which no
parameter carries, a neutral value is used instead, and whatever placeholder is
left after that is handled by :func:`neutralize_placeholders`.

Every template is rendered the same way: :data:`TEMPLATES` names the
placeholders of the file, and where the value of each comes from, and
:func:`apply_substitutions` replaces them the way the scripts do with `sed`.
That is also why a template engine such as mustache is not used: the scripts do
not render the files as templates, they replace a known set of tokens and leave
everything else alone, including the `{{CMF_CONF_DIR}}` the agent expands later
and the bare tokens Knox resolves itself.

The tables are a transcription of the control scripts of the Knox and Ozone
service descriptors as shipped with Cloudera Manager 7.13 (`KNOX_C730` and
`OZONE_C730`, `scripts/deployTopologies.sh`, `scripts/setupKerberos.sh`,
`scripts/setupAutoDiscovery.sh`, `scripts/setupRanger.sh` and
`scripts/prometheus_config_utils.sh`). The descriptors of the Knox IDBroker,
which the gateway ships but never deploys, are left to the neutral values.
"""

import json
import logging
import posixpath
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi

# The role type whose configuration the Prometheus templates the Ozone roles ship
# draw on. It is looked up via the base role config group of the type, which
# exists whether or not such a role was added.
OZONE_PROMETHEUS_ROLE_TYPE = "OZONE_PROMETHEUS"

# The value Cloudera Manager uses for "the CA bundle Auto-TLS distributes", and
# the location the Ozone control script resolves it to.
AUTO_TLS_CA_FILE = "{{AUTO_TLS_CA_FILE}}"
AUTO_TLS_CA_FILE_LOCATION = "{{CMF_CONF_DIR}}/cm-auto-global_cacerts.pem"

# The Prometheus scrape interval which applies if none is configured.
PROMETHEUS_DEFAULT_SCRAPE_INTERVAL = "1m"

# The template of the `tls_server_config` section of the Prometheus web
# configuration, as shipped in `aux/templates/prometheus-tls-config.yml`. It is
# used if the role does not list the file.
PROMETHEUS_TLS_CONFIG_TEMPLATE = """tls_server_config:
  cert_file: "{{SERVER_CERT}}"
  key_file: "{{DECRYPTED_KEY}}"
  min_version: "{{SERVER_MIN_TLS_VERSION}}"
  max_version: "{{SERVER_MAX_TLS_VERSION}}"
  cipher_suites: {{SERVER_CIPHER_SUITES}}"""

# A placeholder which takes up a line of its own, standing in for a block, and an
# inline mustache placeholder which is not quoted.
WHOLE_LINE_PLACEHOLDER = re.compile(
    r'^[ \t]*(?:\{\{[A-Z][A-Z0-9_]*\}\}|"?[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+"?)'
    r'[ \t]*,?[ \t]*(?:\n|$)',
    re.MULTILINE
)
UNQUOTED_MUSTACHE_PLACEHOLDER = re.compile(
    r'(?<!["\'])(\{\{[A-Z][A-Z0-9_]*\}\})(?!["\'])'
)
# A comma which a removed line has left dangling in front of a closing bracket.
DANGLING_JSON_COMMA = re.compile(r",(\s*[}\]])")


class TemplateContext:
    """
    What a renderer may consult about the role a template belongs to. Every
    lookup is done on first use and cached, so that the roles which do not ship
    a template do not cost a single additional request.
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(self,
                 api: ClouderaManagerApi,
                 cluster_name: str,
                 service_name: str,
                 role: Dict,
                 role_files: Dict[str, str]):
        self._api = api
        self._cluster_name = cluster_name
        self._service_name = service_name
        self._role = role
        self._role_files = role_files
        self._cache: Dict = {}

    def _cached(self, key, compute: Callable):
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def _layers(self, role_type: Optional[str]) -> List[Dict[str, Dict]]:
        """
        The configuration levels a parameter is looked up in, most specific
        first: the role, its role config group and the service, or, for another
        role type, the base role config group of that type and the service.
        """
        def compute():
            api, cluster, service = \
                self._api, self._cluster_name, self._service_name
            layers = []
            if role_type is None:
                layers.append(api.get_role_config(cluster, service,
                                                  self._role.get("name")))
                group_name = (self._role.get("roleConfigGroupRef") or {}).get(
                    "roleConfigGroupName"
                )
            else:
                group_name = next(
                    (group.get("name")
                     for group in api.list_role_config_groups(cluster, service)
                     if group.get("roleType") == role_type and group.get("base")),
                    None
                )
            if group_name:
                layers.append(api.get_role_config_group_config(cluster, service,
                                                               group_name))
            layers.append(self._cached(
                "service", lambda: api.get_service_config(cluster, service)
            ))
            return layers
        return self._cached(("layers", role_type), compute)

    def parameter(self,
                  name: str,
                  role_type: Optional[str] = None) -> Optional[str]:
        """
        The effective value of a configuration parameter: the value set at the
        most specific level, or, if it is set nowhere, its default.
        """
        layers = self._layers(role_type)
        for key in ("value", "default"):
            for layer in layers:
                if key in layer.get(name, {}):
                    return layer[name][key]
        return None

    def host_name(self) -> Optional[str]:
        """
        The fully qualified name of the host the role runs on.
        """
        return (self._role.get("hostRef") or {}).get("hostname")

    def kerberos_realm(self) -> Optional[str]:
        """
        The Kerberos realm Cloudera Manager creates principals in.
        """
        realm = self._cached(
            "cloudera manager", self._api.get_cloudera_manager_config
        ).get("SECURITY_REALM", {})
        return realm.get("value", realm.get("default"))

    def file(self, config_file_name: str) -> Optional[str]:
        """
        The content of another configuration file of the role, retrieved if it
        is not among the files collected anyway.
        """
        if config_file_name in self._role_files:
            return self._role_files[config_file_name]
        return self._cached(("file", config_file_name), lambda: \
            self._api.get_config_file(self._cluster_name, self._service_name,
                                      self._role.get("name"), config_file_name))

    def file_names(self) -> List[str]:
        """
        The names of the configuration files collected for the role.
        """
        return list(self._role_files)


@dataclass(frozen=True)
class Substitution:
    """
    One placeholder a control script replaces, and how its value is determined.
    `remove_line_if_empty` mirrors
    the `replaceOrRemovePattern` helper of the Knox scripts, which deletes the
    line of a placeholder whose value is empty rather than leaving an empty
    value behind; a plain `sed` substitution leaves the empty value.
    """
    token: str
    value: Callable[[TemplateContext], Optional[str]]
    remove_line_if_empty: bool = True


def environment_value(value: Optional[str]) -> Optional[str]:
    """
    The value a configuration parameter takes on in the environment of a control
    script. One pair of enclosing double quotes does not make it there: the
    proxy user block of Knox is configured as `"a": "NONE","b": "NONE"`, and
    rendered into `"PROXYUSER_BLOCK",` it yields `"a": "NONE","b": "NONE",` on
    the host.
    """
    if value and len(value) >= 2 and value.startswith('"') \
       and value.endswith('"'):
        return value[1:-1]
    return value


def _parameter(name: str,
               role_type: Optional[str] = None
               ) -> Callable[[TemplateContext], Optional[str]]:
    return lambda context: environment_value(context.parameter(name, role_type))


def _constant(value: str) -> Callable[[TemplateContext], Optional[str]]:
    return lambda _: value


def _knox_spnego_principal(context: TemplateContext) -> Optional[str]:
    # The descriptor declares the principal as `HTTP/${host}` in the realm of
    # the cluster.
    host_name = context.host_name()
    realm = context.kerberos_realm()
    if not host_name or not realm:
        return None
    return f"HTTP/{host_name}@{realm}"


def _knox_auth_to_local_rules(context: TemplateContext) -> Optional[str]:
    # `setupKerberos.sh` takes the value of `kerberos.auth.to.local.rules` from
    # the properties file the role ships, and escapes it for a JSON string.
    content = context.file("conf/kerberos_auth_to_local_rules.properties") or ""
    for line in content.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "kerberos.auth.to.local.rules":
            return value.replace('"', '\\"')
    return None


def _knoxsso_redirect_whitelist(context: TemplateContext) -> Optional[str]:
    # `deployTopologies.sh` puts the domain of the host in the place of
    # `KNOX_GW_DOMAIN`, and doubles every backslash for the JSON string.
    regex = environment_value(
        context.parameter("knoxsso_redirect_whitelist_regex")
    )
    if regex is None:
        return None
    host_name = context.host_name() or ""
    if "KNOX_GW_DOMAIN" in regex and "." in host_name:
        domain = host_name.split(".", 1)[1]
        regex = regex.replace("KNOX_GW_DOMAIN", domain.replace(".", "\\."))
    return json.dumps(regex)[1:-1]


def _knox_gateway_url(context: TemplateContext) -> Optional[str]:
    # The descriptor defines `KNOX_GATEWAY_URL` as
    # `https://${host}:${gateway_port}/${gateway_path}`.
    host_name = context.host_name()
    if not host_name:
        return None
    return (f"https://{host_name}:{context.parameter('gateway_port')}/"
            f"{context.parameter('gateway_path')}")


def _knox_ranger_authorization_enabled(context: TemplateContext) -> str:
    # `setupRanger.sh` enables the authorization provider if, and only if, the
    # Knox service depends on a Ranger service.
    return "true" if context.parameter("ranger_service") else "false"


_KNOX_PAM_SERVICE_NAME = Substitution(
    "KNOX_PAM_SERVICE_NAME", _parameter("knox_pam_realm_service"), False
)
_KNOX_SSO_COOKIE_MANAGEMENT_ENABLED = Substitution(
    "KNOX_SSO_COOKIE_MANAGEMENT_ENABLED",
    _parameter("knoxsso_cookie_management_enabled")
)
_KNOX_RANGER_AUTH_ENABLED = Substitution(
    "RANGER_AUTH_ENABLED", _knox_ranger_authorization_enabled, False
)
_KNOX_KERBEROS = (
    Substitution("AUTH_CONFIG_KERBEROS_PRINCIPAL", _knox_spnego_principal),
    Substitution("AUTH_CONFIG_KERBEROS_KEYTAB",
                 _constant("{{CMF_CONF_DIR}}/knox.keytab")),
    Substitution("AUTH_TO_LOCAL_RULES", _knox_auth_to_local_rules),
)
# `KNOX_TOKEN_SIGNATURE_ALG` is not part of the environment the descriptor
# defines, so the scripts substitute it with an empty value.
_KNOX_TOKEN_SIGNATURE_ALGORITHM = Substitution(
    "TOKEN_SIGNATURE_ALGORITHM", _constant(""), False
)

# The substitutions of the Knox control scripts, keyed by the name of the file
# in the `configFiles` listing of a Knox role.
KNOX_TEMPLATES: Dict[str, Tuple[Substitution, ...]] = {
    "aux/shared-providers/admin.json": (_KNOX_PAM_SERVICE_NAME,),
    "aux/shared-providers/knoxsso.json": (_KNOX_PAM_SERVICE_NAME,),
    "aux/shared-providers/metadata.json": (_KNOX_PAM_SERVICE_NAME,),
    "aux/shared-providers/manager.json": (_KNOX_SSO_COOKIE_MANAGEMENT_ENABLED,),
    "aux/shared-providers/homepage.json": (
        _KNOX_SSO_COOKIE_MANAGEMENT_ENABLED,
        Substitution("KNOX_TOKEN_IMPERSONATION_ENABLED",
                     _parameter("gateway_token_generation_enable_impersonation")),
        Substitution("PROXYUSER_BLOCK", _parameter("hadoop_proxyuser_block")),
    ),
    "aux/shared-providers/kerberos-providers.json": _KNOX_KERBEROS + (
        Substitution("PROXYUSER_BLOCK", _parameter("hadoop_proxyuser_block")),
    ),
    "aux/shared-providers/pam.json": (
        _KNOX_PAM_SERVICE_NAME,
        _KNOX_RANGER_AUTH_ENABLED,
    ),
    "aux/shared-providers/sso.json": (
        Substitution("GATEWAY_URL", _knox_gateway_url, False),
        _KNOX_SSO_COOKIE_MANAGEMENT_ENABLED,
        _KNOX_RANGER_AUTH_ENABLED,
    ),
    "aux/shared-providers/tokenbased.json": (
        Substitution("KNOX_TOKEN_JWKS_URL",
                     _parameter("gateway_knox_token_jwks_url")),
        Substitution("KNOX_TOKEN_ALLOWED_JWS_TYPES",
                     _parameter("gateway_knox_token_allowed_jws_types")),
        Substitution("KNOX_TOKEN_EXPECTED_PRINCIPAL_CLAIM",
                     _parameter("gateway_knox_token_expected_principal_claim")),
        Substitution("KNOX_TOKEN_EXPECTED_JWT_SIGNATURE_ALG",
                     _parameter(
                         "gateway_knox_token_expected_jwt_signature_algorithm"
                     )),
        Substitution("KNOX_TOKEN_EXPECTED_JWT_ISSUER",
                     _parameter("gateway_knox_token_expected_jwt_issuer")),
        _KNOX_RANGER_AUTH_ENABLED,
    ),
    "aux/descriptors/knoxsso.json": (
        Substitution("SSO_TOKEN_TTL", _parameter("knoxsso_token_ttl"), False),
        _KNOX_TOKEN_SIGNATURE_ALGORITHM,
        Substitution("KNOXSSO_REDIRECT_WHITELIST_REGEX",
                     _knoxsso_redirect_whitelist,
                     False),
        Substitution("KNOX_SSO_COOKIE_SAMESITE",
                     _parameter("knoxsso_cookie_samesite")),
        _KNOX_SSO_COOKIE_MANAGEMENT_ENABLED,
    ),
    "aux/descriptors/homepage.json": tuple(
        Substitution(token, _parameter(parameter))
        for token, parameter in (
            ("TOKEN_GEN_KNOX_TOKEN_TTL",
             "gateway_token_generation_knox_token_ttl"),
            ("TOKEN_GEN_KNOX_TOKEN_TYPE", "gateway_knox_token_type"),
            ("TOKEN_GEN_ALLOWED_TSS_BACKENDS",
             "gateway_token_generation_allowed_tss_backends"),
            ("TOKEN_GEN_ENABLE_LIFESPAN_INPUT",
             "gateway_token_generation_enable_lifespan_input"),
            ("TOKEN_MAN_RENEWER_WHITELIST",
             "gateway_knox_token_renewer_whitelist"),
            ("TOKEN_USER_LIMITED_EXCEEDED_ACTION",
             "gateway_knox_token_user_limit_exceeded_action"),
        )
    ),
    "aux/descriptors/kt-kerberos.json": (
        Substitution("KNOX_TOKEN_KERBEROS_TTL",
                     _parameter("knox_token_kerberos_ttl_ms"),
                     False),
        Substitution("KNOX_TOKEN_KERBEROS_INCLUDE_GROUPS_ALLOWED",
                     _parameter("knox_token_kerberos_include_groups_allowed"),
                     False),
    ),
}


def apply_substitutions(content: str,
                        substitutions: Tuple[Substitution, ...],
                        context: TemplateContext) -> str:
    """
    Applies the substitutions in order, the way the control scripts do with
    `sed`: every occurrence of the token is replaced by the value, and the lines
    holding it are deleted instead if the value is empty and the substitution
    says so.
    """
    for substitution in substitutions:
        if substitution.token not in content:
            continue
        value = substitution.value(context)
        if not value and substitution.remove_line_if_empty:
            content = "".join(
                line for line in content.splitlines(keepends=True)
                if substitution.token not in line
            )
        else:
            content = content.replace(substitution.token, value or "")
    return content


def _ozone_ssl_enabled(context: TemplateContext) -> bool:
    configured = context.parameter("ssl_enabled", OZONE_PROMETHEUS_ROLE_TYPE)
    if configured is None:
        for name in context.file_names():
            if posixpath.basename(name) == "ozone-site.xml":
                configured = _xml_property(context.file(name) or "",
                                           "ozone.ssl.enabled")
                break
    return (configured or "").strip().lower() == "true"


def _xml_property(content: str, name: str) -> Optional[str]:
    match = re.search(
        r"<name>\s*" + re.escape(name) + r"\s*</name>\s*<value>([^<]*)</value>",
        content
    )
    return match.group(1).strip() if match else None


# The peer files the Ozone control script collects the scrape targets from, and
# the key of the port in each of them, for a given scheme.
OZONE_PROMETHEUS_TARGETS = (
    ("ozone-scm.properties", "ozone.scm.{scheme}-port"),
    ("ozone-om.properties", "ozone.om.{scheme}-port"),
    ("ozone-dn.properties", "ozone.datanode.{scheme}-port"),
    ("ozone-recon.properties", "ozone.recon.{scheme}-port"),
    ("ozone-tiering.properties", "ozone.tiering.{scheme}-port"),
    ("ozone-s3g.properties", "ozone.s3g.webadmin.{scheme}-port"),
)


def _ozone_prometheus_targets(context: TemplateContext, scheme: str) -> str:
    """
    The `host:port` entries of the scrape targets. A peer file has one
    `host:key=value` line per property and host, and those of the roles which
    are part of the cluster are among the files the role ships.
    """
    peer_files = {
        posixpath.basename(name): name for name in context.file_names()
        if name.startswith("ozone-conf/")
    }
    targets = ""
    for peer_file, key_template in OZONE_PROMETHEUS_TARGETS:
        if peer_file not in peer_files:
            continue
        key = key_template.format(scheme=scheme)
        for line in (context.file(peer_files[peer_file]) or "").splitlines():
            host, _, assignment = line.partition(":")
            name, separator, port = assignment.partition("=")
            if separator and name.strip() == key:
                targets += f'        - "{host.strip()}:{port.strip()}"\n'
    return targets


def _yaml_scalar(value: str) -> str:
    # A location which still carries a placeholder of Cloudera Manager, such as
    # `{{CMF_CONF_DIR}}`, would read as a flow mapping if left unquoted. A
    # double-quoted scalar has the same value.
    return json.dumps(value) if value.startswith("{") else value


def _ozone_scheme(context: TemplateContext) -> str:
    return "https" if _ozone_ssl_enabled(context) else "http"


def _ozone_ca_file(context: TemplateContext) -> str:
    if not _ozone_ssl_enabled(context):
        return ""
    ca_file = context.parameter("ozone.prometheus.ca.file",
                                OZONE_PROMETHEUS_ROLE_TYPE) or ""
    if ca_file == AUTO_TLS_CA_FILE:
        ca_file = AUTO_TLS_CA_FILE_LOCATION
    return _yaml_scalar(ca_file)


def _ozone_decrypted_key(context: TemplateContext) -> str:
    # The control script decrypts the key next to the original. A location
    # Cloudera Manager has not resolved yet, such as `{{CM_AUTO_TLS}}`, stays
    # what it is.
    server_key = context.parameter("ssl_server_privatekey_location",
                                   OZONE_PROMETHEUS_ROLE_TYPE) or ""
    if "/" not in server_key:
        return server_key
    return posixpath.join(posixpath.dirname(server_key),
                          "decrypted-server-private-key.pem")


# The `tls_server_config` section of the Prometheus web configuration. Without
# advanced TLS controls, the script requests the defaults of Prometheus: TLS 1.2
# to 1.3 and the default cipher suites.
PROMETHEUS_TLS_CONFIG: Tuple[Substitution, ...] = (
    Substitution("{{SERVER_CERT}}",
                 _parameter("ssl_server_certificate_location",
                            OZONE_PROMETHEUS_ROLE_TYPE),
                 False),
    Substitution("{{DECRYPTED_KEY}}", _ozone_decrypted_key, False),
    Substitution("{{SERVER_MIN_TLS_VERSION}}", _constant("TLS12"), False),
    Substitution("{{SERVER_MAX_TLS_VERSION}}", _constant("TLS13"), False),
    Substitution("{{SERVER_CIPHER_SUITES}}", _constant("[]"), False),
)


def _ozone_tls_server_config(context: TemplateContext) -> str:
    # TLS is off by default, so omitting the section disables it.
    if not _ozone_ssl_enabled(context):
        return ""
    template = context.file("aux/templates/prometheus-tls-config.yml") or \
        PROMETHEUS_TLS_CONFIG_TEMPLATE
    return apply_substitutions(template, PROMETHEUS_TLS_CONFIG,
                               context).rstrip("\n")


OZONE_PROMETHEUS_CONFIG: Tuple[Substitution, ...] = (
    Substitution("{{SCHEME}}", _ozone_scheme, False),
    Substitution("{{CA_FILE}}", _ozone_ca_file, False),
    Substitution(
        "{{TARGETS}}",
        lambda context: _ozone_prometheus_targets(context,
                                                  _ozone_scheme(context)),
        False
    ),
    Substitution("{{TOKEN_FILE}}",
                 _constant('"{{CMF_CONF_DIR}}/ozone-conf/prometheus-token"'),
                 False),
    Substitution(
        "{{SCRAPE_INTERVAL}}",
        lambda context: context.parameter("ozone.prometheus.scrape.interval",
                                          OZONE_PROMETHEUS_ROLE_TYPE)
        or PROMETHEUS_DEFAULT_SCRAPE_INTERVAL,
        False
    ),
)
OZONE_PROMETHEUS_WEB_CONFIG: Tuple[Substitution, ...] = (
    Substitution("{{TLS_SERVER_CONFIG}}", _ozone_tls_server_config, False),
)

# Every template this module renders, keyed by the Cloudera service type and the
# name of the file in the `configFiles` listing of a role. The Ozone roles ship
# the Prometheus files in `aux/`; a Prometheus role reads them from `ozone-conf/`.
TEMPLATES: Dict[Tuple[str, str], Tuple[Substitution, ...]] = {
    **{("KNOX", name): substitutions
       for name, substitutions in KNOX_TEMPLATES.items()},
    **{("OZONE", f"{folder}/ozone-prometheus.yml"): OZONE_PROMETHEUS_CONFIG
       for folder in ("aux", "ozone-conf")},
    **{("OZONE", f"{folder}/prometheus-web.yml"): OZONE_PROMETHEUS_WEB_CONFIG
       for folder in ("aux", "ozone-conf")},
}


def render_template(cloudera_service_type: str,
                    config_file_name: str,
                    content: str,
                    context: TemplateContext) -> str:
    """
    Renders a configuration file the way the control script of its role would
    on the host, if it is one of the :data:`TEMPLATES`. Any other file is
    returned unchanged.
    """
    substitutions = TEMPLATES.get(
        ((cloudera_service_type or "").upper(), config_file_name)
    )
    if substitutions is None:
        return content
    return apply_substitutions(content, substitutions, context)


def neutralize_placeholders(content: str, file_type: str) -> str:
    """
    Turns the placeholders left in a file into something its syntax accepts:
    a placeholder on a line of its own, standing in for a block, is removed,
    together with the comma it leaves dangling in JSON, and an inline
    placeholder is quoted, so that it becomes a string value.

    This is the last resort for a placeholder no renderer knows the value of,
    and it is only ever applied to a file which does not parse otherwise.
    """
    content = WHOLE_LINE_PLACEHOLDER.sub("", content)
    content = UNQUOTED_MUSTACHE_PLACEHOLDER.sub(r'"\1"', content)
    if file_type == "json":
        content = DANGLING_JSON_COMMA.sub(r"\1", content)
    logging.debug("Content after neutralizing the placeholders: %s", content)
    return content
