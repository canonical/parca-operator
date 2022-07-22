# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest import fixture
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@fixture(scope="module")
async def parca_charm(ops_test: OpsTest):
    """Parca charm used for integration testing."""
    charm = await ops_test.build_charm(".")
    return charm
