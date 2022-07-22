#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import requests
from pytest import mark
from pytest_operator.plugin import OpsTest
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential as wexp

logger = logging.getLogger(__name__)

PARCA = "parca"
UNIT_0 = f"{PARCA}/0"


@mark.abort_on_fail
@mark.skip_if_deployed
async def test_deploy(ops_test: OpsTest, parca_charm):
    await ops_test.model.deploy(await parca_charm, application_name=PARCA, to="0")
    # issuing dummy update_status just to trigger an event
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[PARCA], status="active", timeout=1000)
        assert ops_test.model.applications[PARCA].units[0].workload_status == "active"


@mark.abort_on_fail
@retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
async def test_application_is_up(ops_test: OpsTest):
    status = await ops_test.model.get_status()  # noqa: F821
    unit = list(status.applications[PARCA].units)[0]
    address = status["applications"][PARCA]["units"][unit]["public-address"]
    response = requests.get(f"http://{address}:7070/")
    assert response.status_code == 200
    response = requests.get(f"http://{address}:7070/metrics")
    assert response.status_code == 200
