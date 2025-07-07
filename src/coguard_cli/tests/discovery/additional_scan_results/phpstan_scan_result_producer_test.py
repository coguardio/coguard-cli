import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

from coguard_cli.discovery.additional_scan_results.phpstan_scan_result_producer import \
    PhpStanSastProducer

class TestPerformExternalScanPhpStan(unittest.TestCase):

    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("coguard_cli.docker_dao.run_external_scanner_container")
    def test_perform_external_scan_success(self, mock_run_scanner, mock_rmtree, mock_mkdtemp):
        mock_mkdtemp.return_value = "/tmp/fake_dir"
        mock_run_scanner.return_value = True

        scanner = PhpStanSastProducer()
        result = scanner.perform_external_scan("/some/path")

        self.assertEqual(result, "/tmp/fake_dir")
        mock_run_scanner.assert_called_once()
        mock_rmtree.assert_not_called()

    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("coguard_cli.docker_dao.run_external_scanner_container")
    def test_perform_external_scan_failure(self, mock_run_scanner, mock_rmtree, mock_mkdtemp):
        mock_mkdtemp.return_value = "/tmp/fake_dir"
        mock_run_scanner.return_value = False

        scanner = PhpStanSastProducer()
        result = scanner.perform_external_scan("/some/path")

        self.assertIsNone(result)
        mock_run_scanner.assert_called_once()
        mock_rmtree.assert_called_once_with("/tmp/fake_dir")

    @patch("tempfile.mkdtemp")
    @patch("json.dump")
    @patch("json.load")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_translate_external_scan_result_success(
        self, mock_file_open, mock_json_load, mock_json_dump, mock_mkdtemp
    ):
        # Setup
        fake_temp_dir = "/tmp/fake_dir"
        mock_mkdtemp.return_value = fake_temp_dir

        mock_json_load.return_value = {
            "files": {
                "/app/src/file.php": {
                    "messages": [
                        {
                            "message": "Undefined variable",
                            "line": 42
                        }
                    ]
                }
            }
        }

        scanner = PhpStanSastProducer()
        result = scanner.translate_external_scan_result("/some/input")

        self.assertEqual(result, fake_temp_dir)

        # Validate file read path
        mock_file_open.assert_any_call("/some/input/result.json", 'r', encoding='utf-8')

        # Validate file write path
        mock_file_open.assert_any_call(f"{fake_temp_dir}/result.json", 'w', encoding='utf-8')

        # Validate json.load was called once on the input file stream
        self.assertEqual(mock_json_load.call_count, 1)

        # Validate json.dump was called with correctly structured result
        args, kwargs = mock_json_dump.call_args
        dumped_result = args[0]

        self.assertIn("failed", dumped_result)
        self.assertEqual(len(dumped_result["failed"]), 1)
        self.assertEqual(dumped_result["failed"][0]["fromLine"], 42)

    @patch("tempfile.mkdtemp")
    @patch("json.dump")
    @patch("json.load", return_value={})
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_translate_external_scan_result_empty_input(
        self, mock_file_open, mock_json_load, mock_json_dump, mock_mkdtemp
    ):
        fake_temp_dir = "/tmp/fake_dir"
        mock_mkdtemp.return_value = fake_temp_dir

        scanner = PhpStanSastProducer()
        result = scanner.translate_external_scan_result("/some/input")

        self.assertEqual(result, fake_temp_dir)
        mock_json_dump.assert_called_once()
        dumped_data = mock_json_dump.call_args[0][0]
        self.assertEqual(dumped_data, {"failed": []})

if __name__ == "__main__":
    unittest.main()
