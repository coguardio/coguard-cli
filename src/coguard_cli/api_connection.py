"""
The coguard CLI module which contains all api-connection
logic, so that it is modularized.
"""

import logging
from typing import Dict, Optional
import requests

def send_zip_file_for_scanning(
        zip_file: str,
        user_name: str,
        auth_token: str,
        coguard_api_url: str) -> Optional[Dict]:
    """
    The helper function to send a zip file for scanning to the back-end.
    The return value will be an optional dictionary value as per the
    result jsons produced by the coguard engine.

    :param zip_file: The path to the zip file.
    :param user_name: The user name associated.
    :param auth_token: The authentication token to be used.
    :param coguard_api_url: The url to be used to contact CoGuard.
    :returns: Either `None`, or a dictionary as returned by CoGuard after
              scanning.
    """
    with open(zip_file, 'rb') as file_to_send:
        resp = requests.post(
            (f"{coguard_api_url}/coguard-cli/"
             f"upload-cluster-zip?userName={user_name}"),
            headers={
                "Authorization": f'Bearer {auth_token}',
                "Content-Type": "application/octet-stream"
            },
            data=file_to_send.read())
    if resp.status_code != 200:
        logging.error("There was an error in the API call: %s",
                      resp.reason)
        return None
    return resp.json()

def does_user_with_email_already_exist(
        user_name: str,
        coguard_url: str) -> Optional[bool]:
    """
    Given a user_name, which is an email, we will check if
    a user with this given name already exists.

    :param user_name: The user name (we store them as emails)
    :param coguard_url: The url to contact the coguard API.
    :returns: Either None, or a boolean which is True if the user exists.
    """
    resp = requests.get(f"{coguard_url}/registration/does-user-exist?userName={user_name}")
    if resp.status_code != 200:
        logging.error("There was an error checking for the existence of a certian user: %s",
                      resp.reason)
        return None
    return resp.text.lower() == 'true'

def sign_up_for_coguard(
        user_name: str,
        password: str,
        coguard_url: str) -> Optional[bool]:
    """
    Sign up mechanism for coguard.

    :param user_name: The user name (we store them as emails)
    :param password: The chosen password by the user.
    :param coguard_url: The url to contact the coguard API.
    :returns: Either None if an error occurred, or a boolean indicating that
              the sign-up was successful.
    """
    resp = requests.post(
        f"{coguard_url}/registration/register-user",
        headers={"content-type": "application/json"},
        json={"userName": user_name, "password": password}
    )
    if resp.status_code != 204:
        logging.error("There was an error signing the user up: %s",
                      resp.reason)
        return None
    return resp.text.lower() == 'true'

def mention_referrer(
        user_name: str,
        referrer: str,
        coguard_url: str) -> None:
    """
    If the user was referred, we will capture this here.

    :param user_name: The name of the user who just signed up
    :param referrer: The name of the referrer
    :param coguard_url: The url of coguard to send the request to.
    """
    resp = requests.post(
        f"{coguard_url}/registration/referrer-capture",
        headers={"content-type": "application/json"},
        json={"userName": user_name, "referrer": referrer}
    )
    if resp.status_code != 204:
        logging.error("Could not capture referrer. Please send this error to info@coguard.io")
