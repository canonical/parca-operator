# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

from pyfakefs.fake_filesystem_unittest import TestCase

from helpers import render_template


class TestHelpers(TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_render_template(self):
        with open("/tmp/test.j2", "w+") as f:
            f.write("Hello {{ name }}")

        render_template("/tmp/test.j2", "/tmp/test", {"name": "Joe Bloggs"})

        with open("/tmp/test", "r") as f:
            self.assertEqual(f.read(), "Hello Joe Bloggs")
