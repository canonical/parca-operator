# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

"""Helpers for the Parca operator."""

from jinja2 import Template


def render_template(template_filename, target_file, context):
    """Render a give template file to target, with a given context."""
    # Open the template from the source file
    with open(template_filename, "r") as t:
        template = Template(t.read())
    # Render the template with the correct context
    rendered = template.render(**context)
    # Write the template out to disk
    with open(target_file, "w+") as t:
        t.write(rendered)
