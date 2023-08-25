# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest

import yaml
from charms.parca.v0.parca_config import ParcaConfig, parca_command_line, parse_version


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

    def test_parca_config_with_scrape_config(self):
        parca_config = ParcaConfig([{"foobar": "bazqux"}], profile_path="/tmp")
        expected = {
            "object_storage": {"bucket": {"type": "FILESYSTEM", "config": {"directory": "/tmp"}}},
            "scrape_configs": [{"foobar": "bazqux"}],
        }
        self.assertEqual(parca_config.to_dict(), expected)

    def test_parca_command_line_default(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=1073741824",
        )

    def test_parca_command_line_custom_bin_path(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config, bin_path="/usr/bin/parca")
        self.assertEqual(
            cmd,
            "/usr/bin/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=1073741824",
        )

    def test_parca_command_line_custom_config_path(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config, config_path="/tmp/config.yaml")
        self.assertEqual(
            cmd,
            "/parca --config-path=/tmp/config.yaml --storage-active-memory=1073741824",
        )

    def test_parca_command_line_memory_limit(self):
        config = {"enable-persistence": False, "memory-storage-limit": 2048}
        cmd = parca_command_line(config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=2147483648",
        )

    def test_parca_command_line_storage_persist(self):
        config = {"enable-persistence": True, "memory-storage-limit": 2048}
        cmd = parca_command_line(app_config=config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --enable-persistence --storage-path=/var/lib/parca",
        )

    def test_parca_command_line_storage_persist_custom_profile_path(self):
        config = {"enable-persistence": True, "memory-storage-limit": 2048}
        cmd = parca_command_line(app_config=config, profile_path="/tmp")
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --enable-persistence --storage-path=/tmp",
        )

    def test_parca_command_line_default_no_store_config(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(app_config=config, store_config={})
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=1073741824",
        )

    def test_parca_command_line_store_config_is_none(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        cmd = parca_command_line(config, store_config=None)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=1073741824",
        )

    def test_parca_command_line_store_config(self):
        config = {"enable-persistence": False, "memory-storage-limit": 1024}
        store_config = {
            "remote-store-address": "grpc.polarsignals.com:443",
            "remote-store-bearer-token": "deadbeef",
            "remote-store-insecure": "false",
        }
        cmd = parca_command_line(config, store_config=store_config)
        self.assertEqual(
            cmd,
            "/parca --config-path=/etc/parca/parca.yaml --storage-active-memory=1073741824 --store-address=grpc.polarsignals.com:443 --bearer-token=deadbeef --insecure=false --mode=scraper-only",
        )

    def test_parse_version_next(self):
        input = "parca, version v0.12.0-next (commit: e888718c206a5dd63d476849c7349a0352547f1a)\n"
        self.assertEqual(parse_version(input), "v0.12.0-next+e88871")

    def test_parca_version_tagged(self):
        input = "parca, version v0.13.0 (commit: e888718c206a5dd63d476849c7349a0352547f1a)\n"
        self.assertEqual(parse_version(input), "v0.13.0")
