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
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ):
            self.assertIsNone(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "baz"),
                "biz",
                "zip",
                None,
                ''
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
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ):
            self.assertDictEqual(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "baz"),
                "biz",
                "zip",
                None,
                ''
            ), {"foo": "bar"})

    def test_send_zip_file_for_scanning_with_org_non_204_status(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420,
            json = lambda: {"foo": "bar"}
        )
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ):
            self.assertIsNone(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "baz"),
                "biz",
                "zip",
                "org",
                ''
            ))

    def test_send_zip_file_for_scanning_with_org_204_failed_run(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204,
            json = lambda: {"foo": "bar"}
        )
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ), \
                unittest.mock.patch(
                    'coguard_cli.api_connection.run_report',
                    new_callable=lambda: lambda a, b, c, d: False
                ):
            self.assertIsNone(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "biz",
                "zip",
                "org",
                ''
            ))

    def test_send_zip_file_for_scanning_with_org_204_failed_latest_report(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204,
            json = lambda: {"foo": "bar"}
        )
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ), \
                unittest.mock.patch(
                    'coguard_cli.api_connection.run_report',
                    new_callable=lambda: lambda a, b, c, d: True
                ), \
                unittest.mock.patch(
                    'coguard_cli.api_connection.get_latest_report',
                    new_callable=lambda: lambda a, b, c, d, e: None
                ):
            self.assertIsNone(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "biz",
                "zip",
                "org",
                ''
            ))

    def test_send_zip_file_for_scanning_with_org_204_not_failed_latest_report(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204,
            json = lambda: {"foo": "bar"}
        )
        mock_response_2 = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {"foo": "bar"}
        )
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ), \
                unittest.mock.patch(
                    'coguard_cli.api_connection.run_report',
                    new_callable=lambda: lambda a, b, c, d: True
                ), \
                unittest.mock.patch(
                    'coguard_cli.api_connection.get_latest_report',
                    new_callable=lambda: lambda a, b, c, d, e: "BOOO"
                ), \
                unittest.mock.patch(
                    'requests.get',
                    new_callable=lambda: lambda url, headers, timeout: mock_response_2
                ):
            self.assertDictEqual(api_connection.send_zip_file_for_scanning(
                "foo",
                "bar",
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "biz",
                "zip",
                "org",
                ''
            ), {"foo": "bar"})

    def test_send_zip_file_for_fixing_non_200_status(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(status_code = 200)
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ), \
            unittest.mock.patch(
                'tempfile.mkstemp',
                new_callable = lambda: lambda prefix, suffix: (0, "temp_zip")
            ), \
            unittest.mock.patch(
                'os.close'
            ):
            self.assertEqual(
                api_connection.send_zip_file_for_fixing(
                    "foo",
                    unittest.mock.Mock(
                        return_value = lambda: "token"),
                    "portal.coguard.io",
                    "ma_org"
                ),
                "temp_zip"
            )

    def test_send_zip_file_for_fixing(self):
        """
        Testing the function and send a non 200 code.
        """
        mock_response = unittest.mock.Mock(status_code = 404)
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open()), \
                unittest.mock.patch(
                    'requests.post',
                    new_callable=lambda: lambda url, headers, data, timeout: mock_response
                ):
            self.assertIsNone(api_connection.send_zip_file_for_fixing(
                "foo",
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "portal.coguard.io",
                "ma_org"
            ))

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
                new_callable=lambda: lambda url, timeout: mock_response):
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
                new_callable=lambda: lambda url, timeout: mock_response):
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
                new_callable=lambda: lambda url, headers, json, timeout: mock_response):
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
                new_callable=lambda: lambda url, headers, json, timeout: mock_response):
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
                new_callable=lambda: lambda url, headers, json, timeout: mock_response):
            api_connection.mention_referrer(
                "foo",
                "bar",
                "baz"
            )

    def test_run_report(self):
        """
        Checks the running of the latest report with False outcome.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420
        )
        with unittest.mock.patch(
                'requests.put',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.run_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                "scan_identifier",
                "organization"
            )
            self.assertFalse(result)

    def test_run_report_true(self):
        """
        Checks the running of the latest report with True outcome.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204
        )
        with unittest.mock.patch(
                'requests.put',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.run_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                "scan_identifier",
                "organization"
            )
            self.assertTrue(result)

    def test_get_latest_report_bad_response(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_latest_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                "scan_identifier",
                "organization",
                "username"
            )
            self.assertIsNone(result)

    def test_get_latest_report_good_response_empty(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: []
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_latest_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                "scan_identifier",
                "organization",
                "username"
            )
            self.assertIsNone(result)

    def test_get_latest_report_good_response_non_empty(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_result = {"failed": []}
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: [mock_result]
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_latest_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                "scan_identifier",
                "organization",
                "username"
            )
            self.assertEqual(result, mock_result)

    def test_get_fixable_rule_list_bad_response_ogranization(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420,
            json = lambda: []
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_fixable_rule_list(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                None,
                'organization'
            )
            self.assertListEqual(result, [])

    def test_get_fixable_rule_list_ogranization(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: ["foo"]
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_fixable_rule_list(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                None,
                'organization'
            )
            self.assertListEqual(result, ["foo"])

    def test_get_fixable_rule_list_bad_response_user_name(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420,
            json = lambda: []
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_fixable_rule_list(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                'user_name',
                None
            )
            self.assertListEqual(result, [])

    def test_get_fixable_rule_list_user_name(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: ["foo"]
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            result = api_connection.get_fixable_rule_list(
                unittest.mock.Mock(
                    return_value = lambda: "token"),
                "https://portal.coguard.io",
                'user_name',
                None
            )
            self.assertListEqual(result, ["foo"])

    def test_log(self):
        """
        Checks the log endpoint.
        """
        mock_response = unittest.mock.Mock(
            status_code = 204
        )
        with unittest.mock.patch(
                'requests.post',
                new_callable=lambda: lambda url, headers, json, timeout: mock_response):
            api_connection.log(
                "foo",
                "https://portal.coguard.io"
            )

    def test_log_with_error(self):
        """
        Checks the log endpoint.
        """
        mock_response = unittest.mock.Mock(
            status_code = 500
        )
        with unittest.mock.patch(
                'requests.post',
                new_callable=lambda: lambda url, headers, json, timeout: mock_response):
            api_connection.log(
                "foo",
                "https://portal.coguard.io"
            )

    def test_download_report_report_bad_response(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        def mock_raise():
            raise Exception("foo")
        mock_response = unittest.mock.Mock(
            status_code = 420,
            raise_for_status = lambda: None,
            __enter__ = lambda x: unittest.mock.Mock(
                raise_for_status = mock_raise(),
                iter_content = lambda chunk_size: ["foo"]
            ),
            __exit__ = lambda w, x, y, z: None
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout: mock_response):
            with self.assertRaises(Exception):
                api_connection.download_report(
                    unittest.mock.Mock(
                        return_value = lambda: "token"
                    ),
                    "https://portal.coguard.io",
                    "organization",
                    "username",
                    "scan_identifier",
                    "cluster_name",
                    "report_name"
                )

    def test_download_report_good_response_organization(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: [],
            raise_for_status = lambda: None,
            __enter__ = lambda x: unittest.mock.Mock(
                raise_for_status = lambda: None,
                iter_content = lambda chunk_size: ["foo"]
            ),
            __exit__ = lambda w, x, y, z: None
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout, stream: mock_response), \
                unittest.mock.patch(
                    'builtins.open',
                    unittest.mock.mock_open()):
            api_connection.download_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"
                ),
                "https://portal.coguard.io",
                "organization",
                "username",
                "scan_identifier",
                "cluster_name",
                "report_name"
            )

    def test_download_report_good_response_user(self):
        """
        Checks the retrieval of the latest report with bad response.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: [],
            raise_for_status = lambda: None,
            __enter__ = lambda x: unittest.mock.Mock(
                raise_for_status = lambda: None,
                iter_content = lambda chunk_size: ["foo"]
            ),
            __exit__ = lambda w, x, y, z: None
        )
        with unittest.mock.patch(
                'requests.get',
                new_callable=lambda: lambda url, headers, timeout, stream: mock_response), \
                unittest.mock.patch(
                    'builtins.open',
                    unittest.mock.mock_open()):
            api_connection.download_report(
                unittest.mock.Mock(
                    return_value = lambda: "token"
                ),
                "https://portal.coguard.io",
                None,
                "username",
                "scan_identifier",
                "cluster_name",
                "report_name"
            )
