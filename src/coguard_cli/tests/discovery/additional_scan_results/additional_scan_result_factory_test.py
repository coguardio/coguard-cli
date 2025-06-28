"""
Test Module for the AdditionalScanResult class
"""

import unittest
from unittest.mock import patch
from typing import Optional, Dict
from coguard_cli.discovery.additional_scan_results.additional_scan_result_producer_abc import AdditionalScanResult

class TestAdditionalScanResult(unittest.TestCase):

    def setUp(self):
        # Create a concrete mock subclass of AdditionalScanResult
        class MockScanResult(AdditionalScanResult):
            def perform_external_scan(self, path_to_file_system: str, additional_parameters: Optional[Dict] = None) -> Optional[str]:
                return super().perform_external_scan(path_to_file_system, additional_parameters)

            def translate_external_scan_result(self, path_to_scan_result: str) -> Optional[str]:
                return super().translate_external_scan_result(path_to_scan_result)

            def get_external_scan_identifier(self) -> str:
                return "mock_scanner"

        self.mock_instance = MockScanResult()

    @patch.object(AdditionalScanResult, 'perform_external_scan')
    @patch.object(AdditionalScanResult, 'translate_external_scan_result')
    @patch('shutil.rmtree')
    def test_successful_scan_and_translation(
        self,
        mock_rmtree,
        mock_translate,
        mock_perform_scan
    ):
        mock_perform_scan.return_value = '/tmp/mock_scan_result'
        mock_translate.return_value = '/tmp/mock_coguard_result'

        result = self.mock_instance.perform_external_scan_and_translation(
            '/fake/filesystem', {'param': 'value'}
        )

        self.assertEqual(result, '/tmp/mock_coguard_result')
        mock_perform_scan.assert_called_once_with('/fake/filesystem', {'param': 'value'})
        mock_translate.assert_called_once_with('/tmp/mock_scan_result')
        mock_rmtree.assert_called_once_with('/tmp/mock_scan_result')

    @patch('shutil.rmtree')
    def test_scan_returns_none(self, mock_rmtree):
        with self.assertLogs(level='ERROR') as cm:
            result = self.mock_instance.perform_external_scan_and_translation('/fake/filesystem', None)
        self.assertIsNone(result)
        self.assertIn("An error occurred while scanning with the external method for mock_scanner", cm.output[0])
        mock_rmtree.assert_called_once_with(None)

    @patch.object(AdditionalScanResult, 'perform_external_scan', return_value='/tmp/mock_scan_result')
    @patch.object(AdditionalScanResult, 'translate_external_scan_result', return_value=None)
    @patch.object(AdditionalScanResult, 'get_external_scan_identifier', return_value='mock_scanner')
    @patch('shutil.rmtree')
    def test_translation_returns_none(self, mock_rmtree, mock_identifier, mock_translate, mock_perform_scan):
        with self.assertLogs(level='ERROR') as cm:
            result = self.mock_instance.perform_external_scan_and_translation('/fake/filesystem', None)
        self.assertIsNone(result)
        self.assertIn("An error occurred while trying to translate the external scanner", cm.output[0])
        mock_rmtree.assert_called_once_with('/tmp/mock_scan_result')

    @patch.object(AdditionalScanResult, 'get_external_scan_identifier', return_value='mock_scanner')
    def test_filesystem_none(self, mock_identifier):
        with self.assertLogs(level='ERROR') as cm:
            result = self.mock_instance.perform_external_scan_and_translation(None, {})
        self.assertIsNone(result)
        self.assertIn("Unexpectedly, the folder where the filesystem was located is None", cm.output[0])
