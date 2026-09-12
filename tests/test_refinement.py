"""Tests for preview-guided batch refinement."""

import json
from pathlib import Path

import pytest

from promptplot.config import PromptPlotConfig
from promptplot.llm import LLMProvider
from promptplot.workflow import BatchGCodeWorkflow


class RefinementProvider(LLMProvider):
    def __init__(self, responses):
        super().__init__(timeout=10)
        self.responses = list(responses)

    @property
    def provider_name(self) -> str:
        return "test"

    async def acomplete(self, prompt: str) -> str:
        return self.responses.pop(0)

    async def acomplete_multimodal(self, prompt: str, image_paths=None) -> str:
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_batch_refinement_prefers_improved_result(monkeypatch, tmp_path):
    def _fake_preview(self, program, output_path):
        Path(output_path).write_bytes(b"png")

    monkeypatch.setattr("promptplot.visualizer.GCodeVisualizer.preview", _fake_preview)

    initial = json.dumps({
        "commands": [
            {
                "command": "FREEFORM",
                "type": "silhouette_outline",
                "params": {"points": [[95, 145], [105, 145], [105, 155], [95, 155]], "closed": True},
            }
        ]
    })
    critique = json.dumps({
        "dominant_issue": "texture",
        "silhouette_clarity": 0.4,
        "canvas_balance": 0.2,
        "density_variation": 0.1,
        "geometry_strength": 0.2,
        "freeform_quality": 0.2,
        "failure_reasons": ["central_clustering", "insufficient_detail"],
    })
    refined = json.dumps({
        "commands": [
            {"command": "PRIMITIVE", "type": "hatch", "params": {"x": 30, "y": 30, "width": 120, "height": 180, "spacing": 8}},
            {
                "command": "FREEFORM",
                "type": "texture_strokes",
                "params": {"centers": [[40, 40], [80, 60], [120, 90], [140, 150]], "stroke_length": 10, "angle": 35},
            },
        ]
    })
    provider = RefinementProvider([initial, critique, refined])

    config = PromptPlotConfig()
    config.vision.preview_feedback = True
    config.vision.max_feedback_iterations = 1
    config.workflow.planning_enabled = False
    config.workflow.multipass.enabled = False

    wf = BatchGCodeWorkflow(llm=provider, config=config)
    result = await wf.run(prompt="clouds")

    program = result["program"]
    assert len(program["commands"]) > 4
    assert any(cmd["command"] == "G1" for cmd in program["commands"])
    assert result["analysis_artifacts"] is not None
    assert result["analysis_artifacts"]["analysis"]["weak_regions"]
    assert result["refinement_action"] in {"detail", "plan_and_detail"}
