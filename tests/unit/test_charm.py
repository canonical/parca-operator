# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import base64
import inspect
import io
import os
import pathlib
from pathlib import Path
from platform import uname
from subprocess import CalledProcessError
from tarfile import ExtractError, ReadError
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from charms.operator_libs_linux.v0.apt import PackageError, PackageNotFoundError
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness
from pyfakefs.fake_filesystem_unittest import TestCase

from charm import ParcaOperatorCharm


def _fake_tarfile():
    """Returns a fake tarfile containing one file named 'parca'."""
    return io.BytesIO(
        base64.b64decode(
            "H4sIAAAAAAAAA+3OMQ7CMBAEQNe8wk+wg3HeY5AoUhAU4P8kiIIKRBEhpJkrVrq7Ys9tOrSwrjSrpSyZ+"
            "116zac+5NLVWpaZ9zl12xpiWrnXw+1ybVOMYRhPb/8+3f/UcRz3bdr8ugYAAAAAAAAAAABfugNLBOmnAC"
            "gAAA=="
        )
    )


def _systemd_unit_property(filename, property):
    """Takes a list of lines from a systemd unit file, returns the one with the specified prop."""
    with open(filename, "r") as f:
        lines = f.readlines()
    return [line for line in lines if line.startswith(f"{property}=")][0]


class TestCharm(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        # Add the charm's config.yaml manually as pyfakefs messes with things!
        filename = inspect.getfile(ParcaOperatorCharm)
        charm_dir = pathlib.Path(filename).parents[1]
        self.fs.add_real_file(charm_dir / "config.yaml")
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.install_stages = [
            "_install_dependencies",
            "_fetch_parca_bin",
            "_create_user",
            "_write_configs",
            "_open_port",
        ]

    def test_install_success(self):
        # Make all of the helpers pass, run the event handler
        for h in self.install_stages:
            setattr(self.harness.charm, h, lambda x=None: True)
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("installing parca"))

    def test_install_fail(self):
        # One by one, make helpers fail, ensure we block
        for h in self.install_stages:
            setattr(self.harness.charm, h, lambda x=None: False)
            self.harness.charm.on.install.emit()
            self.assertEqual(
                self.harness.charm.unit.status,
                BlockedStatus("failed to install parca, check logs"),
            )
            setattr(self.harness.charm, h, lambda x=None: True)

    @patch("charm.systemd.service_resume")
    def test_start(self, resume):
        self.harness.charm.on.start.emit()
        self.assertEqual(resume.call_count, 2)
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.systemd.service_restart")
    @patch("charm.systemd.daemon_reload")
    def test_config_changed(self, reload, restart):
        self.fs.add_real_directory("src/configs")
        os.makedirs("/etc/systemd/system", exist_ok=True)
        self.harness.update_config({"memory-storage-limit": 1024})
        reload.assert_called_once()
        restart.assert_called_with("parca")
        exec_line = _systemd_unit_property("/etc/systemd/system/parca.service", "ExecStart")
        self.assertTrue("--storage-active-memory=1073741824" in exec_line)
        self.harness.update_config({"memory-storage-limit": 2048})
        exec_line = _systemd_unit_property("/etc/systemd/system/parca.service", "ExecStart")
        self.assertTrue("--storage-active-memory=2147483648" in exec_line)

    @patch("charm.apt.update")
    @patch("charm.apt.add_package")
    def test_install_dependencies(self, install, upd):
        installed = self.harness.charm._install_dependencies()
        upd.assert_called_once()
        install.assert_called_with(
            ["llvm", "binutils", "elfutils", f"linux-headers-{uname().release}"]
        )
        self.assertTrue(installed)

    @patch("charm.apt.update")
    def test_install_dependencies_error(self, _):
        for e in [PackageNotFoundError, PackageError("foo")]:
            with patch("charm.apt.add_package", side_effect=e):
                installed = self.harness.charm._install_dependencies()
                self.assertFalse(installed)

    @patch("charm.urllib.request.urlopen", lambda x: _fake_tarfile())
    def test_fetch_parca_bin(self):
        fetched = self.harness.charm._fetch_parca_bin()
        # Check that the 'parca' file was extracted to the right location
        self.assertTrue(os.path.exists("/usr/bin/parca"))
        self.assertTrue(fetched)

    def test_fetch_parca_bin_network_error(self):
        for e in [URLError("foobar"), HTTPError("foo", 404, "foobar", {}, None)]:
            with patch("charm.urllib.request.urlopen", side_effect=e):
                fetched = self.harness.charm._fetch_parca_bin()
                self.assertFalse(fetched)
                self.assertFalse(os.path.exists("/usr/bin/parca"))

    @patch("charm.urllib.request.urlopen", lambda x: _fake_tarfile())
    def test_fetch_parca_bin_tarball_error(self):
        for e in [ExtractError, ReadError]:
            with patch("charm.tarfile.open", side_effect=e):
                fetched = self.harness.charm._fetch_parca_bin()
                self.assertFalse(fetched)
                self.assertFalse(os.path.exists("/usr/bin/parca"))

    @patch("charm.passwd.add_user")
    def test_create_user(self, add_user):
        create = self.harness.charm._create_user()
        add_user.assert_called_with(username="parca", system_user=True)
        self.assertTrue(create)

    def test_write_configs(self):
        paths = [
            "/etc/systemd/system/parca.service",
            "/etc/systemd/system/juju-introspect.service",
            "/etc/parca/parca.yaml",
        ]

        for f in paths:
            self.assertFalse(Path(f).exists())

        self.fs.add_real_directory("src/configs")
        os.makedirs("/etc/systemd/system", exist_ok=True)
        written = self.harness.charm._write_configs()

        self.assertTrue(written)
        for f in paths:
            self.assertTrue(Path(f).exists())

    def test_write_configs_fail(self):
        # Without any setup, this will fail
        written = self.harness.charm._write_configs()
        self.assertFalse(written)

    @patch("charm.check_call")
    def test_open_port_success(self, cc):
        open = self.harness.charm._open_port()
        cc.assert_called_with(["open-port", "7070/TCP"])
        self.assertTrue(open)

    @patch("charm.check_call", side_effect=CalledProcessError(1, "foo"))
    def test_open_port_failure(self, _):
        open = self.harness.charm._open_port()
        self.assertFalse(open)

    @patch("charm.ParcaOperatorCharm._config_changed")
    def test_storage_limit_property(self, _):
        self.assertEqual(self.harness.charm._storage_limit_in_bytes, 536870912)
        self.harness.update_config({"memory-storage-limit": 1024})
        self.assertEqual(self.harness.charm._storage_limit_in_bytes, 1073741824)
