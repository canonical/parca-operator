#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

import logging
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
from subprocess import check_call

from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus

logger = logging.getLogger(__name__)

PARCA_VERSION = "0.12.0"
PARCA_URL = f"https://github.com/parca-dev/parca/releases/download/v{PARCA_VERSION}/parca_{PARCA_VERSION}_Linux_x86_64.tar.gz"


class ParcaOperatorCharm(CharmBase):
    """Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.start, self._start)

    def _install(self, _):
        """Install dependencies for Parca and ensure initial configs are written."""
        self.unit.status = MaintenanceStatus("installing parca")
        self._install_dependencies()
        self._fetch_parca_bin()
        self._create_user()
        self._write_configs()
        # Instruct Juju to open the port for Parca
        check_call(["open-port", "7070/TCP"])

    def _start(self, _):
        """Start both the Parca service and the Juju Introspect service."""
        systemd.service_resume("juju-introspect")
        systemd.service_resume("parca")
        self.unit.status = ActiveStatus()

    def _install_dependencies(self):
        """Install apt dependencies for Parca."""
        logger.debug("installing dependencies")
        try:
            apt.update()
            apt.add_package(
                ["llvm", "binutils", "elfutils", f"linux-headers-{platform.uname().release}"]
            )
        except apt.PackageNotFoundError:
            logger.error("a specified package not found in package cache or on system")
        except apt.PackageError as e:
            logger.error("could not install package. Reason: %s", e.message)

    def _fetch_parca_bin(self):
        """Fetch the Parca release from Github and extract into correct location."""
        logger.debug("downloading Parca %s from: %s", PARCA_VERSION, PARCA_URL)
        with urllib.request.urlopen(PARCA_URL) as response:
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                shutil.copyfileobj(response, tmp_file)
                with tarfile.open(tmp_file.name) as tarball:
                    logger.debug("extracting Parca to /usr/bin/parca")
                    tarball.extract("parca", "/usr/bin")

    def _create_user(self):
        """Create a system user for Parca to run as."""
        logger.debug("creating parca user")
        passwd.add_user(username="parca", system_user=True)

    def _write_configs(self):
        """Write systemd units and Parca server config."""
        logger.debug("writing configs and systemd unit files")
        # Install a systemd unit file to start Parca
        shutil.copy("src/configs/parca.service", "/etc/systemd/system/parca.service")
        # Install a systemd unit file to start `juju-introspect`
        shutil.copy(
            "src/configs/juju-introspect.service", "/etc/systemd/system/juju-introspect.service"
        )
        # Install the actual Parca config
        os.makedirs("/etc/parca", exist_ok=True)
        shutil.copy("src/configs/parca.yaml", "/etc/parca/parca.yaml")


if __name__ == "__main__":
    main(ParcaOperatorCharm)
