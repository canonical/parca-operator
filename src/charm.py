#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

import logging
import os
import shutil
import tarfile
import tempfile
import urllib.request
from platform import uname
from subprocess import CalledProcessError, check_call
from urllib.error import HTTPError, URLError

from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

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
        install_stages = [
            self._install_dependencies,
            self._fetch_parca_bin,
            self._create_user,
            self._write_configs,
            self._open_port,
        ]
        for stage in install_stages:
            if not stage():
                self.unit.status = BlockedStatus("failed to install parca, check logs")
                return

    def _start(self, _):
        """Start both the Parca service and the Juju Introspect service."""
        systemd.service_resume("juju-introspect")
        systemd.service_resume("parca")
        self.unit.status = ActiveStatus()

    def _config_changed(self, _):
        pass

    def _install_dependencies(self) -> bool:
        """Install apt dependencies for Parca."""
        logger.debug("installing dependencies")
        # Grab the kernel version so we can install the correct headers
        kernel_version = uname().release
        dependencies = ["llvm", "binutils", "elfutils", f"linux-headers-{kernel_version}"]
        try:
            apt.update()
            apt.add_package(dependencies)
            return True
        except apt.PackageNotFoundError:
            logger.error("a specified package not found in package cache or on system")
            return False
        except apt.PackageError as e:
            logger.error("could not install package. Reason: %s", e.message)
            return False

    def _fetch_parca_bin(self) -> bool:
        """Fetch the Parca release from Github and extract into correct location."""
        logger.debug("downloading Parca %s from: %s", PARCA_VERSION, PARCA_URL)
        try:
            # Download the tarball
            response = urllib.request.urlopen(PARCA_URL)
        except (URLError, HTTPError) as e:
            logger.error(str(e))
            return False

        # Write the fetched file to a temporary file
        tmp_file = tempfile.NamedTemporaryFile()
        with open(tmp_file.name, "wb") as f:
            shutil.copyfileobj(response, f)

        try:
            # Extract the fetched tarball to /usr/bin
            with tarfile.open(tmp_file.name) as tarball:
                tarball.extract("parca", "/usr/bin")
        except (tarfile.ExtractError, tarfile.ReadError) as e:
            logger.error(str(e))
            return False
        return True

    def _create_user(self) -> bool:
        """Create a system user for Parca to run as."""
        logger.debug("creating parca user")
        passwd.add_user(username="parca", system_user=True)
        return True

    def _write_configs(self) -> bool:
        """Write systemd units and Parca server config."""
        logger.debug("writing configs and systemd unit files")
        try:
            # Install a systemd unit file to start Parca
            shutil.copy("src/configs/parca.service", "/etc/systemd/system/parca.service")
            # Install a systemd unit file to start `juju-introspect`
            shutil.copy(
                "src/configs/juju-introspect.service",
                "/etc/systemd/system/juju-introspect.service",
            )
            # Install the actual Parca config
            os.makedirs("/etc/parca", exist_ok=True)
            shutil.copy("src/configs/parca.yaml", "/etc/parca/parca.yaml")
            return True
        except Exception as e:
            logger.error("error writing config files: %s", str(e))
            return False

    def _open_port(self) -> bool:
        # Instruct Juju to open the port for Parca
        try:
            check_call(["open-port", "7070/TCP"])
            return True
        except CalledProcessError as e:
            logger.error("error opening port: %s", str(e))
            return False


if __name__ == "__main__":  # pragma: nocover
    main(ParcaOperatorCharm)
