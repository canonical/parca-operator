# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import json
import unittest
from subprocess import CalledProcessError
from unittest.mock import patch

import ops.testing
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import ParcaOperatorCharm

ops.testing.SIMULATE_CAN_CONNECT = True

SCRAPE_METADATA = {
    "model": "test-model",
    "model_uuid": "abcdef",
    "application": "profiled-app",
    "charm_name": "test-charm",
}
SCRAPE_JOBS = [
    {
        "global": {"scrape_interval": "1h"},
        "rule_files": ["/some/file"],
        "file_sd_configs": [{"files": "*some-files*"}],
        "job_name": "my-first-job",
        "metrics_path": "/one-path",
        "static_configs": [{"targets": ["*:7000"], "labels": {"some-key": "some-value"}}],
    },
]


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

    @patch("charm.Parca.configure")
    def test_profiling_endpoint_relation(self, _):
        # Create a relation to an app named "profiled-app"
        rel_id = self.harness.add_relation("profiling-endpoint", "profiled-app")
        # Simulate that "profiled-app" has provided the data we're expecting
        self.harness.update_relation_data(
            rel_id,
            "profiled-app",
            {
                "scrape_metadata": json.dumps(SCRAPE_METADATA),
                "scrape_jobs": json.dumps(SCRAPE_JOBS),
            },
        )
        # Add a unit to the relation
        self.harness.add_relation_unit(rel_id, "profiled-app/0")
        # Simulate the remote unit adding its details for scraping
        self.harness.update_relation_data(
            rel_id,
            "profiled-app/0",
            {
                "prometheus_scrape_unit_address": "1.1.1.1",
                "prometheus_scrape_unit_name": "profiled-app/0",
            },
        )
        # Taking into account the data provided by the simulated app, we should receive the
        # following jobs config from the profiling_consumer
        expected = [
            {
                "metrics_path": "/one-path",
                "static_configs": [
                    {
                        "labels": {
                            "some-key": "some-value",
                            "juju_model": "test-model",
                            "juju_model_uuid": "abcdef",
                            "juju_application": "profiled-app",
                            "juju_charm": "test-charm",
                            "juju_unit": "profiled-app/0",
                        },
                        "targets": ["1.1.1.1:7000"],
                    }
                ],
                "job_name": "juju_test-model_abcdef_profiled-app_test-charm_prometheus_scrape_my-first-job",
                "relabel_configs": [
                    {
                        "source_labels": [
                            "juju_model",
                            "juju_model_uuid",
                            "juju_application",
                            "juju_unit",
                        ],
                        "separator": "_",
                        "target_label": "instance",
                        "regex": "(.*)",
                    }
                ],
            }
        ]
        self.assertEqual(self.harness.charm.profiling_consumer.jobs(), expected)

    @patch("charm.Parca.configure")
    @patch("socket.getfqdn", new=lambda *args: "some.host")
    def test_metrics_endpoint_relation(self, _):
        # Create a relation to an app named "prometheus"
        rel_id = self.harness.add_relation("metrics-endpoint", "prometheus")
        # Add a prometheus unit
        self.harness.add_relation_unit(rel_id, "prometheus/0")
        # Grab the unit data from the relation
        unit_data = self.harness.get_relation_data(rel_id, self.harness.charm.unit.name)
        # Ensure that the unit set its targets correctly
        expected = {
            "prometheus_scrape_unit_address": "some.host",
            "prometheus_scrape_unit_name": "parca/0",
        }
        self.assertEqual(unit_data, expected)
