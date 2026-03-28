"""Tests for config-aware prompt builders."""

import pytest

from promptplot.config import PaperConfig, PenConfig
from promptplot.llm import (
    build_gcode_prompt,
    build_reflection_prompt,
    build_next_command_prompt,
    STYLE_PRESETS,
)


class TestBuildGcodePrompt:
    def test_default_config_dimensions(self):
        """Default A4 paper should produce 190x277 drawable dimensions."""
        prompt = build_gcode_prompt("draw a cat", PaperConfig(), PenConfig())
        assert "190" in prompt
        assert "277" in prompt

    def test_custom_paper_dimensions(self):
        """Custom paper changes prompt text."""
        paper = PaperConfig(width=420, height=297, margin_x=15, margin_y=15)
        prompt = build_gcode_prompt("draw a line", paper, PenConfig())
        assert "390" in prompt  # 420 - 2*15
        assert "267" in prompt  # 297 - 2*15

    def test_pen_s_value_in_prompt(self):
        """Custom pen_down_s_value appears in prompt."""
        pen = PenConfig(pen_down_s_value=500)
        prompt = build_gcode_prompt("draw a square", PaperConfig(), pen)
        assert "S500" in prompt
        assert "S100" not in prompt  # old hardcoded value should not appear

    def test_feed_rate_in_prompt(self):
        """Custom feed_rate appears in prompt."""
        pen = PenConfig(feed_rate=3000)
        prompt = build_gcode_prompt("draw a circle", PaperConfig(), pen)
        assert "F3000" in prompt

    def test_default_feed_rate(self):
        """Default feed rate is 2000."""
        prompt = build_gcode_prompt("draw a line", PaperConfig(), PenConfig())
        assert "F2000" in prompt

    def test_coordinate_bounds_in_prompt(self):
        """Prompt includes min/max coordinate bounds."""
        paper = PaperConfig(width=210, height=297, margin_x=10, margin_y=10)
        prompt = build_gcode_prompt("draw a star", paper, PenConfig())
        assert "10.0" in prompt  # min x/y
        assert "200.0" in prompt  # max x
        assert "287.0" in prompt  # max y

    def test_center_in_prompt(self):
        """Prompt includes canvas center."""
        paper = PaperConfig(width=210, height=297, margin_x=10, margin_y=10)
        prompt = build_gcode_prompt("draw a circle", paper, PenConfig())
        assert "105.0" in prompt  # center x
        assert "148.5" in prompt  # center y

    def test_landscape_orientation_tip(self):
        """Landscape paper gets horizontal composition tip."""
        paper = PaperConfig(width=420, height=297)
        prompt = build_gcode_prompt("draw a landscape", paper, PenConfig())
        assert "wider than tall" in prompt

    def test_portrait_orientation_tip(self):
        """Portrait paper gets vertical composition tip."""
        paper = PaperConfig(width=210, height=297)
        prompt = build_gcode_prompt("draw a portrait", paper, PenConfig())
        assert "taller than wide" in prompt

    def test_style_presets(self):
        """Different style presets produce different prompt text."""
        for style_name in STYLE_PRESETS:
            prompt = build_gcode_prompt("draw a cat", PaperConfig(), PenConfig(), style=style_name)
            assert STYLE_PRESETS[style_name].split("\n")[0] in prompt

    def test_few_shot_geometric(self):
        """Geometric keywords trigger geometric example."""
        prompt = build_gcode_prompt("draw a square", PaperConfig(), PenConfig())
        assert "REFERENCE EXAMPLE" in prompt
        assert "cross-hatching" in prompt

    def test_few_shot_organic(self):
        """Organic keywords trigger organic example."""
        prompt = build_gcode_prompt("draw a flower", PaperConfig(), PenConfig())
        assert "REFERENCE EXAMPLE" in prompt
        assert "curved petals" in prompt

    def test_no_few_shot_for_generic(self):
        """Generic prompts don't include few-shot examples."""
        prompt = build_gcode_prompt("draw something", PaperConfig(), PenConfig())
        assert "REFERENCE EXAMPLE" not in prompt

    def test_json_structure_in_prompt(self):
        """Prompt includes valid JSON example structure."""
        prompt = build_gcode_prompt("draw a line", PaperConfig(), PenConfig())
        assert '"commands"' in prompt
        assert '"command": "M5"' in prompt
        assert '"command": "G0"' in prompt


class TestBuildReflectionPrompt:
    def test_includes_coordinate_ranges(self):
        """Reflection prompt includes valid coordinate ranges."""
        paper = PaperConfig(width=210, height=297, margin_x=10, margin_y=10)
        prompt = build_reflection_prompt("bad output", "parse error", paper)
        assert "10.0" in prompt
        assert "200.0" in prompt
        assert "287.0" in prompt

    def test_includes_error(self):
        """Reflection prompt includes the error details."""
        prompt = build_reflection_prompt("bad", "Invalid JSON", PaperConfig())
        assert "Invalid JSON" in prompt

    def test_includes_previous_response(self):
        """Reflection prompt includes the previous wrong response."""
        prompt = build_reflection_prompt("malformed json", "error", PaperConfig())
        assert "malformed json" in prompt


class TestBuildNextCommandPrompt:
    def test_uses_config_values(self):
        """Streaming prompt uses actual config values."""
        paper = PaperConfig(width=300, height=400, margin_x=20, margin_y=20)
        pen = PenConfig(pen_down_s_value=800, feed_rate=1500)
        prompt = build_next_command_prompt("draw a line", "No previous commands", paper, pen)
        assert "S800" in prompt
        assert "f=1500" in prompt or "F1500" in prompt
        assert "260" in prompt  # 300 - 2*20
        assert "360" in prompt  # 400 - 2*20
