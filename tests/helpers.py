# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.


import os
from types import SimpleNamespace

from jinja2 import Template

DEFAULT_PARCA_CONFIG = {
    "storage-persist": False,
    "memory-storage-limit": 1024,
    "juju-scrape-interval": 5,
}

FAKE_PWUID = SimpleNamespace(pw_uid=1000, pw_gid=1000)


def file_content_equals_string(filename: str, expected: str):
    """Check if the contents of file 'filename' equal the 'expected' param."""
    with open(filename) as f:
        return f.read() == expected


def render_template(template, context):
    """Render a Jinja2 template at the specified path with specified context.

    Return the rendered file as a string.
    """
    with open(template) as f:
        template = Template(f.read())
    return template.render(**context)


def install_fake_daemon(filename):
    """The functional test machine lacks some binaries; write fake binary to given filename."""
    with open(filename, "w+") as f:
        # Simple bash loop that runs infinitely
        f.write("""#!/bin/bash\nwhile true; do sleep 2; done""")
    os.chmod(filename, 0o755)
