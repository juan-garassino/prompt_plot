"""Tests for SupervisorWorkerWorkflow."""

import json
import re
import pytest
from unittest.mock import AsyncMock, Mock

from promptplot.workflow import SupervisorWorkerWorkflow
from promptplot.config import PromptPlotConfig
from promptplot.llm import LLMProvider
from promptplot.models import Region


def _parse_region_from_prompt(prompt: str) -> Region:
    mx = re.search(r"X:\s*\[([\d.]+),\s*([\d.]+)\]", prompt)
    my = re.search(r"Y:\s*\[([\d.]+),\s*([\d.]+)\]", prompt)
    return Region(bounds=(float(mx.group(1)), float(my.group(1)),
                          float(mx.group(2)), float(my.group(2))))


def _worker_response_for_region(region) -> str:
    """Build a canned response whose G1s densely fill the given region."""
    x0, y0, x1, y1 = region.bounds
    w = x1 - x0
    h = y1 - y0
    cmds = [{"command": "M5"}, {"command": "G0", "x": x0 + 2, "y": y0 + 2}]
    cmds.append({"command": "M3", "s": 1000})
    for i in range(30):
        t = i / 30.0
        cmds.append({
            "command": "G1",
            "x": x0 + w * t * 0.9 + 1.0,
            "y": y0 + h * (0.1 + 0.8 * ((i % 10) / 10.0)),
            "f": 2000,
        })
    cmds.append({"command": "M5"})
    return json.dumps({"commands": cmds})


@pytest.fixture
def config():
    cfg = PromptPlotConfig()
    cfg.workflow.planning_enabled = False
    return cfg


@pytest.fixture
def mock_llm():
    mock = Mock(spec=LLMProvider)
    call_count = {"n": 0}

    async def acomplete(prompt: str) -> str:
        call_count["n"] += 1
        region = _parse_region_from_prompt(prompt)
        return _worker_response_for_region(region)

    mock.acomplete = AsyncMock(side_effect=acomplete)
    return mock, call_count


@pytest.mark.asyncio
async def test_n_workers_called(config, mock_llm):
    llm, calls = mock_llm
    wf = SupervisorWorkerWorkflow(llm=llm, config=config, regions=4, strategy="grid_2x2")
    result = await wf.run(prompt="test scene")
    # One per region
    assert calls["n"] == 4
    assert result["commands_count"] > 4


@pytest.mark.asyncio
async def test_merged_output_exceeds_regions(config, mock_llm):
    llm, _ = mock_llm
    wf = SupervisorWorkerWorkflow(llm=llm, config=config, regions=4, strategy="grid_2x2")
    result = await wf.run(prompt="test scene")
    # 4 workers × ~43 cmds each = ~170 commands. Sum > 4
    assert result["commands_count"] > 50


@pytest.mark.asyncio
async def test_weak_region_retry(config):
    """Force a weak region by returning empty for region 0, full for others."""
    mock = Mock(spec=LLMProvider)
    idx = {"i": 0}

    async def acomplete(prompt: str) -> str:
        i = idx["i"]
        idx["i"] += 1
        if i == 0:
            return json.dumps({"commands": [{"command": "M5"}]})
        region = _parse_region_from_prompt(prompt)
        return _worker_response_for_region(region)

    mock.acomplete = AsyncMock(side_effect=acomplete)

    wf = SupervisorWorkerWorkflow(llm=mock, config=config, regions=4, strategy="grid_2x2")
    result = await wf.run(prompt="test scene")
    # 4 initial + 1 retry for the weak region
    assert idx["i"] == 5
    assert result["commands_count"] > 50
