"""
This is a testing module for the common functions inside the cloud_scan module.
"""

import unittest
import unittest.mock

from coguard_cli import cloud_scan
from coguard_cli.auth.enums import DealEnum


def provider(name="cloudera", cluster_representation=None, iac_folder="/tmp/iac"):
    """
    A helper producing a cloud provider double. A provider which returns a
    cluster representation of its own skips the Infrastructure as Code path.
    """
    result = unittest.mock.MagicMock()
    result.get_cloud_provider_name.return_value = name
    result.extract_cluster_representation.return_value = cluster_representation
    result.extract_iac_files_for_account.return_value = iac_folder
    return result


def perform_scan(cloud_provider, provider_name="cloudera",
                 collected_config_file_tuple=None, dry_run=False):
    """
    Runs a cloud provider scan with everything which touches the file system or
    the network replaced, and returns the mock of the upload.
    """
    upload = unittest.mock.MagicMock()
    with unittest.mock.patch(
            "coguard_cli.cloud_scan.cloud_provider_factory",
            new_callable=lambda: lambda: [cloud_provider]
    ), unittest.mock.patch(
        "coguard_cli.folder_scan.find_configuration_files_and_collect",
        new_callable=lambda: lambda *args: collected_config_file_tuple
    ), unittest.mock.patch(
        "coguard_cli.folder_scan.create_zip_to_upload_from_file_system",
        new_callable=lambda: lambda *args: ("/tmp/zip", "location")
    ), unittest.mock.patch(
        "coguard_cli.cloud_scan.shutil.rmtree"
    ), unittest.mock.patch(
        "coguard_cli.cloud_scan.upload_and_evaluate_zip_candidate",
        new_callable=lambda: upload
    ):
        cloud_scan.perform_cloud_provider_scan(
            provider_name,
            None,
            DealEnum.ENTERPRISE,
            unittest.mock.MagicMock(),
            unittest.mock.MagicMock(),
            "organization",
            "https://portal.coguard.io/server",
            "formatted",
            1,
            "",
            dry_run
        )
    return upload


class TestCloudScanCommonFunc(unittest.TestCase):
    """
    The TestCase class with the common functions to test
    """

    def test_a_provider_which_is_not_implemented_does_not_upload(self):
        """
        A name which no factory entry answers to is an error, not an upload.
        """
        upload = perform_scan(provider(name="aws"), provider_name="gcp")
        upload.assert_not_called()

    def test_the_scan_identifier_of_a_cluster_is_taken_from_the_manifest(self):
        """
        A provider which produces the cluster representation itself names the
        cluster after what its own API calls it, and the back-end takes that name
        out of the manifest inside the zip. The report is then run and retrieved
        by name, so the name the scan is run under has to be the manifest one and
        not a name assembled from the provider.
        """
        upload = perform_scan(provider(
            cluster_representation=("/tmp/collected",
                                    {"name": "ozone_base_cluster"})
        ))
        upload.assert_called_once()
        self.assertEqual(upload.call_args[0][5], "ozone_base_cluster")

    def test_the_scan_identifier_of_an_iac_export_is_the_provider(self):
        """
        The Infrastructure as Code path sets the manifest name itself, so the two
        agree there, and a manifest without a name still produces a scan.
        """
        upload = perform_scan(
            provider(name="aws", cluster_representation=None),
            provider_name="aws",
            collected_config_file_tuple=("/tmp/collected", {})
        )
        upload.assert_called_once()
        self.assertEqual(upload.call_args[0][5], "aws_extraction")

    def test_a_provider_without_configuration_files_does_not_upload(self):
        """
        Neither path produced anything to scan.
        """
        upload = perform_scan(
            provider(cluster_representation=None),
            collected_config_file_tuple=None
        )
        upload.assert_not_called()

    def test_a_provider_without_an_iac_export_does_not_upload(self):
        """
        The export of the account failed altogether.
        """
        upload = perform_scan(
            provider(cluster_representation=None, iac_folder=None)
        )
        upload.assert_not_called()

    def test_a_dry_run_does_not_upload(self):
        """
        A dry run prints the zip it would have sent.
        """
        with unittest.mock.patch("coguard_cli.cloud_scan.dry_run_outp") as outp:
            upload = perform_scan(
                provider(cluster_representation=("/tmp/collected",
                                                 {"name": "ozone_base_cluster"})),
                dry_run=True
            )
        upload.assert_not_called()
        outp.assert_called_once()

    def test_provider_options_are_handed_to_the_provider(self):
        """
        The options of e.g. the Cloudera Manager connection are given to the
        provider before it is asked for the cluster.
        """
        cloud_provider = provider(
            cluster_representation=("/tmp/collected", {"name": "cluster"})
        )
        with unittest.mock.patch(
                "coguard_cli.cloud_scan.cloud_provider_factory",
                new_callable=lambda: lambda: [cloud_provider]
        ), unittest.mock.patch(
            "coguard_cli.folder_scan.create_zip_to_upload_from_file_system",
            new_callable=lambda: lambda *args: ("/tmp/zip", "location")
        ), unittest.mock.patch(
            "coguard_cli.cloud_scan.shutil.rmtree"
        ), unittest.mock.patch(
            "coguard_cli.cloud_scan.upload_and_evaluate_zip_candidate"
        ):
            cloud_scan.perform_cloud_provider_scan(
                "cloudera",
                None,
                DealEnum.ENTERPRISE,
                unittest.mock.MagicMock(),
                unittest.mock.MagicMock(),
                "organization",
                "https://portal.coguard.io/server",
                "formatted",
                1,
                "",
                False,
                {"cloudera_manager_url": "https://cm.example.com"}
            )
        cloud_provider.set_options.assert_called_once_with(
            {"cloudera_manager_url": "https://cm.example.com"}
        )

    def test_a_zip_which_could_not_be_created_does_not_upload(self):
        """
        The files were found, but the zip was not written.
        """
        upload = unittest.mock.MagicMock()
        with unittest.mock.patch(
                "coguard_cli.cloud_scan.cloud_provider_factory",
                new_callable=lambda: lambda: [provider(
                    cluster_representation=("/tmp/collected",
                                            {"name": "cluster"})
                )]
        ), unittest.mock.patch(
            "coguard_cli.folder_scan.create_zip_to_upload_from_file_system",
            new_callable=lambda: lambda *args: None
        ), unittest.mock.patch(
            "coguard_cli.cloud_scan.shutil.rmtree"
        ), unittest.mock.patch(
            "coguard_cli.cloud_scan.upload_and_evaluate_zip_candidate",
            new_callable=lambda: upload
        ):
            cloud_scan.perform_cloud_provider_scan(
                "cloudera",
                None,
                DealEnum.ENTERPRISE,
                unittest.mock.MagicMock(),
                unittest.mock.MagicMock(),
                "organization",
                "https://portal.coguard.io/server",
                "formatted",
                1,
                ""
            )
        upload.assert_not_called()
