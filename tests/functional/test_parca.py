# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import logging
import os
import unittest
from pathlib import Path
from platform import uname
from types import SimpleNamespace

import yaml
from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd
from jinja2 import Template

from parca import Parca, ParcaConfig

DEFAULT_PARCA_CONFIG = {
    "storage-persist": False,
    "memory-storage-limit": 1024,
    "juju-scrape-interval": 5,
}


def _file_content_equals_string(filename: str, expected: str):
    """Check if the contents of file 'filename' equal the 'expected' param."""
    with open(filename) as f:
        return f.read() == expected


def _render_template(template, context):
    """Render a Jinja2 template at the specified path with specified context.

    Return the rendered file as a string.
    """
    with open(template) as f:
        template = Template(f.read())
    return template.render(**context)


logger = logging.getLogger(__name__)


def _setup_test_parca(parca):
    parca.install()
    parca.configure(DEFAULT_PARCA_CONFIG)
    parca.start()


class TestParca(unittest.TestCase):
    def setUp(self):
        self.parca = Parca()
        with open("./parca", "w+") as f:
            # Simple bash loop that runs infinitely
            f.write("""#!/bin/bash\nwhile true; do sleep 2; done""")
        os.chmod("./parca", 0o755)

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

    def test_configure_systemd_storage_persist(self):
        config = {"storage-persist": True, "juju-scrape-interval": 5}
        self.parca.configure(config)

        storage_config = [
            "--storage-in-memory=false",
            "--storage-persist",
            f"--storage-path={self.parca.PROFILE_PATH}",
        ]

        # Check the systemd service was rendered correctly
        svc = _render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(_file_content_equals_string(self.parca.SVC_PATH, svc))

        prof_dir = self.parca.PROFILE_PATH
        self.assertTrue(prof_dir.exists())
        self.assertEqual(prof_dir.owner(), self.parca.SVC_NAME)

    def test_configure_systemd_storage_in_memory(self):
        self.parca.configure(DEFAULT_PARCA_CONFIG)
        storage_config = ["--storage-in-memory=true", "--storage-active-memory=1073741824"]
        # Check the systemd service was rendered correctly
        svc = _render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(_file_content_equals_string(self.parca.SVC_PATH, svc))

    def test_configure_parca_no_scrape_jobs(self):
        self.parca.configure(DEFAULT_PARCA_CONFIG)
        config = ParcaConfig(self.parca.PROFILE_PATH, [])
        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))

    def test_configure_parca_simple_scrape_jobs(self):
        self.parca.configure(DEFAULT_PARCA_CONFIG, [{"metrics_path": "foobar", "bar": "baz"}])
        config = ParcaConfig(self.parca.PROFILE_PATH, [{"metrics_path": "foobar", "bar": "baz"}])
        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))

    def test_create_user(self):
        self.parca._create_user()
        self.assertTrue(passwd.user_exists(self.parca.SVC_NAME))
