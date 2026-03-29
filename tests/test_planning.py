"""Tests for LLM-driven planning phase."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from promptplot.models import CompositionSubject, CompositionPlan
from promptplot.llm import build_composition_plan_prompt
from promptplot.config import PaperConfig, PromptPlotConfig


class TestCompositionPlan:
    def test_valid_plan(self):
        plan = CompositionPlan(
            subjects=[
                CompositionSubject(name="tree", x=100, y=150, width=80, height=120),
                CompositionSubject(name="sun", x=180, y=50, width=40, height=40, density="sparse"),
            ],
            style="artistic",
            estimated_commands=80,
        )
        assert len(plan.subjects) == 2
        assert plan.subjects[0].name == "tree"

    def test_empty_subjects_raises(self):
        with pytest.raises(ValueError, match="at least one subject"):
            CompositionPlan(subjects=[], style="artistic")

    def test_validate_bounds_ok(self):
        plan = CompositionPlan(
            subjects=[
                CompositionSubject(name="box", x=50, y=50, width=40, height=40),
            ],
        )
        violations = plan.validate_bounds(210, 297)
        assert violations == []

    def test_validate_bounds_violation(self):
        plan = CompositionPlan(
            subjects=[
                CompositionSubject(name="big", x=200, y=290, width=40, height=20),
            ],
        )
        violations = plan.validate_bounds(210, 297)
        assert len(violations) > 0

    def test_to_prompt_guidance(self):
        plan = CompositionPlan(
            subjects=[
                CompositionSubject(
                    name="house", description="a small house",
                    x=100, y=150, width=60, height=50, density="medium", priority=1,
                ),
            ],
            notes="Keep it simple",
        )
        guidance = plan.to_prompt_guidance()
        assert "COMPOSITION PLAN" in guidance
        assert "house" in guidance
        assert "100.0" in guidance
        assert "Keep it simple" in guidance

    def test_invalid_density(self):
        with pytest.raises(ValueError, match="density"):
            CompositionSubject(name="x", x=0, y=0, width=10, height=10, density="ultra")


class TestBuildCompositionPlanPrompt:
    def test_prompt_contains_canvas_info(self):
        paper = PaperConfig(width=210, height=297, margin_x=10, margin_y=10)
        prompt = build_composition_plan_prompt("a house with garden", paper, "artistic")
        assert "a house with garden" in prompt
        assert "190" in prompt  # drawable width
        assert "277" in prompt  # drawable height
        assert "artistic" in prompt
        assert "JSON" in prompt


class TestPlanningWorkflow:
    @pytest.mark.asyncio
    async def test_planning_disabled_skips(self):
        """When planning_enabled=False, workflow goes straight to GENERATING."""
        from promptplot.workflow import BatchGCodeWorkflow
        config = PromptPlotConfig()
        config.workflow.planning_enabled = False

        mock_llm = AsyncMock()
        mock_llm.acomplete = AsyncMock(return_value=json.dumps({
            "commands": [
                {"command": "M5"},
                {"command": "G0", "x": 50, "y": 50},
                {"command": "M3", "s": 1000},
                {"command": "G1", "x": 100, "y": 100, "f": 2000},
                {"command": "M5"},
                {"command": "G0", "x": 0, "y": 0},
            ]
        }))

        wf = BatchGCodeWorkflow(llm=mock_llm, config=config)
        result = await wf.run(prompt="a square")
        assert result is not None
        assert "gcode" in result

    @pytest.mark.asyncio
    async def test_planning_enabled_calls_plan(self):
        """When planning_enabled=True, plan_composition step runs."""
        from promptplot.workflow import BatchGCodeWorkflow
        config = PromptPlotConfig()
        config.workflow.planning_enabled = True

        plan_json = json.dumps({
            "subjects": [
                {"name": "house", "x": 100, "y": 150, "width": 60, "height": 50}
            ],
            "style": "artistic",
            "estimated_commands": 50,
        })
        gcode_json = json.dumps({
            "commands": [
                {"command": "M5"},
                {"command": "G0", "x": 50, "y": 50},
                {"command": "M3", "s": 1000},
                {"command": "G1", "x": 100, "y": 100, "f": 2000},
                {"command": "M5"},
                {"command": "G0", "x": 0, "y": 0},
            ]
        })

        mock_llm = AsyncMock()
        mock_llm.acomplete = AsyncMock(side_effect=[plan_json, gcode_json])

        wf = BatchGCodeWorkflow(llm=mock_llm, config=config)
        result = await wf.run(prompt="a house")
        assert result is not None
        # LLM called twice: once for plan, once for GCode
        assert mock_llm.acomplete.call_count == 2

    @pytest.mark.asyncio
    async def test_planning_failure_fallback(self):
        """If planning fails, generation proceeds without plan."""
        from promptplot.workflow import BatchGCodeWorkflow
        config = PromptPlotConfig()
        config.workflow.planning_enabled = True

        gcode_json = json.dumps({
            "commands": [
                {"command": "M5"},
                {"command": "G0", "x": 50, "y": 50},
                {"command": "M3", "s": 1000},
                {"command": "G1", "x": 100, "y": 100, "f": 2000},
                {"command": "M5"},
                {"command": "G0", "x": 0, "y": 0},
            ]
        })

        mock_llm = AsyncMock()
        # First call (plan) returns invalid JSON, second call (gcode) returns valid
        mock_llm.acomplete = AsyncMock(side_effect=["not valid json at all", gcode_json])

        wf = BatchGCodeWorkflow(llm=mock_llm, config=config)
        result = await wf.run(prompt="a house")
        assert result is not None
        assert "gcode" in result
