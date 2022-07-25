# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import logging
import unittest
from pathlib import Path

from charms.operator_libs_linux.v1 import systemd

from jujuintrospect import JujuIntrospect
from tests.helpers import install_fake_daemon

logger = logging.getLogger(__name__)


class TestJujuIntrospect(unittest.TestCase):
    def setUp(self):
        self.juju_introspect = JujuIntrospect()
        install_fake_daemon("/usr/bin/juju-introspect")

    def test_install(self):
        self.juju_introspect.install()

        tmpl = "src/configs/juju-introspect.service"
        file = "/etc/systemd/system/juju-introspect.service"
        with open(tmpl) as f1, open(file) as f2:
            self.assertEqual(f1.read(), f2.read())

        self.juju_introspect.remove()

    def test_start(self):
        self.juju_introspect.install()
        self.juju_introspect.start()
        self.assertTrue(systemd.service_running("juju-introspect"))
        self.juju_introspect.remove()

    def test_stop(self):
        self.juju_introspect.install()
        self.juju_introspect.start()
        self.juju_introspect.stop()
        self.assertFalse(systemd.service_running("juju-introspect"))
        self.juju_introspect.remove()

    def test_remove(self):
        self.juju_introspect.install()
        self.juju_introspect.start()
        self.juju_introspect.remove()
        self.assertFalse(Path("/etc/systemd/system/juju-introspect.service").exists())
        self.assertFalse(systemd.service_running("juju-introspect"))
