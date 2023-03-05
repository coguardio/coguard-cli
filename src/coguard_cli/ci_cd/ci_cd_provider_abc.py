"""
This module contains an abstract base class for a CI/CD handler, and defines
the necessary functions
"""

from abc import ABC, abstractmethod
from typing import Optional

class CiCdProvider(ABC):
    """
    This is an abstract base class for a CI/CD tool.
    """

    @abstractmethod
    def add(self, location: str) -> Optional[str]:
        """
        This function generates the CI/CD script for the specific CI/CD provider.
        It would put it into the `location`, which is the input parameter.
        Returns the folder where scripts have been generated or None.
        """

    @abstractmethod
    def post_string(self) -> str:
        """
        This is a function which generates the "post" string with reminders
        after the file has been generated. This can include recommendations
        such as setting of secrets, etc.
        """

    @abstractmethod
    def get_identifier(self) -> str:
        """
        Returns an identifier by which to address this class by.
        """
