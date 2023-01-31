"""
This is a simple representation of a token, which also renews automatically
if it expired.
"""

import logging
import jwt
import coguard_cli.auth
from coguard_cli.auth.auth_config import CoGuardCliConfig

class Token():
    """
    A simple representation of an access token.
    """

    def __init__(self, token: str, auth_config: CoGuardCliConfig):
        """
        Initialization of this object with a valid token,
        and an auth_config in case we need to renew it.
        """
        self._token = token
        self._auth_config = auth_config

    def get_token(self, renewal=True) -> str:
        """
        Getter function for the token, which also renews in case the token has expired.
        """
        if renewal and self.is_token_expired():
            logging.debug("Token has expired. Renewing.")
            self._token = coguard_cli.auth.authenticate_to_server(self._auth_config)
        return self._token

    def is_token_expired(self) -> bool:
        """
        Helper function to detect if a given token is expired or not.
        """
        public_key = coguard_cli.auth.get_public_key(self._auth_config)
        if not public_key:
            logging.error(
                "Assuming free account, as we could not find the public key of the auth server."
            )
            False
        try:
            coguard_cli.auth.get_decoded_jwt_token(self, public_key)
        except jwt.exceptions.JWTDecodeError:
            logging.debug("JWT token expired. Renewing.")
            return True
        return False
