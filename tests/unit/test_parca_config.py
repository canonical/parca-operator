# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest

import yaml
from charms.parca.v0.parca_config import ParcaConfig, parca_command_line


class TestCharm(unittest.TestCase):
    def test_parca_config_no_scrape_config_to_dict(self):
        parca_config = ParcaConfig([], profile_path="/tmp")
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [],
        }
        self.assertEqual(parca_config.to_dict(), expected)

    def test_parca_config_no_scrape_config_to_str(self):
        parca_config = ParcaConfig([], profile_path="/tmp")
        expected = yaml.safe_dump(
            {
                "object_storage": {
                    "bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}
                },
                "scrape_configs": [],
            }
        )
        self.assertEqual(str(parca_config), expected)

    def test_parca_config_with_scrape_config_strip_metrics_path(self):
        parca_config = ParcaConfig(
            [{"metrics_path": "foobar", "foobar": "bazqux"}], profile_path="/tmp"
        )
        # The metric_path attribute should be stripped from the scrape configs
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [{"foobar": "bazqux"}],
        }
        self.assertEqual(parca_config.to_dict(), expected)  #

    def test_parca_config_with_scrape_config(self):
        parca_config = ParcaConfig([{"foobar": "bazqux"}], profile_path="/tmp")
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [{"foobar": "bazqux"}],
        }
        self.assertEqual(parca_config.to_dict(), expected)

    def test_parca_command_line_default(self):
        config = {"storage-persist": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-in-memory=true --storage-active-memory=1073741824",
        )

    def test_parca_command_line_custom_bin_path(self):
        config = {"storage-persist": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config, bin_path="/usr/bin/parca")
        self.assertEqual(
            cmd,
            "/usr/bin/parca --config-path=/etc/parca/parca.yaml --storage-in-memory=true --storage-active-memory=1073741824",
        )

    def test_parca_command_line_custom_config_path(self):
        config = {"storage-persist": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config, config_path="/tmp/config.yaml")
        self.assertEqual(
            cmd,
            "/parca --config-path=/tmp/config.yaml --storage-in-memory=true --storage-active-memory=1073741824",
        )

    def test_parca_command_line_memory_limit(self):
        config = {"storage-persist": False, "memory-storage-limit": 2048}
        cmd = parca_command_line(config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-in-memory=true --storage-active-memory=2147483648",
        )

    def test_parca_command_line_storage_persist(self):
        config = {"storage-persist": True, "memory-storage-limit": 2048}
        cmd = parca_command_line(config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-in-memory=false --storage-persist --storage-path=/var/lib/parca",
        )

    def test_parca_command_line_storage_persist_custom_profile_path(self):
        config = {"storage-persist": True, "memory-storage-limit": 2048}
        cmd = parca_command_line(config, profile_path="/tmp")
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-in-memory=false --storage-persist --storage-path=/tmp",
        )
