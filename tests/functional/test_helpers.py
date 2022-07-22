import logging
import unittest
from pathlib import Path
from platform import uname

from charms.operator_libs_linux.v0 import apt, passwd
from jinja2 import Template
from ops.testing import Harness

from charm import ParcaOperatorCharm

logger = logging.getLogger(__name__)


def _file_content_equals_string(filename: str, expected: str):
    with open(filename) as f:
        return f.read() == expected


def _render_template(template, context):
    with open(template) as f:
        template = Template(f.read())
    return template.render(**context)


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_install_dependencies(self):
        self.harness.charm._install_dependencies()
        kernel_version = uname().release
        dependencies = ["llvm", "binutils", "elfutils", f"linux-headers-{kernel_version}"]
        # Loop over dependencies, ensure they are installed
        for d in dependencies:
            package = apt.DebianPackage.from_system(d)
            self.assertTrue(package.present)

        # Check that the juju-introspect service is in place
        tmpl = "src/configs/juju-introspect.service"
        file = "/etc/systemd/system/juju-introspect.service"
        with open(tmpl) as f1, open(file) as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_create_user(self):
        self.harness.charm._create_user()
        self.assertTrue(passwd.user_exists("parca"))

    def test_write_configs_storage_persist(self):
        config = {"storage-persist": True, "juju-scrape-interval": 5}
        self.harness.charm._configure_parca(config)

        storage_config = [
            "--storage-in-memory=false",
            "--storage-persist",
            "--storage-path=/var/lib/parca",
        ]

        # Check the systemd service was rendered correctly
        svc = _render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(_file_content_equals_string("/etc/systemd/system/parca.service", svc))

        prof_dir = Path("/var/lib/parca")
        self.assertTrue(prof_dir.exists())
        self.assertEqual(prof_dir.owner(), "parca")

    def test_write_configs_storage_in_memory(self):
        config = {
            "storage-persist": False,
            "memory-storage-limit": 1024,
            "juju-scrape-interval": 5,
        }
        self.harness.charm._configure_parca(config)

        storage_config = ["--storage-in-memory=true", "--storage-active-memory=1073741824"]
        # Check the systemd service was rendered correctly
        svc = _render_template(
            "src/configs/parca.service", {"storage_config": " ".join(storage_config)}
        )
        self.assertTrue(_file_content_equals_string("/etc/systemd/system/parca.service", svc))

    def test_write_configs_scrape_interval(self):
        config = {
            "storage-persist": False,
            "memory-storage-limit": 1024,
            "juju-scrape-interval": 5,
        }
        self.harness.charm._configure_parca(config)
        # Check the parca.yaml was rendered correctly
        cfg = _render_template("src/configs/parca.yaml", {"interval": 5})
        self.assertTrue(_file_content_equals_string("/etc/parca/parca.yaml", cfg))

    def test_remove_charm_cleanup(self):
        # Make sure the test can run independently - ensure files are present
        self.harness.charm._configure_parca(
            {
                "storage-persist": False,
                "memory-storage-limit": 1024,
                "juju-scrape-interval": 5,
            }
        )
        self.harness.charm._cleanup()
        paths = [
            "/usr/bin/parca",
            "/etc/parca",
            "/etc/systemd/system/juju-introspect.service",
            "/etc/systemd/system/parca.service",
        ]
        for path in paths:
            self.assertFalse(Path(path).exists())

    # TODO(jnsgruk): Disabled while pulling Parca from charm itself
    # def test_install_parca(self):
    #     self.harness.charm._install_parca_bin()
    #     self.assertTrue(Path("/usr/bin/parca").exists())
    #     parca_version = check_output(["/usr/bin/parca", "--version"])
    #     self.assertTrue(f"parca, version {PARCA_VERSION}" in parca_version.decode())
