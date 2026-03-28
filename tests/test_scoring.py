"""Tests for promptplot/scoring.py — quality scorer and style profiles."""

import pytest
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.config import PaperConfig
from promptplot.scoring import score_gcode, QualityReport, extract_style_profile, StyleProfile


def _prog(data):
    return GCodeProgram(commands=[GCodeCommand(**c) for c in data])


@pytest.fixture
def paper():
    return PaperConfig(width=210, height=297, margin_x=10, margin_y=10)


@pytest.fixture
def good_program():
    """A reasonable program covering decent area."""
    return _prog([
        {"command": "M5"},
        {"command": "G0", "x": 30, "y": 30},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 180, "y": 30, "f": 2000},
        {"command": "G1", "x": 180, "y": 260, "f": 2000},
        {"command": "G1", "x": 30, "y": 260, "f": 2000},
        {"command": "G1", "x": 30, "y": 30, "f": 2000},
        {"command": "M5"},
        # Cross-hatching
        {"command": "G0", "x": 60, "y": 30},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 60, "y": 260, "f": 2000},
        {"command": "M5"},
        {"command": "G0", "x": 100, "y": 30},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 100, "y": 260, "f": 2000},
        {"command": "M5"},
        {"command": "G0", "x": 140, "y": 30},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 140, "y": 260, "f": 2000},
        {"command": "M5"},
        {"command": "G0", "x": 30, "y": 100},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 180, "y": 100, "f": 2000},
        {"command": "M5"},
        {"command": "G0", "x": 30, "y": 180},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 180, "y": 180, "f": 2000},
        {"command": "M5"},
        {"command": "G0", "x": 0, "y": 0},
    ])


@pytest.fixture
def minimal_program():
    return _prog([
        {"command": "M5"},
        {"command": "G0", "x": 5, "y": 5},
        {"command": "M3", "s": 1000},
        {"command": "G1", "x": 10, "y": 10, "f": 2000},
        {"command": "M5"},
    ])


class TestScoreGCode:
    def test_good_program_scores_well(self, good_program, paper):
        report = score_gcode(good_program, paper)
        assert report.grade in ("A", "B")
        assert report.canvas_utilization > 0.3
        assert report.stroke_count >= 5
        assert report.total_draw_distance > 0
        assert report.command_count > 20

    def test_minimal_program_low_grade(self, minimal_program, paper):
        report = score_gcode(minimal_program, paper)
        assert report.grade in ("D", "F")
        assert report.canvas_utilization < 0.1

    def test_empty_drawing_grade_f(self, paper):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 50, "y": 50},
            {"command": "M5"},
        ])
        report = score_gcode(prog, paper)
        assert report.grade == "F"
        assert report.total_draw_distance == 0

    def test_report_fields(self, good_program, paper):
        report = score_gcode(good_program, paper)
        assert isinstance(report.canvas_utilization, float)
        assert isinstance(report.stroke_count, int)
        assert isinstance(report.pen_lift_count, int)
        assert isinstance(report.estimated_time_seconds, float)
        assert report.estimated_time_seconds > 0

    def test_to_dict(self, good_program, paper):
        report = score_gcode(good_program, paper)
        d = report.to_dict()
        assert "grade" in d
        assert "canvas_utilization" in d


class TestExtractStyleProfile:
    def test_basic_profile(self, good_program, paper):
        profile = extract_style_profile(good_program, paper)
        assert isinstance(profile, StyleProfile)
        assert profile.avg_stroke_length > 0
        assert profile.canvas_utilization > 0

    def test_to_prompt_hints(self, good_program, paper):
        profile = extract_style_profile(good_program, paper)
        hints = profile.to_prompt_hints()
        assert isinstance(hints, str)
        assert len(hints) > 0

    def test_empty_program(self, paper):
        prog = _prog([{"command": "M5"}])
        profile = extract_style_profile(prog, paper)
        assert profile.avg_stroke_length == 0.0
