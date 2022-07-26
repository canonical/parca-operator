# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest

import yaml

from parca import ParcaConfig


class TestCharm(unittest.TestCase):
    def setUp(self):
        pass

    def test_parca_config_no_scrape_config_to_dict(self):
        parca_config = ParcaConfig("/tmp", [])
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [],
        }
        self.assertEqual(parca_config.to_dict(), expected)

    def test_parca_config_no_scrape_config_to_str(self):
        parca_config = ParcaConfig("/tmp", [])
        expected = yaml.safe_dump(
            {
                "object_storage": {
                    "bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}
                },
                "scrape_configs": [],
            }
        )
        self.assertEqual(str(parca_config), expected)

    def test_parca_config_with_scrape_config(self):
        parca_config = ParcaConfig("/tmp", [{"metrics_path": "foobar", "foobar": "bazqux"}])
        # The metric_path attribute should be stripped from the scrape configs
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [{"foobar": "bazqux"}],
        }
        self.assertEqual(parca_config.to_dict(), expected)  #

    def test_parca_config_with_scrape_config(self):
        parca_config = ParcaConfig("/tmp", [{"foobar": "bazqux"}])
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [{"foobar": "bazqux"}],
        }
        self.assertEqual(parca_config.to_dict(), expected)
