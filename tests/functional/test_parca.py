# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import logging
import unittest
from pathlib import Path
from platform import uname

from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd

from parca import Parca
from tests.helpers import (
    DEFAULT_PARCA_CONFIG,
    file_content_equals_string,
    install_fake_daemon,
    render_template,
)

logger = logging.getLogger(__name__)


def _setup_test_parca(parca):
    parca.install()
    parca.configure(DEFAULT_PARCA_CONFIG)
    parca.start()


class TestParca(unittest.TestCase):
    def setUp(self):
        self.parca = Parca()
        install_fake_daemon("./parca")

    def test_install(self):
        self.parca.install()

        # Check installation of dependencies first
        kernel_version = uname().release
        dependencies = ["llvm", "binutils", "elfutils", f"linux-headers-{kernel_version}"]
        # Loop over dependencies, ensure they are installed
        for d in dependencies:
            package = apt.DebianPackage.from_system(d)
            self.assertTrue(package.present)

        self.assertTrue(self.parca.BIN_PATH.exists())

    def test_start(self):
        _setup_test_parca(self.parca)
        self.assertTrue(systemd.service_running(self.parca.SVC_NAME))
        self.parca.remove()

    def test_stop(self):
        _setup_test_parca(self.parca)
        self.parca.stop()
        self.assertFalse(systemd.service_running(self.parca.SVC_NAME))
        self.parca.remove()

    def test_remove(self):
        _setup_test_parca(self.parca)
        self.parca.remove()

        paths = [self.parca.BIN_PATH, "/etc/parca", self.parca.SVC_PATH]
        for path in paths:
            self.assertFalse(Path(path).exists())

        self.assertFalse(systemd.service_running(self.parca.SVC_NAME))

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

        prof_dir = self.parca.PROFILE_PATH
        self.assertTrue(prof_dir.exists())
        self.assertEqual(prof_dir.owner(), self.parca.SVC_NAME)

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

    def test_create_user(self):
        self.parca._create_user()
        self.assertTrue(passwd.user_exists(self.parca.SVC_NAME))
