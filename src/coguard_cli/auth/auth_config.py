"""
The module that contains the class which represents a configuration
for the coguard CLI
"""

import json

DEFAULT_COGUARD_URL = "https://portal.coguard.io/server"
DEFAULT_AUTH_URL = "https://portal.coguard.io/auth"

class CoGuardCliConfig():
    """
    The class representing the configuration of the CoGuard CLI
    """

    def __init__(self,
                 username: str,
                 password: str,
                 coguard_url: str = DEFAULT_COGUARD_URL,
                 auth_url: str = DEFAULT_AUTH_URL):
        """
        The initialization of the default parameters.

        :param username: The username
        :param password: The password
        :param coguard_url: The url to contact CoGuard from.
        :param auth_url: The url to contact the authentication mechanism from.
        """
        self._password = password
        self._username = username
        self._coguard_url = coguard_url
        self._auth_url = auth_url

    def get_password(self) -> str:
        """
        The getter for the password parameter.
        """
        return self._password

    def get_username(self) -> str:
        """
        The getter for the username parameter
        """
        return self._username

    def get_coguard_url(self) -> str:
        """
        The getter for the coguard url parameter
        """
        return self._coguard_url

    def get_auth_url(self) -> str:
        """
        The getter for the auth url.
        """
        return self._auth_url

    def __str__(self):
        """
        The string encoding of this class. Will be JSON.
        """
        rep = {
            "username": self.get_username(),
            "password": self.get_password(),
            "coguard-url": self.get_coguard_url(),
            "coguard-auth-url": self.get_auth_url()
        }
        return json.dumps(rep)
