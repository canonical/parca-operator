#!/usr/bin/env python3
# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

import logging
import os
import shutil
from pathlib import Path
from platform import uname
from subprocess import CalledProcessError, check_call

from charms.operator_libs_linux.v0 import apt, passwd
from charms.operator_libs_linux.v1 import systemd
from jinja2 import Template
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

# TODO(jnsgruk): Re-enable when we're fetching Parca from the web
# import tarfile
# import tempfile
# import urllib.request
# from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

PARCA_VERSION = "0.12.0"
PARCA_URL = f"https://github.com/parca-dev/parca/releases/download/v{PARCA_VERSION}/parca_{PARCA_VERSION}_Linux_x86_64.tar.gz"


class ParcaOperatorCharm(CharmBase):
    """Simple, hacky charm to deploy Parca for monitoring a Juju controller."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.start, self._start)
        self.framework.observe(self.on.config_changed, self._config_changed)
        self.framework.observe(self.on.remove, self._remove)

    def _install(self, _):
        """Install dependencies for Parca and ensure initial configs are written."""
        self.unit.status = MaintenanceStatus("installing parca")
        if not self._install_dependencies():
            self.unit.status = BlockedStatus("failed installing dependencies")
            return

        if not self._install_parca_bin():
            self.unit.status = BlockedStatus("failed installing parca")
            return

    def _start(self, _):
        """Start both the Parca service and the Juju Introspect service."""
        self._open_port()
        systemd.service_resume("juju-introspect")
        systemd.service_resume("parca")
        self.unit.status = ActiveStatus()

    def _config_changed(self, _):
        """Update the configuration files, restart parca."""
        self._configure_parca(self.config)
        systemd.daemon_reload()
        systemd.service_restart("parca")

    def _remove(self, _):
        self.unit.status = MaintenanceStatus("removing parca")
        self._cleanup()

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

        # Install a systemd unit file to start `juju-introspect`
        shutil.copy(
            "src/configs/juju-introspect.service", "/etc/systemd/system/juju-introspect.service"
        )
        return True

    def _install_parca_bin(self) -> bool:
        """Fetch the Parca release from Github and extract into correct location."""
        # logger.debug("downloading Parca %s from: %s", PARCA_VERSION, PARCA_URL)
        # try:
        #     # Download the tarball
        #     response = urllib.request.urlopen(PARCA_URL)
        # except (URLError, HTTPError) as e:
        #     logger.error(str(e))
        #     return False

        # # Write the fetched file to a temporary file
        # tmp_file = tempfile.NamedTemporaryFile()
        # with open(tmp_file.name, "wb") as f:
        #     shutil.copyfileobj(response, f)

        # try:
        #     # Extract the fetched tarball to /usr/bin
        #     with tarfile.open(tmp_file.name) as tarball:
        #         tarball.extract("parca", "/usr/bin")
        # except (tarfile.ExtractError, tarfile.ReadError) as e:
        #     logger.error(str(e))
        #     return False
        # return True
        logger.debug("installing parca from charm package")
        shutil.copy("./parca", "/usr/bin/parca")
        return True

    def _create_user(self) -> bool:
        """Create a system user for Parca to run as."""
        logger.debug("creating parca user")
        passwd.add_user(username="parca", system_user=True)
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
            storage_config.append("--storage-path=/var/lib/parca")
            # Ensure that the relevant directories and permissions are in place
            u = passwd.user_exists("parca")
            os.makedirs("/var/lib/parca", exist_ok=True)
            os.chown("/var/lib/parca", u.pw_uid, u.pw_gid)
        else:
            limit = config["memory-storage-limit"] * 1048576
            storage_config.append("--storage-in-memory=true")
            storage_config.append(f"--storage-active-memory={limit}")

        try:
            # Render the systemd service for parca
            self._render_template(
                "src/configs/parca.service",
                "/etc/systemd/system/parca.service",
                {"storage_config": " ".join(storage_config)},
            )
            # Render the config file for parca
            os.makedirs("/etc/parca", exist_ok=True)
            self._render_template(
                "src/configs/parca.yaml",
                "/etc/parca/parca.yaml",
                {"interval": config["juju-scrape-interval"]},
            )
            return True
        except Exception as e:
            logger.error("error writing config files: %s", str(e))
            logger.debug(e, exc_info=True)
            return False

    def _render_template(self, template_filename, target_file, context):
        """Render a give template file to target, with a given context."""
        # Open the template from the source file
        with open(template_filename, "r") as t:
            template = Template(t.read())
        # Render the template with the correct context
        rendered = template.render(**context)
        # Write the template out to disk
        with open(target_file, "w+") as t:
            t.write(rendered)

    def _open_port(self) -> bool:
        """Ensure that Juju opens the correct TCP port for the Parca Dashboard."""
        try:
            check_call(["open-port", "7070/TCP"])
            return True
        except CalledProcessError as e:
            logger.error("error opening port: %s", str(e))
            logger.debug(e, exc_info=True)
            return False

    def _cleanup(self) -> bool:
        """Remove all the files installed by Parca, do not cleanup data from /var/lib/parca."""
        systemd.service_stop("parca")
        systemd.service_stop("juju-introspect")
        files = [
            "/etc/systemd/system/parca.service",
            "/etc/systemd/system/juju-introspect.service",
            "/usr/bin/parca",
        ]
        for f in files:
            if Path(f).exists():
                os.remove(f)

        dirs = ["/etc/parca"]
        for d in dirs:
            shutil.rmtree(d)

        passwd.remove_user("parca")
        return True


if __name__ == "__main__":  # pragma: nocover
    main(ParcaOperatorCharm)
