# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import unittest
from pathlib import Path
from subprocess import check_call

from charms.parca.v0.parca_config import ParcaConfig
from parca import Parca

DEFAULT_PARCA_CONFIG = {
    "enable-persistence": False,
    "memory-storage-limit": 1024,
}


def _file_content_equals_string(filename: str, expected: str):
    """Check if the contents of file 'filename' equal the 'expected' param."""
    with open(filename) as f:
        return f.read() == expected


class TestParca(unittest.TestCase):
    def setUp(self):
        self.parca = Parca()
        if not self.parca.installed:
            self.parca.install()

    def test_install(self):
        self.assertTrue(Path("/snap/bin/parca").exists())
        self.assertEqual(check_call(["/snap/bin/parca", "--version"]), 0)

    def test_start(self):
        self.parca.start()
        self.assertTrue(self.parca.running)
        self.parca.remove()

    def test_stop(self):
        self.parca.stop()
        self.assertFalse(self.parca.running)
        self.parca.remove()

    def test_remove(self):
        self.parca.remove()
        self.assertFalse(self.parca.installed)

    def test_configure_systemd_storage_persist(self):
        self.parca.configure(app_config={"enable-persistence": True})
        self.assertEqual(self.parca._snap.get("enable-persistence"), "true")

    def test_configure_systemd_storage_in_memory(self):
        self.parca.configure(app_config=DEFAULT_PARCA_CONFIG)
        self.assertEqual(self.parca._snap.get("enable-persistence"), "false")
        self.assertEqual(self.parca._snap.get("storage-active-memory"), "1073741824")

    def test_configure_parca_no_scrape_jobs(self):
        self.parca.configure(app_config=DEFAULT_PARCA_CONFIG)
        config = ParcaConfig([], profile_path="/var/snap/parca/current/profiles")
        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))

    def test_configure_parca_simple_scrape_jobs(self):
        self.parca.configure(
            app_config=DEFAULT_PARCA_CONFIG,
            scrape_config=[{"metrics_path": "foobar", "bar": "baz"}],
        )
        config = ParcaConfig(
            [{"metrics_path": "foobar", "bar": "baz"}],
            profile_path="/var/snap/parca/current/profiles",
        )
        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))

    def test_configure_parca_store_config(self):
        self.parca.configure(
            store_config={
                "remote-store-address": "grpc.polarsignals.com:443",
                "remote-store-bearer-token": "deadbeef",
                "remote-store-insecure": "false",
            }
        )
        self.assertEqual(self.parca._snap.get("remote-store-address"), "grpc.polarsignals.com:443")
        self.assertEqual(self.parca._snap.get("remote-store-bearer-token"), "deadbeef")
        self.assertEqual(self.parca._snap.get("remote-store-insecure"), "false")

    def test_configure_parca_store_config_no_conflict_with_app_config(self):
        # Setup baseline config
        self.parca.configure(app_config=DEFAULT_PARCA_CONFIG)
        self.assertEqual(self.parca._snap.get("enable-persistence"), "false")
        self.assertEqual(self.parca._snap.get("storage-active-memory"), "1073741824")

        # Setup some store config
        self.parca.configure(
            store_config={
                "remote-store-address": "grpc.polarsignals.com:443",
                "remote-store-bearer-token": "deadbeef",
                "remote-store-insecure": "false",
            }
        )

        self.assertEqual(self.parca._snap.get("remote-store-address"), "grpc.polarsignals.com:443")
        self.assertEqual(self.parca._snap.get("remote-store-bearer-token"), "deadbeef")
        self.assertEqual(self.parca._snap.get("remote-store-insecure"), "false")

        # Check we didn't mess with the app_config
        self.assertEqual(self.parca._snap.get("enable-persistence"), "false")
        self.assertEqual(self.parca._snap.get("storage-active-memory"), "1073741824")

    def test_configure_parca_store_config_no_conflict_with_scrape_config(self):
        self.parca.configure(
            app_config=DEFAULT_PARCA_CONFIG,
            scrape_config=[{"metrics_path": "foobar", "bar": "baz"}],
        )
        config = ParcaConfig(
            [{"metrics_path": "foobar", "bar": "baz"}],
            profile_path="/var/snap/parca/current/profiles",
        )
        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))

        # Setup some store config
        self.parca.configure(
            store_config={
                "remote-store-address": "grpc.polarsignals.com:443",
                "remote-store-bearer-token": "deadbeef",
                "remote-store-insecure": "false",
            }
        )

        self.assertEqual(self.parca._snap.get("remote-store-address"), "grpc.polarsignals.com:443")
        self.assertEqual(self.parca._snap.get("remote-store-bearer-token"), "deadbeef")
        self.assertEqual(self.parca._snap.get("remote-store-insecure"), "false")

        self.assertTrue(_file_content_equals_string(self.parca.CONFIG_PATH, str(config)))
