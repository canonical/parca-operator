# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import unittest
from subprocess import CalledProcessError
from unittest.mock import patch

import ops.testing
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import ParcaOperatorCharm

ops.testing.SIMULATE_CAN_CONNECT = True


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("charm.Parca.install", lambda _: True)
    def test_install_success(self):
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("installing parca"))

    @patch("parca.Parca.install")
    def test_install_fail_installing_deps(self, install):
        install.side_effect = snap.SnapError("failed installing parca")
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, BlockedStatus("failed installing parca"))

    @patch("charm.ParcaOperatorCharm._open_port")
    @patch("charm.Parca.start")
    def test_start(self, parca_start, open_port):
        self.harness.charm.on.start.emit()
        parca_start.assert_called_once()
        open_port.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.Parca.configure")
    def test_config_changed(self, configure):
        config = {
            "storage-persist": False,
            "memory-storage-limit": 1024,
        }
        self.harness.update_config(config)
        configure.assert_called_with(config, [])
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.Parca.remove")
    def test_remove(self, parca_stop):
        self.harness.charm.on.remove.emit()
        parca_stop.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("removing parca"))

    @patch("charm.check_call")
    def test_open_port(self, check_call):
        result = self.harness.charm._open_port()
        check_call.assert_called_with(["open-port", "7070/TCP"])
        self.assertTrue(result)

    @patch("charm.check_call")
    def test_open_port_fail(self, check_call):
        check_call.side_effect = CalledProcessError(1, "foo")
        result = self.harness.charm._open_port()
        check_call.assert_called_with(["open-port", "7070/TCP"])
        self.assertFalse(result)
