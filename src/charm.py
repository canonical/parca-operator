#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Charmed Operator to deploy Parca - a continuous profiling tool."""

import logging
from subprocess import CalledProcessError, check_call

from charms.operator_libs_linux.v1 import snap
from charms.prometheus_k8s.v0.prometheus_scrape import (
    MetricsEndpointConsumer,
    MetricsEndpointProvider,
)
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from parca import Parca

logger = logging.getLogger(__name__)


class ParcaOperatorCharm(CharmBase):
    """Charmed Operator to deploy Parca - a continuous profiling tool."""

    def __init__(self, *args):
        super().__init__(*args)
        self.parca = Parca()

        # Observe common Juju events
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)
        self.framework.observe(self.on.start, self._start)
        self.framework.observe(self.on.config_changed, self._config_changed)
        self.framework.observe(self.on.remove, self._remove)
        self.framework.observe(self.on.update_status, self._update_status)

        # The profiling_consumer handles the relation that allows Parca to scrape other apps in the
        # model that provide a "profiling-endpoint" relation
        self.profiling_consumer = MetricsEndpointConsumer(self, relation_name="profiling-endpoint")
        self.framework.observe(
            self.profiling_consumer.on.targets_changed, self._on_profiling_targets_changed
        )

        # The metrics_endpoint_provider enables Parca to be scraped by Prometheus for metrics
        self.metrics_endpoint_provider = MetricsEndpointProvider(
            self,
            jobs=[{"static_configs": [{"targets": ["*:7070"]}]}],
            relation_name="metrics-endpoint",
        )

        # The self_profiling_endpoint_provider enables Parca to profile itself
        self.self_profiling_endpoint_provider = MetricsEndpointProvider(
            self,
            jobs=[{"static_configs": [{"targets": ["*:7070"]}]}],
            relation_name="self-profiling-endpoint",
        )

    def _install(self, _):
        """Install dependencies for Parca and ensure initial configs are written."""
        self.unit.status = MaintenanceStatus("installing parca")
        try:
            self.parca.install()
            self.unit.set_workload_version(self.parca.version)
        except snap.SnapError as e:
            self.unit.status = BlockedStatus(str(e))

    def _upgrade_charm(self, _):
        """Ensure the snap is refreshed (in channel) if there are new revisions."""
        self.unit.status = MaintenanceStatus("refreshing parca")
        try:
            self.parca.refresh()
        except snap.SnapError as e:
            self.unit.status = BlockedStatus(str(e))

    def _update_status(self, _):
        """Performed on an interval dictated by model config."""
        # Ensure the hold is extended to make sure the snap never auto-refreshes
        # out of our control
        snap.hold_refresh()
        self.unit.set_workload_version(self.parca.version)

    def _start(self, _):
        """Start Parca."""
        self.parca.start()
        self._open_port()
        self.unit.status = ActiveStatus()

    def _config_changed(self, _):
        """Update the configuration files, restart parca."""
        self.unit.status = MaintenanceStatus("reconfiguring parca")
        scrape_config = self.profiling_consumer.jobs()
        self.parca.configure(self.config, scrape_config)
        self.unit.status = ActiveStatus()

    def _remove(self, _):
        """Remove Parca from the machine."""
        self.unit.status = MaintenanceStatus("removing parca")
        self.parca.remove()

    def _on_profiling_targets_changed(self, _):
        """Update the Parca scrape configuration according to present relations."""
        self.unit.status = MaintenanceStatus("reconfiguring parca")
        self.parca.configure(self.config, self.profiling_consumer.jobs())
        self.unit.status = ActiveStatus()

    def _open_port(self) -> bool:
        """Ensure that Juju opens the correct TCP port for the Parca Dashboard."""
        try:
            check_call(["open-port", "7070/TCP"])
            return True
        except CalledProcessError as e:
            logger.error("error opening port: %s", str(e))
            logger.debug(e, exc_info=True)
            return False


if __name__ == "__main__":  # pragma: nocover
    main(ParcaOperatorCharm)
