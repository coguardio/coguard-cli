"""
Tests for the token class.
"""

import unittest
import unittest.mock
import requests
from coguard_cli.auth.token import Token, choose_organization
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.auth.enums import DealEnum

class TestTokenClass(unittest.TestCase):
    """
    The class for testing the token class.
    """

    def test_get_public_key_status_not_200(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io"
        )
        token = Token("foo", mock_config_object)
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = token.get_public_key()
            self.assertIsNone(result)

    def test_get_public_key_status_200_no_public_key(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {}
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io/auth"
        )
        token = Token("foo", mock_config_object)
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = token.get_public_key()
            self.assertIsNone(result)

    def test_get_public_key_status_200_public_key(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {"public_key": "123456"}
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io/auth"
        )
        token = Token("foo", mock_config_object)
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = token.get_public_key()
            self.assertEqual(result, "123456")

    def test_get_decoded_jwt_token(self):
        """
        Tests the decoded jwt token.
        """
        mock_result = unittest.mock.Mock()
        mock_jwt = unittest.mock.Mock(
            decode = lambda token, public_key: mock_result
        )
        with unittest.mock.patch(
                'jwt.JWT',
                return_value=mock_jwt
        ), \
        unittest.mock.patch(
                'jwt.jwk_from_pem',
                new_callable = lambda: lambda b: "foo"
        ):
            token = Token("foo", {})
            result = token.get_decoded_jwt_token(
                "bar"
            )
            self.assertEqual(result, mock_result)

    def test_extract_organization_from_token_no_pk(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: ""
        ):
            token = Token("foo", {})
            result = token.extract_organization_from_token()
            self.assertIsNone(result)

    def test_extract_organization_from_token_pk_empty(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {}
        ):
            token = Token("foo", {})
            result = token.extract_organization_from_token()
            self.assertIsNone(result)

    def test_extract_organization_from_token_pk(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {"organization": "bar"}
        ), \
        unittest.mock.patch.dict('os.environ', {}, clear=True):
            token = Token("foo", {})
            result = token.extract_organization_from_token()
            self.assertEqual(result, "bar")

    def test_extract_organization_from_token_single_entry_list(self):
        """
        Tests the extraction of the organization key from the token when the
        token carries a list with exactly one organization.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {"organization": ["bar"]}
        ), \
        unittest.mock.patch.dict('os.environ', {}, clear=True):
            token = Token("foo", {})
            result = token.extract_organization_from_token()
            self.assertEqual(result, "bar")

    def test_extract_organization_from_token_single_entry_not_requested(self):
        """
        Tests that requesting an organization other than the only one in the
        token yields no organization.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {"organization": "bar"}
        ), \
        unittest.mock.patch.dict('os.environ', {}, clear=True):
            token = Token("foo", {})
            self.assertIsNone(token.extract_organization_from_token("baz"))
            self.assertEqual(token.extract_organization_from_token("bar"), "bar")

    def test_extract_organization_from_token_multiple_entries(self):
        """
        Tests that the extraction of the organization key from a token with
        several organizations defers the choice.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {
                    "organization": ["foo", "bar"]
                }
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.choose_organization',
                return_value="bar"
        ) as choose_mock:
            token = Token("foo", {})
            result = token.extract_organization_from_token("bar")
            self.assertEqual(result, "bar")
            choose_mock.assert_called_once_with(["foo", "bar"], "bar")

    def test_extract_deal_type_from_token_no_pk(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: ""
        ):
            token = Token("foo", {})
            result = token.extract_deal_type_from_token()
            self.assertEqual(result, DealEnum.FREE)

    def test_extract_deal_type_from_token_pk_no_deal_id(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "foo"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, pk: {}
        ):
            token = Token("foo", {})
            result = token.extract_deal_type_from_token()
            self.assertEqual(result, DealEnum.FREE)

    def test_extract_deal_type_from_token_pk_deal_id(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_public_key',
                new_callable=lambda: lambda c: "foo"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.token.Token.get_decoded_jwt_token',
                new_callable=lambda: lambda token, pk: {
                    "realm_access": {
                        "roles": [
                            "DEV"
                        ]
                    }
                }):
            token = Token("foo", {})
            result = token.extract_deal_type_from_token()
            self.assertEqual(result, DealEnum.DEV)

    def test_authenticate_to_server_empty_config_object(self):
        """
        Tests that the authentication returns None if the configuration object is None
        """
        token = Token("foo", None)
        self.assertIsNone(token.authenticate_to_server())

    def test_authenticate_to_server_non_empty_config_object_404(self):
        """
        Tests that the authentication returns None if the status code
        is not 200.
        """
        config_obj = CoGuardCliConfig("foo", "bar")
        def new_callable(url, data, timeout):
            response = requests.Response()
            setattr(response, 'status_code', 404)
            return response
        with unittest.mock.patch('requests.post',
                                 new_callable=lambda: new_callable):
            token = Token("foo", config_obj)
            self.assertIsNone(token.authenticate_to_server())

    def test_authenticate_to_server_non_empty_config_object_success(self):
        """
        Tests that the authentication returns None if the status code
        is not 200.
        """
        config_obj = CoGuardCliConfig("foo", "bar")
        def new_callable(url, data, timeout):
            response = requests.Response()
            setattr(response, 'status_code', 200)
            return response
        def new_json(arg):
            return {
                "access_token": "foo"
            }
        with unittest.mock.patch('requests.post',
                                 new_callable=lambda: new_callable), \
             unittest.mock.patch('requests.Response.json',
                                 new_callable=lambda: new_json):
            token = Token("foo", config_obj)
            result = token.authenticate_to_server()
            self.assertIsNotNone(result)
            self.assertEqual(result, "foo")

class TestChooseOrganization(unittest.TestCase):
    """
    The class for testing the choice between several organizations of an
    account.
    """

    def test_the_environment_is_asked_before_the_operator(self):
        """
        Tests that the environment variable decides, and that nothing is read
        from the standard input when it does.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "bar"}
        ), \
        unittest.mock.patch('builtins.input') as input_mock:
            self.assertEqual(choose_organization(["foo", "bar"]), "bar")
            input_mock.assert_not_called()

    def test_the_command_line_is_asked_before_the_environment(self):
        """
        Tests that `--organization` decides over the environment variable, and
        that nothing is read from the standard input when it does.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "foo"}
        ), \
        unittest.mock.patch('builtins.input') as input_mock:
            self.assertEqual(choose_organization(["foo", "bar"], " bar "), "bar")
            input_mock.assert_not_called()

    def test_an_empty_command_line_value_falls_back_to_the_environment(self):
        """
        Tests that an empty `--organization` is as good as none.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "bar"}
        ):
            self.assertEqual(choose_organization(["foo", "bar"], " "), "bar")

    def test_a_command_line_organization_the_account_does_not_have(self):
        """
        Tests that `--organization` naming an organization outside the token is
        an error, even if the environment variable names a valid one.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "bar"}
        ), \
        unittest.mock.patch('builtins.input') as input_mock:
            self.assertIsNone(choose_organization(["foo", "bar"], "baz"))
            input_mock.assert_not_called()

    def test_the_only_organization_is_used_without_a_request(self):
        """
        Tests that an account with one organization needs no choice.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
        unittest.mock.patch('builtins.input') as input_mock:
            self.assertEqual(choose_organization(["foo"]), "foo")
            input_mock.assert_not_called()

    def test_a_request_must_match_the_only_organization(self):
        """
        Tests that requesting an organization the account does not have is an
        error even if the account has only one, whether it is requested via
        `--organization` or via the environment.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True):
            self.assertEqual(choose_organization(["foo"], "foo"), "foo")
            self.assertIsNone(choose_organization(["foo"], "bar"))
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "bar"}
        ):
            self.assertIsNone(choose_organization(["foo"]))

    def test_surrounding_space_in_the_environment_is_ignored(self):
        """
        Tests that a value which a credentials file or a unit file left a space
        or a newline in still names its organization.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": " bar\n"}
        ):
            self.assertEqual(choose_organization(["foo", "bar"]), "bar")

    def test_an_organization_the_account_does_not_have_is_not_a_choice(self):
        """
        Tests that an environment variable naming an organization outside the
        token is an error rather than a reason to ask or to guess.
        """
        with unittest.mock.patch.dict(
                'os.environ',
                {"COGUARD_ORGANIZATION": "baz"}
        ), \
        unittest.mock.patch('builtins.input') as input_mock:
            self.assertIsNone(choose_organization(["foo", "bar"]))
            input_mock.assert_not_called()

    def test_nothing_is_asked_without_a_terminal_to_answer(self):
        """
        Tests that a run without a terminal -- a timer, a pipeline, a Cloudera
        role -- is told what to set instead of failing with an EOFError.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
             unittest.mock.patch(
                 'sys.stdin',
                 new_callable=lambda: unittest.mock.Mock(isatty=lambda: False)
             ), \
             unittest.mock.patch('builtins.input') as input_mock:
            self.assertIsNone(choose_organization(["foo", "bar"]))
            input_mock.assert_not_called()

    def test_a_closed_standard_input_is_not_a_terminal_either(self):
        """
        Tests the case where there is no standard input object at all.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
             unittest.mock.patch('sys.stdin', new=None), \
             unittest.mock.patch('builtins.input') as input_mock:
            self.assertIsNone(choose_organization(["foo", "bar"]))
            input_mock.assert_not_called()

    def test_the_operator_is_asked_at_a_terminal(self):
        """
        Tests that the choice is asked for interactively when it can be.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
             unittest.mock.patch(
                 'sys.stdin',
                 new_callable=lambda: unittest.mock.Mock(isatty=lambda: True)
             ), \
             unittest.mock.patch('builtins.input', return_value="bar"):
            self.assertEqual(choose_organization(["foo", "bar"]), "bar")

    def test_an_empty_answer_is_the_first_organization(self):
        """
        Tests that pressing enter takes the default which the prompt names.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
             unittest.mock.patch(
                 'sys.stdin',
                 new_callable=lambda: unittest.mock.Mock(isatty=lambda: True)
             ), \
             unittest.mock.patch('builtins.input', return_value=""):
            self.assertEqual(choose_organization(["foo", "bar"]), "foo")

    def test_an_invalid_answer_is_asked_again(self):
        """
        Tests that a typo at the prompt repeats the question.
        """
        with unittest.mock.patch.dict('os.environ', {}, clear=True), \
             unittest.mock.patch(
                 'sys.stdin',
                 new_callable=lambda: unittest.mock.Mock(isatty=lambda: True)
             ), \
             unittest.mock.patch(
                 'builtins.input',
                 side_effect=["baz", "bar"]
             ) as input_mock:
            self.assertEqual(choose_organization(["foo", "bar"]), "bar")
            self.assertEqual(input_mock.call_count, 2)
