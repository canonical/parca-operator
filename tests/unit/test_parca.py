# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

from charms.operator_libs_linux.v1 import snap

from parca import Parca


class TestParca(unittest.TestCase):
    @patch("parca.check_output")
    @patch("parca.Parca.installed", True)
    def test_parca_version_next(self, checko):
        checko.return_value = (
            b"parca, version v0.12.0-next (commit: e888718c206a5dd63d476849c7349a0352547f1a)\n"
        )
        parca = Parca()
        self.assertEqual(parca.version, "v0.12.0-next+e88871")

    @patch("parca.Parca.installed", False)
    def test_parca_version_not_installed(self):
        try:
            parca = Parca()
            parca.version
        except snap.SnapError as e:
            self.assertEqual(str(e), "parca snap not installed, cannot fetch version")
