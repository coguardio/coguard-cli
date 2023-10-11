"""
This module contains a factory to produce the config file finder
instances needed to check a given container.
"""

from typing import Generator

#pylint: disable=unused-import
from coguard_cli.discovery.config_file_finders.config_file_finder_nginx \
    import ConfigFileFinderNginx
from coguard_cli.discovery.config_file_finders.config_file_finder_mysql \
    import ConfigFileFinderMysql
from coguard_cli.discovery.config_file_finders.config_file_finder_kafka \
    import ConfigFileFinderKafka
from coguard_cli.discovery.config_file_finders.config_file_finder_mongodb \
    import ConfigFileFinderMongodb
from coguard_cli.discovery.config_file_finders.config_file_finder_apache \
    import ConfigFileFinderApache
from coguard_cli.discovery.config_file_finders.config_file_finder_kerberos \
    import ConfigFileFinderKerberos
from coguard_cli.discovery.config_file_finders.config_file_finder_postgres \
    import ConfigFileFinderPostgres
from coguard_cli.discovery.config_file_finders.config_file_finder_elasticsearch \
    import ConfigFileFinderElasticsearch
from coguard_cli.discovery.config_file_finders.config_file_finder_tomcat \
    import ConfigFileFinderTomcat
from coguard_cli.discovery.config_file_finders.config_file_finder_open_telemetry_collector \
    import ConfigFileFinderOpenTelemetryCollector
from coguard_cli.discovery.config_file_finders.config_file_finder_redis \
    import ConfigFileFinderRedis
from coguard_cli.discovery.config_file_finders.config_file_finder_netlify \
    import ConfigFileFinderNetlify
from coguard_cli.discovery.config_file_finders.config_file_finder_dockerfile \
    import ConfigFileFinderDockerfile
from coguard_cli.discovery.config_file_finders.config_file_finder_docker_compose \
    import ConfigFileFinderDockerCompose
from coguard_cli.discovery.config_file_finders.config_file_finder_kubernetes \
    import ConfigFileFinderKubernetes
from coguard_cli.discovery.config_file_finders.config_file_finder_helm \
    import ConfigFileFinderHelm
from coguard_cli.discovery.config_file_finders.config_file_finder_terraform \
    import ConfigFileFinderTerraform
from coguard_cli.discovery.config_file_finders.config_file_finder_aws_cfn \
    import ConfigFileFinderCloudformation
from coguard_cli.discovery.config_file_finders.config_file_finder_iis \
    import ConfigFileFinderIis
from coguard_cli.discovery.config_file_finders.config_file_finder_rabbitmq \
    import ConfigFileFinderRabbitmq
from coguard_cli.discovery.config_file_finders.config_file_finder_ansible \
    import ConfigFileFinderAnsible
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder

def config_file_finder_factory() -> Generator[ConfigFileFinder, None, None]:
    """
    The factory to get different instances to find configuration files.

    :returns: A generator continuously yielding subclasses of :class:`ConfigFileFinder`.
    """
    for cls in ConfigFileFinder.__subclasses__():
        yield cls()
