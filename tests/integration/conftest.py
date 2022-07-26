# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

from pytest import fixture
from pytest_operator.plugin import OpsTest


@fixture(scope="module")
async def parca_charm(ops_test: OpsTest):
    """Parca charm used for integration testing."""
    charm = await ops_test.build_charm(".")
    return charm
