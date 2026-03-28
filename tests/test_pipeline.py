"""Tests for promptplot/pipeline.py — FilePipeline."""

import pytest
import asyncio
from pathlib import Path

from promptplot.pipeline import FilePipeline
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PromptPlotConfig
from promptplot.plotter import SimulatedPlotter


@pytest.fixture
def config():
    return PromptPlotConfig()


@pytest.fixture
def pipeline(config):
    return FilePipeline(config)


@pytest.fixture
def gcode_file(tmp_path):
    content = """M5
G0 X10 Y10
M3 S1000
G1 X50 Y50 F2000
G1 X80 Y80 F2000
M5
G0 X0 Y0
"""
    path = tmp_path / "test.gcode"
    path.write_text(content)
    return str(path)


@pytest.fixture
def empty_gcode_file(tmp_path):
    path = tmp_path / "empty.gcode"
    path.write_text("; just comments\n; nothing here\n")
    return str(path)


class TestFilePipeline:
    def test_init_stores_config(self, config):
        p = FilePipeline(config)
        assert p.config is config

    def test_init_default_config(self):
        p = FilePipeline()
        assert p.config is not None

    def test_load_gcode_file(self, pipeline, gcode_file):
        program = pipeline.load_gcode_file(gcode_file)
        assert isinstance(program, GCodeProgram)
        assert len(program.commands) > 0
        assert program.metadata["source_file"] is not None

    def test_load_gcode_file_not_found(self, pipeline):
        with pytest.raises(FileNotFoundError):
            pipeline.load_gcode_file("/nonexistent/file.gcode")

    def test_load_gcode_file_empty(self, pipeline, empty_gcode_file):
        with pytest.raises(ValueError, match="No valid GCode"):
            pipeline.load_gcode_file(empty_gcode_file)

    @pytest.mark.asyncio
    async def test_process_file_preview_only(self, pipeline, gcode_file):
        processed, success, errors = await pipeline.process_file(
            gcode_file, preview_only=True
        )
        assert isinstance(processed, GCodeProgram)
        assert success == 0
        assert errors == 0

    @pytest.mark.asyncio
    async def test_process_file_with_simulated_plotter(self, pipeline, gcode_file):
        plotter = SimulatedPlotter(command_delay=0)
        processed, success, errors = await pipeline.process_file(
            gcode_file, plotter=plotter
        )
        assert isinstance(processed, GCodeProgram)
        assert success > 0
        assert errors == 0

    @pytest.mark.asyncio
    async def test_process_and_save(self, pipeline, gcode_file, tmp_path):
        output = str(tmp_path / "output.gcode")
        processed = await pipeline.process_and_save(gcode_file, output)
        assert isinstance(processed, GCodeProgram)
        assert Path(output).exists()
        content = Path(output).read_text()
        assert "M5" in content
