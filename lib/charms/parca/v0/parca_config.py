# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Helpers for generating Parca configuration.

This library is used for generating YAML configuration files for Parca, the continuous profiling
tool. More information about Parca can be found at https://www.parca.dev/.

You can use this library as follows:

```python
from charms.parca.v0.parca_config import ParcaConfig, parca_command_line

# Generate a Parca config and get the dictionary representation
config = ParcaConfig().to_dict()

# Get the YAML representation of the config
yaml_config = str(ParcaConfig())

# Generate a command line to start Parca (pass the Parca charm config)
cmd = parca_command_line(app_config)
```
"""
import yaml

# The unique Charmhub library identifier, never change it
LIBID = "96af36467bb844d7ab8447058ebbc73a"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 6


DEFAULT_BIN_PATH = "/parca"
DEFAULT_CONFIG_PATH = "/etc/parca/parca.yaml"
DEFAULT_PROFILE_PATH = "/var/lib/parca"


def parca_command_line(
    app_config: dict = None,
    *,
    bin_path: str = DEFAULT_BIN_PATH,
    config_path: str = DEFAULT_CONFIG_PATH,
    profile_path: str = DEFAULT_PROFILE_PATH,
    store_config: dict = None,
) -> str:
    """Generate a valid Parca command line.

    Args:
        app_config: Charm configuration dictionary.
        bin_path: Path to the Parca binary to be started.
        config_path: Path to the Parca YAML configuration file.
        profile_path: Path to profile storage directory.
        store_config: Configuration to send profiles to a remote store
    """
    cmd = [str(bin_path), f"--config-path={config_path}"]

    # Render the template files with the correct values

    if app_config.get("enable-persistence", None):
        # Add the correct command line options for disk persistence
        cmd.append("--enable-persistence")
        cmd.append(f"--storage-path={profile_path}")
    else:
        limit = app_config["memory-storage-limit"] * 1048576
        cmd.append(f"--storage-active-memory={limit}")

    if store_config is not None:
        store_config_args = []

        if addr := store_config.get("remote-store-address", None):
            store_config_args.append(f"--store-address={addr}")

        if token := store_config.get("remote-store-bearer-token", None):
            store_config_args.append(f"--bearer-token={token}")

        if insecure := store_config.get("remote-store-insecure", None):
            store_config_args.append(f"--insecure={insecure}")

        if store_config_args:
            store_config_args.append("--mode=scraper-only")
            cmd += store_config_args

    return " ".join(cmd)


def parse_version(vstr: str) -> str:
    """Parse the output of 'parca --version' and return a representative string."""
    splits = vstr.split(" ")
    # If we're not on a 'proper' released version, include the first few digits of
    # the commit we're build from - e.g. 0.12.1-next+deadbeef
    if "-next" in splits[2]:
        return f"{splits[2]}+{splits[4][:6]}"
    return splits[2]


class ParcaConfig:
    """Class representing the Parca config file."""

    def __init__(self, scrape_configs=[], *, profile_path=DEFAULT_PROFILE_PATH, s3_creds=None):
        self._profile_path = str(profile_path)
        self._scrape_configs = scrape_configs
        self._s3_credentials = s3_creds

    @property
    def _config(self) -> dict:
        if self.s3_creds is None:
            return {
                # Read whatever config was here before overwriting
                "object_storage": {
                    "bucket": {"type": "FILESYSTEM", "config": {"directory": self._profile_path}}
                },
                "scrape_configs": self._scrape_configs,
            }

    def to_dict(self) -> dict:
        """Return the Parca config as a Python dictionary."""
        return self._config

    def __str__(self) -> str:
        """Return the Parca config as a YAML string."""
        return yaml.safe_dump(self._config)
