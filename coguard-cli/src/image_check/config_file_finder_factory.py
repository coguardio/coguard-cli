"""
This module contains a factory to produce the config file finder
instances needed to check a given container.
"""

from typing import Generator

#pylint: disable=unused-import
from src.image_check.config_file_finders.config_file_finder_nginx import ConfigFileFinderNginx
from src.image_check.config_file_finders.config_file_finder_mysql import ConfigFileFinderMysql
from src.image_check.config_file_finders.config_file_finder_kafka import ConfigFileFinderKafka
from src.image_check.config_file_finders.config_file_finder_mongodb import ConfigFileFinderMongodb
from src.image_check.config_file_finders.config_file_finder_apache import ConfigFileFinderApache
from src.image_check.config_file_finders.config_file_finder_kerberos import ConfigFileFinderKerberos
from src.image_check.config_file_finders.config_file_finder_postgres import ConfigFileFinderPostgres
from src.image_check.config_file_finders.config_file_finder_elasticsearch \
    import ConfigFileFinderElasticsearch
from src.image_check.config_file_finder_abc import ConfigFileFinder

def config_file_finder_factory() -> Generator[ConfigFileFinder, None, None]:
    """
    The factory to get different instances to find configuration files.

    :returns: A generator continuously yielding subclasses of :class:`ConfigFileFinder`.
    """
    for cls in ConfigFileFinder.__subclasses__():
        yield cls()
