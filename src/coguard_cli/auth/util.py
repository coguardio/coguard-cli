"""
Utility module for common functions, and to avoid circular imports.
"""
import re
import os
import stat
import json
import zlib
from pathlib import Path
from typing import Optional, Dict
from getpass import getpass
from coguard_cli.auth.token import Token
from coguard_cli.api_connection import does_user_with_email_already_exist, \
    sign_up_for_coguard, \
    mention_referrer
from coguard_cli.print_colors import COLOR_TERMINATION, COLOR_RED, COLOR_CYAN, COLOR_YELLOW
from coguard_cli.auth.auth_config import CoGuardCliConfig

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

def sign_in_or_sign_up(coguard_url: str, auth_url: str) -> Optional[Token]:
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
    token = Token("", new_config_object)
    auth_res = token.authenticate_to_server()
    if auth_res is not None:
        store_config_object_in_auth_file(new_config_object)
    return token if auth_res is not None else None

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

DEFAULT_CONFIG_PATH = str(Path.home().joinpath(
    '.config',
    'coguard-cli',
    'coguard_conf'
))

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
