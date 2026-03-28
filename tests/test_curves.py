"""Tests for arc approximation in promptplot/postprocess.py."""

import pytest
from promptplot.models import GCodeCommand, GCodeProgram
from promptplot.postprocess import approximate_arcs


def _prog(data):
    return GCodeProgram(commands=[GCodeCommand(**c) for c in data])


class TestApproximateArcs:
    def test_no_arcs_passthrough(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = approximate_arcs(prog)
        assert len(result.commands) == len(prog.commands)

    def test_g2_arc_converted(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G2", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = approximate_arcs(prog, segments_per_arc=12)
        # G2 should be replaced by 12 G1 segments
        g1_cmds = [c for c in result.commands if c.command == "G1"]
        assert len(g1_cmds) == 12
        # No G2 should remain
        g2_cmds = [c for c in result.commands if c.command == "G2"]
        assert len(g2_cmds) == 0

    def test_g3_arc_converted(self):
        prog = _prog([
            {"command": "M3", "s": 1000},
            {"command": "G3", "x": 30, "y": 30, "f": 2000},
            {"command": "M5"},
        ])
        result = approximate_arcs(prog, segments_per_arc=8)
        g1_cmds = [c for c in result.commands if c.command == "G1"]
        assert len(g1_cmds) == 8

    def test_configurable_segments(self):
        prog = _prog([
            {"command": "M3", "s": 1000},
            {"command": "G2", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        for n in [4, 8, 16]:
            result = approximate_arcs(prog, segments_per_arc=n)
            g1_cmds = [c for c in result.commands if c.command == "G1"]
            assert len(g1_cmds) == n

    def test_metadata_set(self):
        prog = _prog([
            {"command": "M3", "s": 1000},
            {"command": "G2", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = approximate_arcs(prog)
        assert result.metadata.get("arcs_approximated") is True

    def test_mixed_commands(self):
        prog = _prog([
            {"command": "M5"},
            {"command": "G0", "x": 10, "y": 10},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 20, "y": 20, "f": 2000},
            {"command": "G2", "x": 40, "y": 40, "f": 2000},
            {"command": "G1", "x": 50, "y": 50, "f": 2000},
            {"command": "M5"},
        ])
        result = approximate_arcs(prog, segments_per_arc=8)
        # Original: M5, G0, M3, G1, G2(→8 G1), G1, M5 = 6 non-arc + 8 = 14
        assert len(result.commands) == 6 + 8  # replaced G2 with 8 G1s
        g2_cmds = [c for c in result.commands if c.command == "G2"]
        assert len(g2_cmds) == 0
