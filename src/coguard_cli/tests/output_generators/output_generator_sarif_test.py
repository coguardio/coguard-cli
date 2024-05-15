"""
The test module for the sarif output generator.
"""

import unittest
import unittest.mock
from coguard_cli.output_generators.output_generator_sarif import \
    translate_result_to_sarif

class TestTranslateToSarif(unittest.TestCase):
    """
    The unit tests for the output generator Sarif module.
    """

    def test_translate_result_to_sarif_empty_result
