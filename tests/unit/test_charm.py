# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import json
import unittest
from unittest.mock import PropertyMock, patch
from uuid import uuid4

import ops.testing
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import ParcaOperatorCharm

ops.testing.SIMULATE_CAN_CONNECT = True

_uuid = uuid4()

SCRAPE_METADATA = {
    "model": "test-model",
    "model_uuid": str(_uuid),
    "application": "profiled-app",
    "charm_name": "test-charm",
}
SCRAPE_JOBS = [
    {
        "global": {"scrape_interval": "1h"},
        "job_name": "my-first-job",
        "static_configs": [{"targets": ["*:7000"], "labels": {"some-key": "some-value"}}],
    },
]


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.add_network("10.10.10.10")
        self.harness.begin()
        self.maxDiff = None

    @patch("charm.Parca.install", lambda _: True)
    @patch("charm.Parca.version", "v0.12.0")
    def test_install_success(self):
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("installing parca"))

    @patch("parca.Parca.install")
    def test_install_fail_(self, install):
        install.side_effect = snap.SnapError("failed installing parca")
        self.harness.charm.on.install.emit()
        self.assertEqual(self.harness.charm.unit.status, BlockedStatus("failed installing parca"))

    @patch("charm.Parca.refresh", lambda _: True)
    def test_upgrade_charm(self):
        self.harness.charm.on.upgrade_charm.emit()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("refreshing parca"))

    @patch("parca.Parca.refresh")
    def test_upgrade_fail_(self, refresh):
        refresh.side_effect = snap.SnapError("failed refreshing parca")
        self.harness.charm.on.upgrade_charm.emit()
        self.assertEqual(self.harness.charm.unit.status, BlockedStatus("failed refreshing parca"))

    @patch("charm.snap.hold_refresh")
    @patch("parca.Parca.version", new_callable=PropertyMock(return_value="v0.12.0"))
    def test_update_status(self, _, hold):
        self.harness.charm.on.update_status.emit()
        hold.assert_called_once()
        self.assertEqual(self.harness.get_workload_version(), "v0.12.0")

    @patch("charm.Parca.start")
    def test_start(self, parca_start):
        self.harness.charm.on.start.emit()
        parca_start.assert_called_once()
        self.assertEqual(
            self.harness.charm.unit.opened_ports(), {ops.OpenedPort(protocol="tcp", port=7070)}
        )
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.Parca.configure")
    def test_config_changed(self, configure):
        config = {
            "enable-persistence": False,
            "memory-storage-limit": 1024,
        }
        self.harness.update_config(config)
        configure.assert_called_with(app_config=config, scrape_config=[])
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.Parca.remove")
    def test_remove(self, parca_stop):
        self.harness.charm.on.remove.emit()
        parca_stop.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("removing parca"))

    @patch("charm.Parca.configure")
    def test_profiling_endpoint_relation(self, _):
        # Create a relation to an app named "profiled-app"
        self.harness.add_relation(
            "profiling-endpoint",
            "profiled-app",
            app_data={
                "scrape_metadata": json.dumps(SCRAPE_METADATA),
                "scrape_jobs": json.dumps(SCRAPE_JOBS),
            },
            unit_data={
                "parca_scrape_unit_address": "1.1.1.1",
                "parca_scrape_unit_name": "profiled-app/0",
            },
        )

        # Taking into account the data provided by the simulated app, we should receive the
        # following jobs config from the profiling_consumer
        expected = [
            {
                "static_configs": [
                    {
                        "labels": {
                            "some-key": "some-value",
                            "juju_model": "test-model",
                            "juju_model_uuid": str(_uuid),
                            "juju_application": "profiled-app",
                            "juju_charm": "test-charm",
                            "juju_unit": "profiled-app/0",
                        },
                        "targets": ["1.1.1.1:7000"],
                    }
                ],
                "job_name": f"test-model_{str(_uuid).split('-')[0]}_profiled-app_my-first-job",
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
    def test_metrics_endpoint_relation(self, _):
        # Create a relation to an app named "prometheus"
        rel_id = self.harness.add_relation("metrics-endpoint", "prometheus", unit_data={})
        # Ugly re-init workaround: manually call `set_scrape_job_spec`
        # https://github.com/canonical/operator/issues/736
        self.harness.charm.metrics_endpoint_provider.set_scrape_job_spec()
        # Grab the unit data from the relation
        unit_data = self.harness.get_relation_data(rel_id, self.harness.charm.unit.name)
        # Ensure that the unit set its targets correctly
        expected = {
            "prometheus_scrape_unit_address": "10.10.10.10",
            "prometheus_scrape_unit_name": "parca/0",
        }
        self.assertEqual(unit_data, expected)

    def test_parca_store_relation(self):
        self.harness.set_leader(True)
        # Create a relation to an app named "parca-agent"
        rel_id = self.harness.add_relation("parca-store-endpoint", "parca-agent", unit_data={})
        # Grab the unit data from the relation
        unit_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)
        # Ensure that the unit set its targets correctly
        expected = {
            "remote-store-address": "10.10.10.10:7070",
            "remote-store-insecure": "true",
        }
        self.assertEqual(unit_data, expected)

    @patch("charm.Parca.configure")
    def test_parca_external_store_relation(self, configure):
        self.harness.set_leader(True)
        # Set some data from the remote application
        store_config = {
            "remote-store-address": "grpc.polarsignals.com:443",
            "remote-store-bearer-token": "deadbeef",
            "remote-store-insecure": "false",
        }
        # Create a relation to an app named "polar-signals-cloud"
        rel_id = self.harness.add_relation(
            "external-parca-store-endpoint", "polar-signals-cloud", app_data=store_config
        )
        # Ensure that we call the configure method on Parca with the correct store details
        configure.assert_called_with(store_config=store_config)
        configure.reset()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

        self.harness.remove_relation(rel_id)
        configure.assert_called_with(store_config={})
