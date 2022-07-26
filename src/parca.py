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
from charms.parca.v0.parca_config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_PROFILE_PATH,
    ParcaConfig,
    parca_command_line,
)
from jinja2 import Template

logger = logging.getLogger(__name__)


class ParcaInstallError(Exception):
    """Raised when there is an error installing Parca."""

    def __init__(self, message):
        super().__init__(message)


class Parca:
    """Class representing Parca on a host system."""

    BIN_PATH = Path("/usr/bin/parca")
    SVC_PATH = Path("/etc/systemd/system/parca.service")
    SVC_NAME = "parca"

    def install(self):
        """Installs Parca and its dependencies on Ubuntu/Debian."""
        self._install_dependencies()
        self._install_parca_bin()

    def start(self):
        """Start and enable Parca using systemd."""
        systemd.service_resume(self.SVC_NAME)

    def stop(self):
        """Stop Parca using systemd."""
        if systemd.service_running(self.SVC_NAME):
            systemd.service_stop(self.SVC_NAME)

    def remove(self):
        """Removes Parca binaries, services and users. Leaves dependencies in tact."""
        self._remove_parca()

    def configure(self, app_config, scrape_configs=[], restart=True):
        """Configure Parca on the host system. Restart Parca by default."""
        # Create a user for the Parca binary to run as
        self._create_user()

        # Make sure that directories are in place and owned correctly if persistent storage
        # is enabled
        if app_config["storage-persist"]:
            # Ensure that the relevant directories and permissions are in place
            u = passwd.user_exists(self.SVC_NAME)
            os.makedirs(DEFAULT_PROFILE_PATH, exist_ok=True)
            os.chown(DEFAULT_PROFILE_PATH, u.pw_uid, u.pw_gid)

        # Create/update the systemd unit file that starts Parca
        self._write_systemd_unit(app_config)
        # Render the config file for parca
        self._write_parca_config(scrape_configs)

        if restart:
            systemd.daemon_reload()
            systemd.service_restart(self.SVC_NAME)

    def _install_dependencies(self):
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
            raise e

    def _install_parca_bin(self):
        """Fetch the Parca release from Github and extract into correct location."""
        logger.debug("installing parca from charm package")
        os.makedirs("/usr/bin", exist_ok=True)
        shutil.copy("./parca", self.BIN_PATH)

    def _write_parca_config(self, scrape_configs):
        """Writes the parca.yaml file to the correct location on disk."""
        os.makedirs("/etc/parca", exist_ok=True)
        parca_config = ParcaConfig(scrape_configs)
        with open(DEFAULT_CONFIG_PATH, "w+") as f:
            f.write(str(parca_config))

    def _write_systemd_unit(self, app_config):
        """Template out the systemd unit file according to the app config."""
        # Generate the Parca command line
        cmd = parca_command_line(app_config, bin_path=self.BIN_PATH)
        # Read the template unit file
        with open("src/configs/parca.service", "r") as t:
            template = Template(t.read())
        # Render the template with the correct context
        rendered = template.render(parca_command=cmd)
        # Write the template out to disk
        with open(self.SVC_PATH, "w+") as t:
            t.write(rendered)

    def _create_user(self):
        """Create a system user for Parca to run as. No-op if user exists."""
        logger.debug("creating parca user")
        passwd.add_user(username=self.SVC_NAME, system_user=True)

    def _remove_parca(self):
        """Remove all the files installed by Parca. Does not cleanup profile data."""
        self.stop()
        files = [self.SVC_PATH, self.BIN_PATH]
        for f in files:
            if Path(f).exists():
                os.remove(f)

        dirs = ["/etc/parca"]
        for d in dirs:
            shutil.rmtree(d)

        passwd.remove_user(self.SVC_NAME)
