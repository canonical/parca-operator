# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest

from ops.testing import Harness

from charm import ParcaOperatorCharm


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_foobar(self):
        self.assertTrue(True)
