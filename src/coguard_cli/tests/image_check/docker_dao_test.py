"""
Tests for the functions in the Docker DAO module
"""

import subprocess
import unittest
import unittest.mock
from coguard_cli.image_check import docker_dao

class TestDockerDao(unittest.TestCase):
    """
    The class for testing the auth module.
    """

    def test_image_name_from_custom_repo_true(self):
        """
        Tests if an image name is coming from a custom repository,
        and returns true, because we are giving it a custom repo.
        """
        image_url = "4556.dkr.ecr.ap-south-1.amazonaws.com/erp:1.0"
        self.assertTrue(docker_dao.is_image_name_from_custom_repo(image_url))

    def test_image_name_from_custom_repo_false(self):
        """
        Tests if an image name is coming from a custom repository,
        and returns false, because we are not giving a custom repo.
        """
        image_url = "erp:1.0"
        self.assertFalse(docker_dao.is_image_name_from_custom_repo(image_url))

    def test_image_name_from_custom_repo_false_more_than_one_line(self):
        """
        Tests if an image name is coming from a custom repository,
        and returns false, because we are not giving a custom repo.
        """
        image_url = "jboss/keycloak"
        self.assertFalse(docker_dao.is_image_name_from_custom_repo(image_url))

    def test_create_docker_image_forbidden(self):
        """
        Tests the creation of Docker image where a custom repo is not allowed,
        but used.
        """
        image_url = "4556.dkr.ecr.ap-south-1.amazonaws.com/erp:1.0"
        self.assertIsNone(docker_dao.create_docker_image(image_url))

    def test_create_docker_image_allowed(self):
        """
        Tests the creation of Docker image where a custom repo is not allowed,
        but used.
        """
        image_url = "erp:1.0"
        with unittest.mock.patch("subprocess.run") as mock_sub_process:
            self.assertIsNotNone(docker_dao.create_docker_image(image_url))
            mock_sub_process.assert_called_once()

    def test_create_docker_image_allowed_but_execution_error(self):
        """
        Tests the creation of Docker image where a custom repo is not allowed,
        but used.
        """
        def new_callable(cmd, check, shell, stdout, stderr, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        image_url = "erp:1.0"
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=(lambda: new_callable)
        ):
            self.assertIsNone(docker_dao.create_docker_image(image_url))


    def test_store_image_file_system_arg_none(self):
        """
        Tests the storing of the image on the file system, with a None parameter.
        """
        self.assertIsNone(docker_dao.store_image_file_system(None))

    def test_store_image_not_none_but_tarfile_not_there(self):
        """
        Tests the storing of the image on the file system, with not None parameter.
        """
        image_uuid = "7397d854-7c3d-485a-a247-61e2bf9360b8"
        with unittest.mock.patch(
                "tempfile.mkdtemp",
                new_callable=lambda: lambda prefix: "/foo/bar"
             ), \
             unittest.mock.patch("subprocess.run") as mock_sub_process:
            self.assertIsNone(
                docker_dao.store_image_file_system(image_uuid)
            )
            mock_sub_process.assert_called_once()

    def test_store_image_not_none_but_docker_image_error(self):
        """
        Tests the storing of the image on the file system, but an error in the subprocess
        call.
        """
        def new_callable(cmd, check, shell, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        image_uuid = "7397d854-7c3d-485a-a247-61e2bf9360b8"
        with unittest.mock.patch(
                "tempfile.mkdtemp",
                new_callable=lambda: lambda prefix: "/foo/bar"
             ), \
             unittest.mock.patch(
                "subprocess.run",
                new_callable = lambda: new_callable
        ):
            self.assertIsNone(
                docker_dao.store_image_file_system(image_uuid)
            )

    def test_store_image_not_none_with_tar_file(self):
        """
        Tests the storing of the image on the file system with no error on
        the tar.
        """
        image_uuid = "7397d854-7c3d-485a-a247-61e2bf9360b8"
        def new_callable(path):
            mock = unittest.mock.MagicMock()
            mock.extractall.return_value = 0
            return unittest.mock.mock_open(mock=mock)
        with unittest.mock.patch(
                "tempfile.mkdtemp",
                new_callable=lambda: lambda prefix: "/foo/bar"
             ), \
             unittest.mock.patch("subprocess.run") as mock_sub_process, \
             unittest.mock.patch('tarfile.open',
                                 new_callable=lambda: new_callable), \
             unittest.mock.patch("os.remove"):
            self.assertIsNotNone(
                docker_dao.store_image_file_system(image_uuid)
            )
            mock_sub_process.assert_called_once()

    def test_get_inspect_result_none_container_name(self):
        """
        Tests the inspection of the container and the correct output.
        In this case, if it is called with None, it should return None.
        """
        self.assertIsNone(
            docker_dao.get_inspect_result(None)
        )

    def test_get_inspect_result(self):
        """
        Tests the inspection of the container and the correct output.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            return subprocess.CompletedProcess(
                args=["foo"],
                stdout="[{}]",
                returncode=0
            )
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertDictEqual(
                docker_dao.get_inspect_result("foo"),
                {}
            )

    def test_get_inspect_result_call_process_error(self):
        """
        Tests the inspection of the container and the correct output.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertIsNone(
                docker_dao.get_inspect_result("foo"),
            )

    def test_get_inspect_result_json_decode_error(self):
        """
        Tests the inspection of the container and the correct output.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            return subprocess.CompletedProcess(
                args=["foo"],
                stdout="[", # this will cause the json error
                returncode=0
            )
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertIsNone(
                docker_dao.get_inspect_result("foo"),
            )

    def test_get_inspect_result_non_dict(self):
        """
        Tests the inspection of the container and the correct output.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            return subprocess.CompletedProcess(
                args=["foo"],
                stdout="{}",
                returncode=0
            )
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertIsNone(
                docker_dao.get_inspect_result("foo")
            )

    def test_rm_temporary_container_name_none_input(self):
        """
        Tests the function rm_temporary_container_name with None input
        """
        with unittest.mock.patch(
                "subprocess.run"
        ) as run_fn:
            docker_dao.rm_temporary_container_name(None)
            run_fn.assert_not_called()

    def test_rm_temporary_container_name(self):
        """
        Tests the function rm_temporary_container_name with proper input
        """
        with unittest.mock.patch(
                "subprocess.run"
        ) as run_fn:
            docker_dao.rm_temporary_container_name("foo")
            run_fn.assert_called_once()

    def test_rm_temporary_container_name_run_exception(self):
        """
        Tests the function rm_temporary_container_name with proper input
        """
        def new_callable(cmd, check, shell, stdout, stderr, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        with unittest.mock.patch(
                "subprocess.run",
                new_callable = lambda: new_callable
        ):
            docker_dao.rm_temporary_container_name("foo")

    def test_extract_docker_file(self):
        """
        Tests the extraction of the dockerfile.
        """
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"foo #(nop) bar baz\nbaf"
                )
        ):
            self.assertEqual(
                docker_dao.extract_docker_file("foo"),
                """baf\n bar baz""")

    def test_extract_docker_file_call_error(self):
        """
        Tests the extraction of the dockerfile.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertIsNone(
                docker_dao.extract_docker_file("foo")
            )

    def test_get_docker_version(self):
        """
        Testing to check the Docker version.
        """
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"foo"
                )
        ):
            self.assertEqual(
                docker_dao.check_docker_version(),
                """foo""")

    def test_get_docker_version_with_error(self):
        """
        Testing to check the Docker version.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable):
            self.assertIsNone(docker_dao.check_docker_version())

    def test_extract_all_existing_docker_images(self):
        """
        Tests the extraction of the dockerfile.
        """
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"foo\nbar\nbaz"
                )
        ):
            self.assertEqual(
                docker_dao.extract_all_installed_docker_images(),
                [
                    "foo",
                    "bar",
                    "baz"
                ])

    def test_extract_all_existing_docker_images_with_nones_in_between(self):
        """
        Tests the extraction of the dockerfile.
        """
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"foo\nbar\n<none>\n<none>:<none>\nbaz"
                )
        ):
            self.assertEqual(
                docker_dao.extract_all_installed_docker_images(),
                [
                    "foo",
                    "bar",
                    "baz"
                ])

    def test_extract_all_existing_docker_images_error(self):
        """
        Tests the extraction of the dockerfile.
        """
        def new_callable(cmd, check, shell, capture_output, timeout):
            raise subprocess.CalledProcessError(1, cmd)
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: new_callable
        ):
            self.assertEqual(
                docker_dao.extract_all_installed_docker_images(),
                []
            )
