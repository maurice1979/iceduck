import os

import pytest


def pytest_collection_modifyitems(config, items):
    """tests/integration/* require a running Floci with applied infra —
    skip them unless ICEDUCK_IT=1 is set, per the project's test convention
    (docs/plans/0001-lakehouse-architecture-outline.md)."""
    if os.environ.get("ICEDUCK_IT") == "1":
        return
    skip_it = pytest.mark.skip(reason="integration test — set ICEDUCK_IT=1 to run (needs a running Floci + applied infra)")
    for item in items:
        if "integration" in item.nodeid.split("/"):
            item.add_marker(skip_it)
