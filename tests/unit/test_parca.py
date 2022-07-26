# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

# These unit tests only focus on flow/exception handling. The functionality
# nearly all touches the underlying system, and is tested within the functional
# test suite instead.

import unittest
from unittest.mock import patch

from parca import Parca, ParcaInstallError
from tests.helpers import DEFAULT_PARCA_CONFIG


@patch("parca.Parca._install_dependencies", lambda x: True)
@patch("parca.Parca._create_user", lambda x: True)
@patch("parca.systemd.daemon_reload", lambda x=True: True)
@patch("parca.systemd.service_restart", lambda x=True: True)
class TestParca(unittest.TestCase):
    def setUp(self):
        self.parca = Parca()

    def test_install_failures(self):
        with patch("parca.Parca._install_dependencies", lambda x=True: False):
            try:
                self.parca.install()
            except ParcaInstallError as e:
                self.assertEqual(str(e), "failed installing parca dependencies")
        with patch("parca.Parca._install_parca_bin", lambda x=True: False):
            try:
                self.parca.install()
            except ParcaInstallError as e:
                self.assertEqual(str(e), "failed installing parca")

    def test_configure_fail(self):
        with patch("parca.render_template", side_effect=Exception):
            result = self.parca.configure(DEFAULT_PARCA_CONFIG)
            self.assertFalse(result)
