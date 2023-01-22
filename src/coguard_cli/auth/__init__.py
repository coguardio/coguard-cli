"""
This module contains the basic functionality to check if the user
is already authenticated with a username and password in a given
file.
"""

from enum import Enum
from getpass import getpass
import re
import json
import os
import logging
import stat
import zlib
from typing import Dict, Optional
from pathlib import Path
import jwt
import requests
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.api_connection import does_user_with_email_already_exist, \
    sign_up_for_coguard, \
    mention_referrer
from coguard_cli.print_colors import COLOR_TERMINATION, COLOR_RED, COLOR_CYAN, COLOR_YELLOW

DEFAULT_CONFIG_PATH = str(Path.home().joinpath(
    '.config',
    'coguard-cli',
    'coguard_conf'
))

COGUARD_REALM_TOKEN_URL = "/realms/coguard/protocol/openid-connect/token"

class DealEnum(Enum):
    """
    An Enum identifying the deal the current user has with CoGuard.
    """
    ENTERPRISE = "Enterprise"
    DEV = "Dev"
    FREE = "Free"

def check_password_strength(password: str) -> Optional[str]:
    """
    Figures out if the password is strong enough. If it returns
    None, then the password is fine. Otherwise, a string with suggestions
    to fix is produced.

    :param password: The password in question.
    :returns: None, if the password is fine, or a string indicating what makes the password weak.
    """
    if len(password) < 15:
        return "Your password needs to be at least 15 characters long."
    if re.search('[0-9]', password) is None:
        return "Your password needs to have at least one number."
    if re.search('[A-Z]', password) is None:
        return "Your password needs to have at least one uppercase character."
    if re.search('[a-z]', password) is None:
        return "Your password needs to have at least one lowercase character."
    if re.search('[^a-zA-Z0-9]', password) is None:
        return "Your password needs to have at least one special character."
    return None

def sign_in_or_sign_up(coguard_url: str, auth_url: str) -> Optional[str]:
    """
    The functionality to sign in to keycloak or sign up.

    :param coguard_url: The url for the CoGuard API
    :param auth_url: The url for the authentication service.
    :returns: The authentication token if the sign in/sign up process was successful,
              or None.
    """
    user_name = input("You need to sign up to use the CoGuard service. "
                      "By providing your email, you confirm that you read, understood "
                      "and agree with the CoGuard Terms of Service "
                      "(https://www.coguard.io/terms-of-service) and Privacy Policy "
                      "(https://www.coguard.io/privacy-policy). Please enter your email: ")
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if not re.fullmatch(email_regex, user_name):
        print(f'{COLOR_RED}Provided email not valid.{COLOR_TERMINATION}')
        return None
    does_user_exist = does_user_with_email_already_exist(user_name, coguard_url)
    if does_user_exist:
        print(f"{COLOR_CYAN}The given email already exists in the system. You just need to enter"
              " your password hence to log in.{COLOR_TERMINATION} \n"
              f"If you have forgotten your password, please visit {coguard_url}, "
              "press `Log In`, and click on `Forgot Password`.\n\n")
        password = getpass("Please enter your password: ")
        new_config_object = CoGuardCliConfig(
            user_name,
            password,
            coguard_url,
            auth_url
        )
    elif does_user_exist is None:
        print(f"{COLOR_RED}There was an error checking if the given user already exists "
              f"(did you enter a valid email address?){COLOR_TERMINATION}")
        return None
    else:
        while True:
            password = getpass(
                f"{COLOR_CYAN}Please enter the password you would love to use {COLOR_TERMINATION}"
                "(min 15 characters, including an uppercase letter, "
                "a lowercase letter, a number and a special character). "
                "To exit, leave this empty: "
            )
            check_password_strength_result = check_password_strength(password)
            if check_password_strength_result is None:
                break
            if password == "":
                return None
            print(f"\n{COLOR_YELLOW}{check_password_strength_result}{COLOR_TERMINATION}\n")
        sign_up_for_coguard(user_name, password, coguard_url)
        new_config_object = CoGuardCliConfig(
            user_name,
            password,
            coguard_url,
            auth_url
        )
        referrer = input(
            "Did someone refer you? Please enter "
            "their email or name here or leave this field blank: ")
        if referrer:
            mention_referrer(
                user_name,
                referrer,
                coguard_url
            )
    token = authenticate_to_server(new_config_object)
    if token is not None:
        store_config_object_in_auth_file(new_config_object)
    return token

def store_config_object_in_auth_file(
        new_config_object: CoGuardCliConfig,
        path: Optional[str] = None) -> None:
    """
    The function to be used to store a new config object in form of an auth file.

    :param new_config_object: The configuration file object generated to be stored
                              locally. It is a dictionary with the necessary keys to
                              authenticate.
    :param path: The optional parameter to define a custom configuration path.
    """
    config_path = path if path is not None else DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(config_path), exist_ok = True)
    with open(config_path, 'wb') as config_file:
        config_file.write(zlib.compress(str(new_config_object).encode('utf-8')))
    os.chmod(config_path, stat.S_IRUSR)

def get_auth_file(path: Optional[str] = None) -> Dict:
    """
    Retrieves the auth file, stored under
    $HOME/.config/coguard-cli/config.json or at the path specified
    with the given path parameter.
    If the file does not
    exist, an empty dictionary is returned.

    :param path: The path to the file.
    :return: The parsed JSON in the configuration authentication file.
    """
    config_path = path if path is not None else DEFAULT_CONFIG_PATH
    if not os.path.exists(config_path):
        return {}
    # Technically, the 0400 should be enough to check for.
    # But according to the os.chmod documentation, the only
    # supported options are stat.S_IWRITE and stat.S_IREAD. Hence,
    # we need to allow for this edge case here until this is addressed
    # one day.
    if not (oct(os.stat(config_path).st_mode).endswith("0400")
            or oct(os.stat(config_path).st_mode).endswith("0444")):
        print(
            f"{COLOR_RED}The authentication file was supposed to be only readable "
            f"by the owner.{COLOR_TERMINATION}"
        )
        return {}
    with open(config_path, 'rb') as config_file:
        config_json = json.loads(
            zlib.decompress(config_file.read()).decode('utf-8')
        )
    return config_json if isinstance(config_json, dict) else {}

def retrieve_configuration_object(
        path: Optional[str] = None,
        arg_coguard_url: Optional[str] = None,
        arg_auth_url: Optional[str] = None
) -> Optional[CoGuardCliConfig]:
    """
    This function returns a configuration object, if it can be
    retrieved, or None.

    :param path: An optional parameter where to find the configuration file.
    :returns: If the configuration object was possible to be retrieved, it returns
              the representation as a :class:`CoGuardCliConfig` instance. Otherwise,
              this function returns None.
    """
    if os.environ.get('COGUARD_USER_NAME') and os.environ.get('COGUARD_PASSWORD'):
        username = os.environ.get('COGUARD_USER_NAME')
        password = os.environ.get('COGUARD_PASSWORD')
        coguard_url = arg_coguard_url
        auth_url = arg_auth_url
    else:
        config_dict = get_auth_file(path)
        username = config_dict.get("username", "")
        password = config_dict.get("password", "")
        coguard_url = config_dict.get("coguard-url", "") or arg_coguard_url
        auth_url = config_dict.get("coguard-auth-url", "") or arg_auth_url
    if (not username) or (not password):
        return None
    if coguard_url:
        if auth_url:
            return CoGuardCliConfig(username, password, coguard_url, auth_url)
        return CoGuardCliConfig(username, password, coguard_url)
    return CoGuardCliConfig(username, password)

def authenticate_to_server(config_object: Optional[CoGuardCliConfig]) -> Optional[str]:
    """
    This is the function which tries to make the call to the coguard authentication server.
    Returns None if authentication could not have been done, and the auth token otherwise.

    :param config_object: The configuration object of type :class:`CoGuardCliConfig`.
    :returns: The authentication token for further use, or None if the authentication failed.
    """
    if config_object is None:
        return None
    # The following check is just for the case if people use a different authentication
    # server url and forget the auth in the subpath
    if config_object.get_auth_url().endswith('/auth'):
        complete_request_url = config_object.get_auth_url() + COGUARD_REALM_TOKEN_URL
    else:
        complete_request_url = f"{config_object.get_auth_url()}/auth{COGUARD_REALM_TOKEN_URL}"
    token_request = requests.post(
        complete_request_url,
        data={
            'client_id': 'client-react-frontend',
            'username': config_object.get_username(),
            'password': config_object.get_password(),
            'grant_type': 'password'
        },
        timeout=300
    )
    if token_request.status_code != 200:
        logging.error("There was an error requesting the authentication token: %s",
                      token_request.reason)
        return None
    response_json = token_request.json()
    return response_json.get("access_token", None)


def get_public_key(config_object: CoGuardCliConfig) -> Optional[str]:
    """
    A helper function to retrieve the public key from the authentication server.
    Returns None if there is no public key.
    """
    if config_object.get_auth_url().endswith('/auth'):
        complete_request_url = config_object.get_auth_url() + "/realms/coguard"
    else:
        complete_request_url = f"{config_object.get_auth_url()}/auth/realms/coguard"
    public_key_request = requests.get(complete_request_url, timeout=5)
    if public_key_request.status_code != 200:
        logging.error("Could not retrieve public key from coguard url: %s",
                      str(public_key_request))
        logging.error("Assuming free account")
        return None
    response_json = public_key_request.json()
    public_key = response_json.get("public_key", "")
    if not public_key:
        logging.error("Could not extract public key.")
        return None
    logging.debug("The public key is %s", str(public_key))
    return public_key

def get_decoded_jwt_token(token: str, public_key: str) -> jwt.jwk.AbstractJWKBase:
    """
    Helper function to get a decoded JWT token.
    """
    expanded_pkey = f"""-----BEGIN PUBLIC KEY-----
    {public_key}
    -----END PUBLIC KEY-----""".replace("    ", "")
    jwt_obj = jwt.JWT()
    return jwt_obj.decode(token, jwt.jwk_from_pem(expanded_pkey.encode()))

def extract_organization_from_token(token: str, config_object: CoGuardCliConfig) -> Optional[str]:
    """
    This is the helper function to extract the organization from the token.
    Returning None if there is no organization.
    """
    public_key = get_public_key(config_object)
    if not public_key:
        return None
    jwt_decoded = get_decoded_jwt_token(token, public_key)
    return jwt_decoded.get("organization", None)

def extract_deal_type_from_token(token: str, config_object: CoGuardCliConfig) -> DealEnum:
    """
    This function uses a token, and a configuruation object, and extracts the deal
    type of the account stored in the JWT token.

    :param token: The JWT token string
    :param config_object: The CoGuard CLI config
    """
    # Getting the public key
    public_key = get_public_key(config_object)
    if not public_key:
        logging.error(
            "Assuming free account, as we could not find the public key of the auth server."
        )
        return DealEnum.FREE
    jwt_decoded = get_decoded_jwt_token(token, public_key)
    deal_identifiers = jwt_decoded.get('realm_access', {}).get('roles', [])
    for deal_enum in list(DealEnum):
        if deal_enum.value.upper() in deal_identifiers:
            return deal_enum
    logging.error("No valid deal enum in decoded JWT token. Assuming free: %s",
                  str(jwt_decoded))
    return DealEnum.FREE
