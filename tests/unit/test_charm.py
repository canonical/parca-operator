# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import unittest
from unittest.mock import call, patch

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

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

    def test_install_success(self):
        # Make all of the helpers pass, run the event handler
        self.harness.charm._install_dependencies = lambda x=None: True
        self.harness.charm._install_parca_bin = lambda x=None: True
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("installing parca"))

    def test_install_fail_installing_deps(self):
        # One by one, make helpers fail, ensure we block
        self.harness.charm._install_dependencies = lambda x=None: False
        self.harness.charm.on.install.emit()
        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("failed installing dependencies")
        )

    def test_install_fail_installing_parca(self):
        self.harness.charm._install_dependencies = lambda x=None: True
        self.harness.charm._install_parca_bin = lambda x=None: False
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, BlockedStatus("failed installing parca"))

    @patch("charm.systemd.service_resume")
    @patch("charm.check_call")
    def test_start(self, check_call, resume):
        self.harness.charm.on.start.emit()
        self.assertListEqual(resume.mock_calls, [call("juju-introspect"), call("parca")])
        check_call.assert_called_with(["open-port", "7070/TCP"])
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.systemd.service_restart")
    @patch("charm.systemd.daemon_reload")
    @patch("charm.ParcaOperatorCharm._configure_parca")
    def test_config_changed(self, configure, reload, restart):
        config = {
            "storage-persist": False,
            "memory-storage-limit": 1024,
            "juju-scrape-interval": 5,
        }
        self.harness.update_config(config)
        reload.assert_called_once()
        restart.assert_called_with("parca")
        configure.assert_called_with(config)

    def test_remove(self):
        self.harness.charm._cleanup = lambda x=None: True
        self.harness.charm.on.remove.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("removing parca"))
