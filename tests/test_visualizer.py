"""Tests for promptplot/visualizer.py — GCodeVisualizer."""

import pytest
from pathlib import Path

from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig

try:
    from promptplot.visualizer import GCodeVisualizer
    import matplotlib
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MATPLOTLIB_AVAILABLE, reason="matplotlib not installed"
)


@pytest.fixture
def config():
    return PromptPlotConfig()


@pytest.fixture
def visualizer(config):
    return GCodeVisualizer(config)


@pytest.fixture
def simple_program():
    return GCodeProgram(commands=[
        GCodeCommand(command="M5"),
        GCodeCommand(command="G0", x=10, y=10),
        GCodeCommand(command="M3", s=1000),
        GCodeCommand(command="G1", x=50, y=50, f=2000),
        GCodeCommand(command="G1", x=80, y=80, f=2000),
        GCodeCommand(command="M5"),
        GCodeCommand(command="G0", x=0, y=0),
    ])


@pytest.fixture
def oob_program():
    """Program with out-of-bounds segments."""
    return GCodeProgram(commands=[
        GCodeCommand(command="M5"),
        GCodeCommand(command="G0", x=10, y=10),
        GCodeCommand(command="M3", s=1000),
        GCodeCommand(command="G1", x=500, y=500, f=2000),
        GCodeCommand(command="M5"),
        GCodeCommand(command="G0", x=0, y=0),
    ])


@pytest.fixture
def empty_program():
    return GCodeProgram(commands=[GCodeCommand(command="M5")])


class TestGCodeVisualizer:
    def test_construction(self, config):
        viz = GCodeVisualizer(config)
        assert viz.config is config

    def test_preview_creates_file(self, visualizer, simple_program, tmp_path):
        output = str(tmp_path / "test_preview.png")
        visualizer.preview(simple_program, output)
        assert Path(output).exists()
        assert Path(output).stat().st_size > 0

    def test_preview_empty_program(self, visualizer, empty_program, tmp_path):
        output = str(tmp_path / "empty_preview.png")
        visualizer.preview(empty_program, output)
        assert Path(output).exists()

    def test_preview_oob_program(self, visualizer, oob_program, tmp_path):
        output = str(tmp_path / "oob_preview.png")
        visualizer.preview(oob_program, output)
        assert Path(output).exists()

    def test_get_stats(self, visualizer, simple_program):
        stats = visualizer.get_stats(simple_program)
        assert "drawing_distance" in stats
        assert "travel_distance" in stats
        assert "pen_cycles" in stats
        assert "total_commands" in stats
        assert stats["drawing_distance"] > 0
        assert stats["pen_cycles"] >= 1

    def test_get_stats_empty(self, visualizer, empty_program):
        stats = visualizer.get_stats(empty_program)
        assert stats["drawing_distance"] == 0
        assert stats["pen_cycles"] == 0

    def test_stats_drawing_segments(self, visualizer, simple_program):
        stats = visualizer.get_stats(simple_program)
        assert stats["drawing_segments"] == 2  # Two G1 commands while pen is down

    def test_construction_without_config(self):
        viz = GCodeVisualizer()
        assert viz.config is None

    def test_analyze_regions_returns_report(self, visualizer, simple_program):
        report = visualizer.analyze_regions(simple_program, creative_mode="figurative")
        assert "global" in report
        assert "regions" in report
        assert len(report["regions"]) > 0

    def test_save_analysis_artifacts(self, visualizer, simple_program, tmp_path):
        artifacts = visualizer.save_analysis_artifacts(
            simple_program,
            str(tmp_path / "analysis"),
            creative_mode="abstract",
        )
        assert Path(artifacts["preview_path"]).exists()
        assert Path(artifacts["overlay_path"]).exists()
        assert Path(artifacts["heatmap_path"]).exists()
        assert Path(artifacts["json_path"]).exists()
        assert artifacts["analysis"]["creative_mode"] == "abstract"
