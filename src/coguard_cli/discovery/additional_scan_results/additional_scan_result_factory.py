"""
This is the factory for additional scan result producer functions.
"""

# pylint: disable=unused-import
from typing import Generator
from coguard_cli.discovery.additional_scan_results.trivy_sbom_scanning_result_producer import \
    TrivyCveProducer
from coguard_cli.discovery.additional_scan_results.phpstan_scan_result_producer import \
    PhpStanSastProducer

from coguard_cli.discovery.additional_scan_results.additional_scan_result_producer_abc \
    import AdditionalScanResult

def additional_scan_result_factory() -> Generator[AdditionalScanResult, None, None]:
    """
    The factory to get different external scan result outputs.
    """
    for cls in AdditionalScanResult.__subclasses__():
        yield cls()
