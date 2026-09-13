"""Tests for creative-mode routing and candidate search."""

import json

import pytest

from promptplot.config import PromptPlotConfig
from promptplot.llm import LLMProvider
from promptplot.workflow import BatchGCodeWorkflow


class SequenceProvider(LLMProvider):
    def __init__(self, responses):
        super().__init__(timeout=10)
        self.responses = list(responses)

    @property
    def provider_name(self) -> str:
        return "seq"

    async def acomplete(self, prompt: str) -> str:
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_candidate_search_prefers_stronger_abstract_output():
    plan1 = json.dumps({
        "regions": [
            {"name": "focus", "role": "focal", "x": 20, "y": 20, "width": 60, "height": 60, "field_family": "moire_grid", "density": "dense", "rhythm": "interference", "layer": 1},
            {"name": "void", "role": "void", "x": 120, "y": 40, "width": 40, "height": 70, "field_family": "mask_region", "density": "sparse", "rhythm": "parallel", "layer": 0},
        ]
    })
    plan2 = json.dumps({
        "regions": [
            {"name": "focus", "role": "focal", "x": 30, "y": 30, "width": 120, "height": 160, "field_family": "field_stack", "density": "dense", "rhythm": "wave", "layer": 1},
            {"name": "void", "role": "void", "x": 160, "y": 40, "width": 20, "height": 50, "field_family": "mask_region", "density": "sparse", "rhythm": "parallel", "layer": 0},
        ]
    })
    weak = json.dumps({
        "commands": [
            {"command": "FREEFORM", "type": "field_stack", "params": {"x": 90, "y": 120, "width": 20, "height": 20, "layers": 1}}
        ]
    })
    strong = json.dumps({
        "commands": [
            {"command": "FREEFORM", "type": "moire_grid", "params": {"x": 20, "y": 20, "width": 120, "height": 180, "spacing": 8}},
            {"command": "FREEFORM", "type": "border_system", "params": {"x": 10, "y": 10, "width": 170, "height": 240, "layers": 2}},
        ]
    })

    provider = SequenceProvider([plan1, plan2, weak, strong])
    config = PromptPlotConfig()
    config.workflow.creative_mode = "abstract"
    config.workflow.planning_enabled = True
    config.workflow.candidate_count = 2
    config.vision.preview_feedback = False
    config.workflow.multipass.enabled = False

    wf = BatchGCodeWorkflow(llm=provider, config=config)
    result = await wf.run(prompt="moire field")
    assert result["program"]["metadata"]["creative_mode"] == "abstract"
    assert len(result["program"]["commands"]) > 6
