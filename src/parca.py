# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Represents Parca on a host system. Provides a Parca class."""

import logging
from subprocess import check_output

from charms.operator_libs_linux.v1 import snap
from charms.parca.v0.parca_config import ParcaConfig, parse_version

logger = logging.getLogger(__name__)


class Parca:
    """Class representing Parca on a host system."""

    CONFIG_PATH = "/var/snap/parca/current/parca.yaml"

    def install(self):
        """Installs the Parca snap package."""
        try:
            self._snap.ensure(snap.SnapState.Latest, channel="edge")
            snap.hold_refresh()
        except snap.SnapError as e:
            logger.error("could not install parca. Reason: %s", e.message)
            logger.debug(e, exc_info=True)
            raise e

    def refresh(self):
        """Refreshes the Parca snap if there is a new revision."""
        # The operation here is exactly the same, so just call the install method
        self.install()

    def start(self):
        """Start and enable Parca using the snap service."""
        self._snap.start(enable=True)

    def stop(self):
        """Stop Parca using the snap service."""
        self._snap.stop(disable=True)

    def remove(self):
        """Removes the Parca snap, preserving config and data."""
        self._snap.ensure(snap.SnapState.Absent)

    def configure(self, app_config, scrape_configs=[], restart=True):
        """Configure Parca on the host system. Restart Parca by default."""
        # Configure the snap appropriately
        if app_config["storage-persist"]:
            self._snap.set({"storage-persist": "true"})
        else:
            limit = app_config["memory-storage-limit"] * 1048576
            self._snap.set({"storage-persist": "false", "storage-active-memory": limit})

        # Write the config file
        parca_config = ParcaConfig(scrape_configs)
        with open(self.CONFIG_PATH, "w+") as f:
            f.write(str(parca_config))

        # Restart the snap service
        if restart:
            self._snap.restart()

    @property
    def installed(self):
        """Reports if the Parca snap is installed."""
        return self._snap.present

    @property
    def running(self):
        """Reports if the 'parca-svc' snap service is running."""
        return self._snap.services["parca-svc"]["active"]

    @property
    def version(self) -> str:
        """Reports the version of Parca currently installed."""
        if self.installed:
            results = check_output(["parca", "--version"]).decode()
            return parse_version(results)
        raise snap.SnapError("parca snap not installed, cannot fetch version")

    @property
    def _snap(self):
        """Returns a representation of the Parca snap."""
        cache = snap.SnapCache()
        return cache["parca"]
