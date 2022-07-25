# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import os
from unittest.mock import patch

from pyfakefs.fake_filesystem_unittest import TestCase

from parca import Parca, ParcaInstallError
from tests.helpers import (
    DEFAULT_PARCA_CONFIG,
    FAKE_PWUID,
    file_content_equals_string,
    render_template,
)


# This looks like a lot of patches - these functions are tested more thoroughly in the
# functional test suite - here we just test the logic / flow of functions
@patch("parca.Parca._install_dependencies", lambda x: True)
@patch("parca.Parca._create_user", lambda x: True)
@patch("parca.passwd.remove_user", lambda x: True)
@patch("parca.passwd.user_exists", lambda x="foo": FAKE_PWUID)
@patch("parca.systemd.daemon_reload", lambda x=True: True)
@patch("parca.systemd.service_resume", lambda x=True: True)
@patch("parca.systemd.service_restart", lambda x=True: True)
@patch("parca.systemd.service_running", lambda x=True: True)
@patch("parca.systemd.service_stop", lambda x=True: True)
class TestParca(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        # Add some things the code expect to be in place on the filesystem
        with open("./parca", "w+") as f:
            f.write("""#!/bin/bash\nwhile true; do sleep 2; done""")
        self.fs.add_real_file("src/configs/parca.service")
        self.fs.add_real_file("src/configs/parca.yaml")
        os.chmod("./parca", 0o755)
        os.makedirs("/etc/systemd/system", exist_ok=True)
        os.makedirs("/etc/parca", exist_ok=True)
        os.makedirs("/var/lib", exist_ok=True)

        self.parca = Parca()

    def test_install(self):
        result = self.parca.install()
        self.assertTrue(result)
        self.assertTrue(os.path.exists("/usr/bin/parca"))

    def test_install_failures(self):
        with patch("parca.Parca._install_dependencies", lambda x=True: False):
            try:
                self.parca.install()
            except ParcaInstallError as e:
                self.assertEqual(str(e), "failed installing parca dependencies")
        with patch("parca.Parca._install_parca_bin", lambda x=True: False):
            try:
                self.parca.install()
            except ParcaInstallError as e:
                self.assertEqual(str(e), "failed installing parca")

    @patch("parca.Parca._create_user", lambda x: True)
    def test_remove(self):
        result = self.parca.install()
        self.parca.configure(DEFAULT_PARCA_CONFIG)
        self.parca.remove()

        paths = ["/usr/bin/parca", "/etc/parca", "/etc/systemd/system/parca.service"]
        for path in paths:
            self.assertFalse(os.path.exists(path))

        self.assertTrue(result)

    def test_configure_storage_persist(self):
        config = {"storage-persist": True, "juju-scrape-interval": 5}
        self.parca.configure(config)

        storage_config = [
            "--storage-in-memory=false",
            "--storage-persist",
            f"--storage-path={self.parca.PROFILE_PATH}",
        ]

        # Check the systemd service was rendered correctly
        svc = render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(file_content_equals_string(self.parca.SVC_PATH, svc))
        self.assertTrue(os.path.exists(self.parca.PROFILE_PATH))
        self.assertEqual(os.stat(self.parca.PROFILE_PATH).st_uid, 1000)

    def test_configure_storage_in_memory(self):
        self.parca.configure(DEFAULT_PARCA_CONFIG)
        storage_config = ["--storage-in-memory=true", "--storage-active-memory=1073741824"]
        # Check the systemd service was rendered correctly
        svc = render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(file_content_equals_string(self.parca.SVC_PATH, svc))

    def test_configure_scrape_interval(self):
        self.parca.configure(DEFAULT_PARCA_CONFIG)
        # Check the parca.yaml was rendered correctly
        cfg = render_template("src/configs/parca.yaml", {"interval": 5})
        self.assertTrue(file_content_equals_string(self.parca.CONFIG_PATH, cfg))

    def test_configure_fail(self):
        with patch("parca.render_template", side_effect=Exception):
            result = self.parca.configure(DEFAULT_PARCA_CONFIG)
            self.assertFalse(result)
