"""
The module to test the functionality of api_connection module.
"""

import unittest
import unittest.mock
from coguard_cli import api_connection

class TestApiConnection(unittest.TestCase):
    """
    The unit tests for the api_connection module.
    """

    def test_send_zip_file_for_scanning_non_200_status(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(status_code = 404)
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data: mock_response
                ):
            self.assertIsNone(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                "baz",
                "biz"
            ))

    def test_send_zip_file_for_scanning_200_status(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {"foo": "bar"}
        )
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data: mock_response
                ):
            self.assertDictEqual(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                "baz",
                "biz"
            ), {"foo": "bar"})

    def test_does_user_with_email_already_exist_200_status(self):
        """
        Checks the existence of the user function
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            text = "true"
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url: mock_response):
            self.assertTrue(
                api_connection.does_user_with_email_already_exist(
                    "foo",
                    "bar"
                )
            )

    def test_does_user_with_email_already_exist_400_status(self):
        """
        Checks the existence of the user function
        """
        mock_response = unittest.mock.Mock(
            status_code = 400,
            text = "true"
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url: mock_response):
            self.assertFalse(
                api_connection.does_user_with_email_already_exist(
                    "foo",
                    "bar"
                )
            )

    def test_sign_up_for_coguard_200_status(self):
        """
        Checks the sign up with successful api call.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204,
            text = "true"
        )
        with unittest.mock.patch(
                'requests.post',
                new_callable=lambda: lambda url, headers, json: mock_response):
            self.assertTrue(
                api_connection.sign_up_for_coguard(
                    "foo",
                    "bar",
                    "baz"
                )
            )

    def test_sign_up_for_coguard_400_status(self):
        """
        Checks the sign up with not successful api call.
        """
        mock_response = unittest.mock.Mock(
            status_code = 400,
            text = "true"
        )
        with unittest.mock.patch(
                'requests.post',
                new_callable=lambda: lambda url, headers, json: mock_response):
            self.assertFalse(
                api_connection.sign_up_for_coguard(
                    "foo",
                    "bar",
                    "baz"
                )
            )

    def test_mention_referrer_200_status(self):
        """
        Checks the sign up with successful api call.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204,
            text = "true"
        )
        with unittest.mock.patch(
                'requests.post',
                new_callable=lambda: lambda url, headers, json: mock_response):
            api_connection.mention_referrer(
                "foo",
                "bar",
                "baz"
            )
