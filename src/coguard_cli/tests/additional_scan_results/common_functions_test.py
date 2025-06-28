"""
This is the module containing checks for the common functions in the
Additional Scan results module.
"""

import unittest
import unittest.mock
import coguard_cli.additional_scan_results

class TestCommonFunctionsAdditionalScans(unittest.TestCase):
    """
    The class to test the functions in coguard_cli.additional_scan_results.__init__
    """

    @unittest.mock.patch('coguard_cli.discovery.additional_scan_results.additional_scan_result_factory.additional_scan_result_factory')
    def test_perform_external_scans_and_return_folders(self, mock_factory):
        """
        Testing the external_scans_and_return_folders function
        """
        # Mock scan result objects
        mock_scan1 = unittest.mock.MagicMock()
        mock_scan1.get_external_scan_identifier.return_value = 'scanner_a'
        mock_scan1.perform_external_scan_and_translation.return_value = '/path/to/results_a'

        mock_scan2 = unittest.mock.MagicMock()
        mock_scan2.get_external_scan_identifier.return_value = 'scanner_b'
        mock_scan2.perform_external_scan_and_translation.return_value = '/path/to/results_b'

        # Mock factory to return both mock scanners
        mock_factory.return_value = [mock_scan1, mock_scan2]

        # Call the function with a selected subset
        result = coguard_cli.additional_scan_results.perform_external_scans_and_return_folders(
            path_to_filesystem='/fake/path',
            additional_parameters={'key': 'value'},
            selected_additional_scanners=['scanner_a']
        )

        # Check that only the selected scanner was run
        mock_scan1.perform_external_scan_and_translation.assert_called_once_with(
            '/fake/path', {'key': 'value'}
        )
        mock_scan2.perform_external_scan_and_translation.assert_not_called()

        expected_result = {'scanner_a': '/path/to/results_a'}
        self.assertEqual(result, expected_result)
