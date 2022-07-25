# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Representative of a systemd service for juju-instrospect."""

import os
import shutil
from pathlib import Path

from charms.operator_libs_linux.v1 import systemd


class JujuIntrospect:
    """Class representing juju-introspect on a host system."""

    SVC_PATH = Path("/etc/systemd/system/juju-introspect.service")
    SVC_NAME = "juju-introspect"

    def install(self):
        """Install the systemd unit file to start juju-introspect.

        The systemd unit will start juju-introspect listening on 127.0.0.1:6000
        """
        shutil.copy("src/configs/juju-introspect.service", self.SVC_PATH)

    def remove(self):
        """Stop service; Remove the systemd unit file for juju-introspect."""
        self.stop()
        if self.SVC_PATH.exists():
            os.remove(str(self.SVC_PATH))

    def start(self):
        """Start and enable the juju-introspect service."""
        systemd.service_resume(self.SVC_NAME)

    def stop(self):
        """Stop the juju-introspect service."""
        if systemd.service_running(self.SVC_NAME):
            systemd.service_stop(self.SVC_NAME)
