#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Charm for Parca - a continuous profiling tool."""

import logging

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.operator_libs_linux.v1 import snap
from charms.parca.v0.parca_scrape import ProfilingEndpointConsumer, ProfilingEndpointProvider
from charms.parca.v0.parca_store import (
    ParcaStoreEndpointProvider,
    ParcaStoreEndpointRequirer,
    RemoveStoreEvent,
)
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

from parca import Parca

logger = logging.getLogger(__name__)


class ParcaOperatorCharm(ops.CharmBase):
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

        # Enable the option to send profiles to a remote store (i.e. Polar Signals Cloud)
        self.store_requirer = ParcaStoreEndpointRequirer(
            self, relation_name="external-parca-store-endpoint"
        )
        self.framework.observe(self.store_requirer.on.endpoints_changed, self._configure_store)
        self.framework.observe(self.store_requirer.on.remove_store, self._configure_store)

        # The profiling_consumer handles the relation that allows Parca to scrape other apps in the
        # model that provide a "profiling-endpoint" relation
        self.profiling_consumer = ProfilingEndpointConsumer(self)
        self.framework.observe(
            self.profiling_consumer.on.targets_changed, self._on_profiling_targets_changed
        )

        # The metrics_endpoint_provider enables Parca to be scraped by Prometheus for metrics
        self.metrics_endpoint_provider = MetricsEndpointProvider(
            self, jobs=[{"static_configs": [{"targets": ["*:7070"]}]}]
        )

        # The self_profiling_endpoint_provider enables Parca to profile itself
        self.self_profiling_endpoint_provider = ProfilingEndpointProvider(
            self,
            jobs=[{"static_configs": [{"targets": ["*:7070"]}]}],
            relation_name="self-profiling-endpoint",
        )

        # Enable Parca Agents to use this Parca instance as a remote store
        self.parca_store_endpoint = ParcaStoreEndpointProvider(
            charm=self, port=7070, insecure=True
        )

        # Allow Parca to provide dashboards to Grafana over a relation
        self._grafana_dashboard_provider = GrafanaDashboardProvider(self)

        # Setup handlers for the S3 relation
        self.s3_client = S3Requirer(self.charm, self.relation_name)
        self.framework.observe(
            self.s3_client.on.credentials_changed, self._on_s3_credential_changed
        )
        self.framework.observe(self.s3_client.on.credentials_gone, self._on_s3_credential_gone)

    def _install(self, _):
        """Install dependencies for Parca and ensure initial configs are written."""
        self.unit.status = ops.MaintenanceStatus("installing parca")
        try:
            self.parca.install()
            self.unit.set_workload_version(self.parca.version)
        except snap.SnapError as e:
            self.unit.status = ops.BlockedStatus(str(e))

    def _upgrade_charm(self, _):
        """Ensure the snap is refreshed (in channel) if there are new revisions."""
        self.unit.status = ops.MaintenanceStatus("refreshing parca")
        try:
            self.parca.refresh()
        except snap.SnapError as e:
            self.unit.status = ops.BlockedStatus(str(e))

    def _update_status(self, _):
        """Handle the update status hook (on an interval dictated by model config)."""
        # Ensure the hold is extended to make sure the snap never auto-refreshes
        # out of our control
        snap.hold_refresh()
        self.unit.set_workload_version(self.parca.version)

    def _start(self, _):
        """Start Parca."""
        self.parca.start()
        self.unit.open_port("tcp", 7070)
        self.unit.status = ops.ActiveStatus()

    def _config_changed(self, _):
        """Update the configuration files, restart parca."""
        self.unit.status = ops.MaintenanceStatus("reconfiguring parca")
        scrape_config = self.profiling_consumer.jobs()
        self.parca.configure(app_config=self.config, scrape_config=scrape_config)
        self.unit.status = ops.ActiveStatus()

    def _configure_store(self, event):
        """Configure store with credentials passed over parca-external-store-endpoint relation."""
        self.unit.status = ops.MaintenanceStatus("reconfiguring parca")
        store_config = {} if isinstance(event, RemoveStoreEvent) else event.store_config
        self.parca.configure(store_config=store_config)
        self.unit.status = ops.ActiveStatus()

    def _on_profiling_targets_changed(self, _):
        """Update the Parca scrape configuration according to present relations."""
        self.unit.status = ops.MaintenanceStatus("reconfiguring parca")
        self.parca.configure(app_config=self.config, scrape_config=self.profiling_consumer.jobs())
        self.unit.status = ops.ActiveStatus()

    def _on_s3_credential_changed(self, event: CredentialsChangedEvent):
        """Update the Parca storage configuration to use S3 credentials when possible."""
        self.parca.configure(s3_creds=self.s3_client.get_s3_connection_info())

    def _on_s3_credential_gone(self, event: CredentialsChangedEvent):
        """Remove S credentials from Parca config when relation is broken."""
        self.parca.configure(s3_creds={})

    def _remove(self, _):
        """Remove Parca from the machine."""
        self.unit.status = ops.MaintenanceStatus("removing parca")
        self.parca.remove()


if __name__ == "__main__":  # pragma: nocover
    ops.main(ParcaOperatorCharm)
