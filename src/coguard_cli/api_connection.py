"""
The coguard CLI module which contains all api-connection
logic, so that it is modularized.
"""

import logging
import tempfile
import os
from typing import Dict, Optional
import requests

from coguard_cli.auth.token import Token
from coguard_cli.util import replace_special_chars_with_underscore

def run_report(
        auth_token: Token,
        coguard_api_url: str,
        scan_identifier: str,
        organization: str):
    """
    This is a helper function to kick off a report run on CoGuard.
    The output is whether the report run was successful or not.
    """
    resp = requests.put(
        (f"{coguard_api_url}/cluster/run-report/"
         f"{replace_special_chars_with_underscore(scan_identifier)}?"
         f"organizationName={organization}"),
        headers={
            "Authorization": f'Bearer {auth_token.get_token()}',
            "Content-Type": "application/json"
        },
        timeout=1600
    )
    if resp.status_code != 204:
        logging.error("Could not run a report on the specified cluster")
        return False
    return True

def get_latest_report(
        auth_token: Token,
        coguard_api_url: str,
        scan_identifier: str,
        organization: str) -> Optional[str]:
    """
    Helper function to get the latest report for a specific cluster.
    Returns None if the latest report did not exist.
    """
    resp = requests.get(
        (f"{coguard_api_url}/cluster/reports/list?"
         f"clusterName={replace_special_chars_with_underscore(scan_identifier)}&"
         f"organizationName={organization}"),
         headers={
            "Authorization": f'Bearer {auth_token.get_token()}',
            "Content-Type": "application/json"
        },
        timeout=300
    )
    if resp.status_code != 200:
        logging.error("Could not retrieve the latest report for cluster %s",
                      scan_identifier)
        return None
    lst = resp.json()
    if not lst:
        return None
    return lst[-1]

def send_zip_file_for_scanning(
        zip_file: str,
        user_name: str,
        auth_token: Token,
        coguard_api_url: str,
        scan_identifier: str,
        organization: Optional[str],
        ruleset: str) -> Optional[Dict]:
    """
    The helper function to send a zip file for scanning to the back-end.
    The return value will be an optional dictionary value as per the
    result jsons produced by the coguard engine.

    :param zip_file: The path to the zip file.
    :param user_name: The user name associated.
    :param auth_token: The authentication token to be used.
    :param coguard_api_url: The url to be used to contact CoGuard.
    :param organization: The optional organization string, indicating that
                         we want to upload it to an org instead of the free account.
    :returns: Either `None`, or a dictionary as returned by CoGuard after
              scanning.
    """
    with open(zip_file, 'rb') as file_to_send:
        if organization:
            resp_upload = requests.post(
                (f"{coguard_api_url}/cluster/"
                 f"upload-cluster-zip?organizationName={organization}&"
                 f"overwrite=true&compliance={ruleset}"),
                headers={
                    "Authorization": f'Bearer {auth_token.get_token()}',
                    "Content-Type": "application/octet-stream"
                },
                data=file_to_send.read(),
                timeout=300)
            if resp_upload.status_code != 204:
                logging.error("There was an issue uploading the zip file")
                logging.debug("Reason %s", resp_upload.reason)
                return None
            logging.debug("We successfully uploaded the cluster. Now running the report.")
            run_report_result = run_report(
                auth_token,
                coguard_api_url,
                scan_identifier,
                organization
            )
            if not run_report_result:
                return None
            latest_report = get_latest_report(
                auth_token,
                coguard_api_url,
                scan_identifier,
                organization
            )
            logging.debug("The latest report is %s", latest_report)
            if not latest_report:
                return None
            resp = requests.get(
                (f"{coguard_api_url}/cluster/report?"
                 f"clusterName={replace_special_chars_with_underscore(scan_identifier)}&"
                 f"organizationName={organization}&"
                 f"reportName={latest_report}"),
                headers={
                    "Authorization": f'Bearer {auth_token.get_token()}',
                    "Content-Type": "application/json"
                },
                timeout=300
            )
        else:
            resp = requests.post(
                (f"{coguard_api_url}/coguard-cli/"
                 f"upload-cluster-zip?userName={user_name}&compliance={ruleset}"),
                headers={
                    "Authorization": f'Bearer {auth_token.get_token()}',
                    "Content-Type": "application/octet-stream"
                },
                data=file_to_send.read(),
                timeout=300)
    if resp.status_code != 200:
        logging.error("There was an error in the API call: %s",
                      resp.reason)
        return None
    return resp.json()

def send_zip_file_for_fixing(
        zip_file: str,
        auth_token: Token,
        coguard_api_url: str,
        organization: Optional[str]) -> Optional[str]:
    """
    The helper function to send a zip file for scanning to the back-end.
    The return value will be an optional dictionary value as per the
    result jsons produced by the coguard engine.

    :param zip_file: The path to the zip file.
    :param user_name: The user name associated.
    :param auth_token: The authentication token to be used.
    :param coguard_api_url: The url to be used to contact CoGuard.
    :param organization: The optional organization string, indicating that
                         we want to upload it to an org instead of the free account.
    :returns: Either `None`, or a dictionary as returned by CoGuard after
              scanning.
    """
    with open(zip_file, 'rb') as file_to_send:
        resp_upload = requests.post(
            (f"{coguard_api_url}/cluster/"
             f"fix-cluster-zip?organizationName={organization}"),
            headers={
                "Authorization": f'Bearer {auth_token.get_token()}',
                "Content-Type": "application/octet-stream"
            },
            data=file_to_send.read(),
            timeout=300)
        if resp_upload.status_code != 200:
            logging.debug("There was an issue uploading the zip file")
            logging.debug("Reason %s", resp_upload.reason)
            return None
        (file_handle, temp_zip) = tempfile.mkstemp(
            prefix="coguard_cli_zip_to_fix", suffix=".zip"
        )
        os.close(file_handle)
        with open(temp_zip, 'wb') as zip_to_write:
            zip_to_write.write(resp_upload.content)
    return temp_zip


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
    resp = requests.get(f"{coguard_url}/registration/does-user-exist?userName={user_name}",
                        timeout=300)
    if resp.status_code != 200:
        logging.error("There was an error checking for the existence of a certain user: %s",
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
        json={"userName": user_name, "password": password},
        timeout=300
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
        json={"userName": user_name, "referrer": referrer},
        timeout=300
    )
    if resp.status_code != 204:
        logging.error("Could not capture referrer. Please send this error to info@coguard.io")

def get_fixable_rule_list(
        token: Token,
        coguard_api_url: str,
        user_name: Optional[str],
        organization: Optional[str]):
    """
    The call to the endpoint to determine a list of fixable rule identifiers.
    """
    if organization:
        resp = requests.get(
            f"{coguard_api_url}/cluster/get-fixable-list?organizationName={organization}",
            headers={
                "Authorization": f'Bearer {token.get_token()}'
            },
            timeout=300
        )
        if resp.status_code != 200:
            logging.error("There was an issue getting the fixable list. ")
            logging.debug("Reason %s", resp.reason)
            return []
        return resp.json()
    resp = requests.get(
        f"{coguard_api_url}/coguard-cli/get-fixable-list?userName={user_name}",
        headers={
            "Authorization": f'Bearer {token.get_token()}'
        },
        timeout=300
    )
    if resp.status_code != 200:
        logging.error("There was an issue getting the fixable list. ")
        logging.debug("Reason %s", resp.reason)
        return []
    return resp.json()
