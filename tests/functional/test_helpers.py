import logging
import unittest
from pathlib import Path
from platform import uname
from subprocess import check_output

from charms.operator_libs_linux.v0 import apt, passwd
from ops.testing import Harness

from charm import PARCA_VERSION, ParcaOperatorCharm

logger = logging.getLogger(__name__)


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_install_dependencies(self):
        self.harness.charm._install_dependencies()
        kernel_version = uname().release
        dependencies = ["llvm", "binutils", "elfutils", f"linux-headers-{kernel_version}"]

        for d in dependencies:
            package = apt.DebianPackage.from_system(d)
            self.assertTrue(package.present)

    def test_fetch_parca_bin(self):
        self.harness.charm._fetch_parca_bin()
        self.assertTrue(Path("/usr/bin/parca").exists())
        parca_version = check_output(["/usr/bin/parca", "--version"])
        self.assertTrue(f"parca, version {PARCA_VERSION}" in parca_version.decode())

    def test_create_user(self):
        self.harness.charm._create_user()
        self.assertTrue(passwd.user_exists("parca"))

    def test_write_configs(self):
        self.harness.charm._write_configs()
        file_pairs = [
            ("tests/functional/parca.service", "/etc/systemd/system/parca.service"),
            ("src/configs/juju-introspect.service", "/etc/systemd/system/juju-introspect.service"),
            ("src/configs/parca.yaml", "/etc/parca/parca.yaml"),
        ]

        for pair in file_pairs:
            with open(pair[0]) as f0, open(pair[1]) as f1:
                self.assertListEqual(f0.readlines(), f1.readlines())
