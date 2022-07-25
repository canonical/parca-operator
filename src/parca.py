# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Represents Parca on a host system. Provides a Parca class."""

import logging
import os
import shutil
from pathlib import Path
from platform import uname

from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd

from helpers import render_template

logger = logging.getLogger(__name__)


class ParcaInstallError(Exception):
    """Raised when there is an error installing Parca."""

    def __init__(self, message):
        super().__init__(message)


class Parca:
    """Class representing Parca on a host system."""

    BIN_PATH = Path("/usr/bin/parca")
    CONFIG_PATH = Path("/etc/parca/parca.yaml")
    SVC_PATH = Path("/etc/systemd/system/parca.service")
    PROFILE_PATH = Path("/var/lib/parca")
    SVC_NAME = "parca"

    def install(self) -> bool:
        """Installs Parca and its dependencies on Ubuntu/Debian."""
        if not self._install_dependencies():
            raise ParcaInstallError("failed installing parca dependencies")

        if not self._install_parca_bin():
            raise ParcaInstallError("failed installing parca")

        return True

    def start(self):
        """Start and enable Parca using systemd."""
        systemd.service_resume(self.SVC_NAME)

    def stop(self):
        """Stop Parca using systemd."""
        if systemd.service_running(self.SVC_NAME):
            systemd.service_stop(self.SVC_NAME)

    def remove(self) -> bool:
        """Removes Parca binaries, services and users. Leaves dependencies in tact."""
        self._remove_parca()

    def configure(self, config, restart=True):
        """Configure Parca on the host system. Restart Parca by default."""
        self._configure_parca(config)

        if restart:
            systemd.daemon_reload()
            systemd.service_restart(self.SVC_NAME)

    def _install_dependencies(self) -> bool:
        """Install apt dependencies for Parca."""
        logger.debug("installing dependencies")
        # Grab the kernel version so we can install the correct headers
        kernel_version = uname().release
        dependencies = ["llvm", "binutils", "elfutils", f"linux-headers-{kernel_version}"]
        try:
            apt.update()
            apt.add_package(dependencies)
        except (apt.PackageNotFoundError, apt.PackageError) as e:
            logger.error("could not install package. Reason: %s", e.message)
            logger.debug(e, exc_info=True)
            return False

        return True

    def _install_parca_bin(self) -> bool:
        """Fetch the Parca release from Github and extract into correct location."""
        logger.debug("installing parca from charm package")
        os.makedirs("/usr/bin", exist_ok=True)
        shutil.copy("./parca", self.BIN_PATH)
        return True

    def _configure_parca(self, config) -> bool:
        """Write systemd units and Parca server config."""
        logger.debug("writing configs and systemd unit files")

        # Create a user for the Parca binary to run as
        self._create_user()

        storage_config = []
        # Render the template files with the correct values
        if config["storage-persist"]:
            # Add the correct command line options for disk persistence
            storage_config.append("--storage-in-memory=false")
            storage_config.append("--storage-persist")
            storage_config.append(f"--storage-path={self.PROFILE_PATH}")
            # Ensure that the relevant directories and permissions are in place
            u = passwd.user_exists(self.SVC_NAME)
            os.makedirs(self.PROFILE_PATH, exist_ok=True)
            os.chown(self.PROFILE_PATH, u.pw_uid, u.pw_gid)
        else:
            limit = config["memory-storage-limit"] * 1048576
            storage_config.append("--storage-in-memory=true")
            storage_config.append(f"--storage-active-memory={limit}")

        try:
            # Render the systemd service for parca
            render_template(
                "src/configs/parca.service",
                self.SVC_PATH,
                {"storage_config": " ".join(storage_config)},
            )
            # Render the config file for parca
            os.makedirs("/etc/parca", exist_ok=True)
            render_template(
                "src/configs/parca.yaml",
                self.CONFIG_PATH,
                {"interval": config["juju-scrape-interval"]},
            )
            return True
        except Exception as e:
            logger.error("error writing config files: %s", str(e))
            logger.debug(e, exc_info=True)
            return False

    def _create_user(self) -> bool:
        """Create a system user for Parca to run as. No-op if user exists."""
        logger.debug("creating parca user")
        passwd.add_user(username=self.SVC_NAME, system_user=True)
        return True

    def _remove_parca(self) -> bool:
        """Remove all the files installed by Parca, do not cleanup data from /var/lib/parca."""
        self.stop()
        files = [self.SVC_PATH, self.BIN_PATH]
        for f in files:
            if Path(f).exists():
                os.remove(f)

        dirs = ["/etc/parca"]
        for d in dirs:
            shutil.rmtree(d)

        passwd.remove_user(self.SVC_NAME)
        return True
