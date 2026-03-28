"""Tests for multi-pass generation and related workflow features."""

import pytest
import json
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig, MultiPassConfig
from promptplot.postprocess import run_pipeline


def _prog(data):
    return GCodeProgram(commands=[GCodeCommand(**c) for c in data])


class TestMultiPassConfig:
    def test_default_disabled(self):
        cfg = PromptPlotConfig()
        assert cfg.workflow.multipass.enabled is False

    def test_enable_multipass(self):
        cfg = PromptPlotConfig()
        cfg.workflow.multipass.enabled = True
        assert cfg.workflow.multipass.enabled is True
        assert cfg.workflow.multipass.outline_style == "precise"
        assert cfg.workflow.multipass.detail_style == "artistic"


class TestMultiPassMerge:
    def test_merged_program_has_commands_from_both(self):
        """Simulates the merge logic in the workflow end step."""
        outline = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ])

        detail = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 20, "y": 20},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 40, "y": 40, "f": 2000},
            {"command": "G1", "x": 45, "y": 45, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ])

        # Merge: outline (without last cmd) + detail
        merged_cmds = list(outline.commands[:-1]) + list(detail.commands)
        merged = GCodeProgram(
            commands=merged_cmds,
            metadata={"multipass": True},
        )

        assert len(merged.commands) > len(outline.commands)
        assert len(merged.commands) > len(detail.commands)
        assert merged.metadata["multipass"] is True

    def test_merged_program_survives_postprocess(self):
        """Merged programs should survive the full postprocess pipeline."""
        outline = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        detail = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 20, "y": 20},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 40, "y": 40, "f": 2000},
            {"command": "M5"},
        ])

        merged_cmds = list(outline.commands) + list(detail.commands)
        merged = GCodeProgram(commands=merged_cmds)

        config = PromptPlotConfig()
        result = run_pipeline(merged, config)
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 0
        # Should have drawing commands from both passes
        g1_cmds = [c for c in result.commands if c.command == "G1"]
        assert len(g1_cmds) >= 2
