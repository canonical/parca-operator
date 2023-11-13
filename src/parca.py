# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Control Parca on a host system. Provides a Parca class."""

import logging
from pathlib import Path
from subprocess import check_output

import yaml
from charms.operator_libs_linux.v1 import snap
from charms.parca.v0.parca_config import ParcaConfig, parse_version

logger = logging.getLogger(__name__)


class Parca:
    """Class representing Parca on a host system."""

    CONFIG_PATH = "/var/snap/parca/current/parca.yaml"
    PROFILE_PATH = "/var/snap/parca/current/profiles"

    def install(self):
        """Install the Parca snap package."""
        try:
            self._snap.ensure(snap.SnapState.Latest, channel="edge")
            snap.hold_refresh()
        except snap.SnapError as e:
            logger.error("could not install parca. Reason: %s", e.message)
            logger.debug(e, exc_info=True)
            raise e

    def refresh(self):
        """Refresh the Parca snap if there is a new revision."""
        # The operation here is exactly the same, so just call the install method
        self.install()

    def start(self):
        """Start and enable Parca using the snap service."""
        self._snap.start(enable=True)

    def stop(self):
        """Stop Parca using the snap service."""
        self._snap.stop(disable=True)

    def remove(self):
        """Remove the Parca snap, preserving config and data."""
        self._snap.ensure(snap.SnapState.Absent)

    def configure(self, *, app_config=None, scrape_config=None, store_config=None, s3_creds=None, restart=True):
        """Configure Parca on the host system. Restart Parca by default."""
        if app_config:
            if app_config.get("enable-persistence", None):
                self._snap.set({"enable-persistence": "true"})
            else:
                limit = app_config["memory-storage-limit"] * 1048576
                self._snap.set({"enable-persistence": "false", "storage-active-memory": limit})

        if store_config:
            if addr := store_config.get("remote-store-address", None):
                self._snap.set({"remote-store-address": addr})

            if token := store_config.get("remote-store-bearer-token", None):
                self._snap.set({"remote-store-bearer-token": token})

            if insecure := store_config.get("remote-store-insecure", None):
                self._snap.set({"remote-store-insecure": insecure})

        if scrape_config:
            # If the scrape configs are explicitly set, then build the config from new
            parca_config = ParcaConfig(scrape_config, profile_path=self.PROFILE_PATH, s3_creds)
        else:
            # Otherwise grab existing scrape jobs and build a config to include them
            old = yaml.safe_load(Path(self.CONFIG_PATH).read_text())
            parca_config = ParcaConfig(
                old.get("scrape_configs", []), profile_path=self.PROFILE_PATH, s3_creds
            )

        with open(self.CONFIG_PATH, "w+") as f:
            f.write(str(parca_config))

        # Restart the snap service
        if restart:
            self._snap.restart()

    @property
    def installed(self):
        """Report if the Parca snap is installed."""
        return self._snap.present

    @property
    def running(self):
        """Report if the 'parca-svc' snap service is running."""
        return self._snap.services["parca-svc"]["active"]

    @property
    def version(self) -> str:
        """Report the version of Parca currently installed."""
        if self.installed:
            results = check_output(["parca", "--version"]).decode()
            return parse_version(results)
        raise snap.SnapError("parca snap not installed, cannot fetch version")

    @property
    def _snap(self):
        """Return a representation of the Parca snap."""
        cache = snap.SnapCache()
        return cache["parca"]
