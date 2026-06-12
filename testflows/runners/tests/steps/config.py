"""Shared @TestStep(Given) fixtures for config-parsing tests."""
import os
import tempfile
import textwrap

from testflows.core import *


@TestStep(Given)
def write_config(self, yaml_text):
    """Write ``yaml_text`` (body of the ``config:`` section) to a temp file
    and yield its path. The file is removed on exit.

    parse_config() expects the document to be nested under a top-level
    ``config:`` key, so the body is indented and prefixed automatically.
    """
    indented = textwrap.indent(textwrap.dedent(yaml_text), "  ")
    full_yaml = "config:\n" + indented
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        f.write(full_yaml)
        f.close()
        yield f.name
    finally:
        with Finally(f"remove {f.name}"):
            if os.path.exists(f.name):
                os.unlink(f.name)
