"""Tests for drawing primitives expansion."""

import math
import json
import pytest

from promptplot.models import (
    GCodeCommand, GCodeProgram, PrimitiveCommand, DrawProgram, DrawCommand,
    VALID_PRIMITIVE_TYPES,
)
from promptplot.primitives import (
    expand_circle, expand_ellipse, expand_polygon, expand_hatch,
    expand_crosshatch, expand_filled_polygon, expand_stipple, expand_spiral,
    expand_flow_field, expand_primitive, expand_primitives, PRIMITIVE_REGISTRY,
    get_primitive_schema, get_all_primitive_schemas, format_schemas_for_prompt,
)
from promptplot.config import PenConfig


# Default pen config for tests
PEN = PenConfig()
FEED = PEN.feed_rate
S_VAL = PEN.pen_down_s_value


def _assert_stroke_structure(cmds):
    """Assert commands follow M5 → G0 → M3 → G1... → M5 structure."""
    assert len(cmds) >= 4, f"Stroke too short: {len(cmds)} commands"
    assert cmds[0].command == "M5"
    assert cmds[1].command == "G0"
    assert cmds[2].command == "M3"
    assert cmds[2].s == S_VAL
    # All middle commands should be G1
    for cmd in cmds[3:-1]:
        assert cmd.command == "G1", f"Expected G1, got {cmd.command}"
        assert cmd.f == FEED
    assert cmds[-1].command == "M5"


# ---------------------------------------------------------------------------
# TestExpandCircle
# ---------------------------------------------------------------------------

class TestExpandCircle:
    def test_default_segments(self):
        cmds = expand_circle(100, 150, 40)
        # M5 + G0 + M3 + 24 G1 segments + M5 = 28
        assert len(cmds) == 28

    def test_custom_segments(self):
        cmds = expand_circle(100, 150, 40, segments=16)
        assert len(cmds) == 20  # M5 + G0 + M3 + 16 G1 + M5

    def test_stroke_structure(self):
        cmds = expand_circle(100, 150, 40)
        _assert_stroke_structure(cmds)

    def test_closes_circle(self):
        """G0 start and last G1 should be the same point (closed shape)."""
        cmds = expand_circle(100, 150, 40, segments=24)
        g0_start = cmds[1]  # G0 to start position
        last_g1 = cmds[-2]  # last G1 before final M5
        assert abs(g0_start.x - (100 + 40)) < 0.01  # starts at (cx+r, cy)
        assert abs(last_g1.x - g0_start.x) < 0.01
        assert abs(last_g1.y - g0_start.y) < 0.01

    def test_radius_accuracy(self):
        cx, cy, r = 100, 150, 40
        cmds = expand_circle(cx, cy, r, segments=24)
        for cmd in cmds:
            if cmd.command == "G1":
                dist = math.sqrt((cmd.x - cx) ** 2 + (cmd.y - cy) ** 2)
                assert abs(dist - r) < 0.1, f"Point at dist {dist:.2f}, expected {r}"


# ---------------------------------------------------------------------------
# TestExpandEllipse
# ---------------------------------------------------------------------------

class TestExpandEllipse:
    def test_basic(self):
        cmds = expand_ellipse(100, 100, 50, 30)
        _assert_stroke_structure(cmds)

    def test_closes(self):
        cmds = expand_ellipse(100, 100, 50, 30, segments=24)
        g0_start = cmds[1]  # G0 to start
        last_g1 = cmds[-2]  # last G1
        assert abs(g0_start.x - last_g1.x) < 0.01
        assert abs(g0_start.y - last_g1.y) < 0.01


# ---------------------------------------------------------------------------
# TestExpandPolygon
# ---------------------------------------------------------------------------

class TestExpandPolygon:
    def test_triangle(self):
        pts = [[50, 50], [100, 50], [75, 100]]
        cmds = expand_polygon(pts)
        _assert_stroke_structure(cmds)
        # 3 original + 1 closing = 4 points → M5+G0+M3 + 3 G1 + M5 = 7
        # G0 goes to first point, then 3 G1 to remaining points including close
        g1_cmds = [c for c in cmds if c.command == "G1"]
        assert len(g1_cmds) == 3  # to pt2, pt3, back to pt1

    def test_closes_polygon(self):
        pts = [[50, 50], [100, 50], [75, 100]]
        cmds = expand_polygon(pts)
        last_g1 = [c for c in cmds if c.command == "G1"][-1]
        assert abs(last_g1.x - 50) < 0.01
        assert abs(last_g1.y - 50) < 0.01

    def test_too_few_points(self):
        assert expand_polygon([[0, 0], [1, 1]]) == []

    def test_already_closed(self):
        pts = [[0, 0], [10, 0], [10, 10], [0, 0]]
        cmds = expand_polygon(pts)
        g1_cmds = [c for c in cmds if c.command == "G1"]
        assert len(g1_cmds) == 3  # no duplicate close


# ---------------------------------------------------------------------------
# TestExpandHatch
# ---------------------------------------------------------------------------

class TestExpandHatch:
    def test_produces_lines(self):
        cmds = expand_hatch(50, 50, 80, 60, angle=0, spacing=10)
        assert len(cmds) > 0
        # Each hatch line is a separate stroke
        m5_count = sum(1 for c in cmds if c.command == "M5")
        assert m5_count >= 4  # at least a few lines

    def test_lines_within_bounds(self):
        x, y, w, h = 50, 50, 80, 60
        cmds = expand_hatch(x, y, w, h, angle=0, spacing=5)
        for cmd in cmds:
            if cmd.x is not None:
                assert x - 0.1 <= cmd.x <= x + w + 0.1, f"X={cmd.x} outside [{x}, {x+w}]"
            if cmd.y is not None:
                assert y - 0.1 <= cmd.y <= y + h + 0.1, f"Y={cmd.y} outside [{y}, {y+h}]"

    def test_angled_hatch(self):
        cmds = expand_hatch(50, 50, 80, 60, angle=45, spacing=5)
        assert len(cmds) > 0


# ---------------------------------------------------------------------------
# TestExpandCrosshatch
# ---------------------------------------------------------------------------

class TestExpandCrosshatch:
    def test_two_passes(self):
        cmds_cross = expand_crosshatch(50, 50, 80, 60, spacing=10)
        cmds_single = expand_hatch(50, 50, 80, 60, angle=45, spacing=10)
        # Crosshatch should have roughly 2x the commands of a single hatch
        assert len(cmds_cross) > len(cmds_single)

    def test_has_commands(self):
        cmds = expand_crosshatch(50, 50, 80, 60, spacing=5)
        assert len(cmds) > 0


# ---------------------------------------------------------------------------
# TestExpandFilledPolygon
# ---------------------------------------------------------------------------

class TestExpandFilledPolygon:
    def test_has_outline_and_fill(self):
        pts = [[50, 50], [150, 50], [150, 150], [50, 150]]
        cmds = expand_filled_polygon(pts, spacing=10)
        # Should have outline strokes + fill strokes
        m5_count = sum(1 for c in cmds if c.command == "M5")
        assert m5_count >= 4  # at least outline (2 M5) + some fill lines

    def test_empty_for_few_points(self):
        assert expand_filled_polygon([[0, 0], [1, 1]]) == []


# ---------------------------------------------------------------------------
# TestExpandStipple
# ---------------------------------------------------------------------------

class TestExpandStipple:
    def test_produces_dots(self):
        cmds = expand_stipple(50, 50, 80, 60, density=0.5)
        assert len(cmds) > 0
        # Each dot is a short stroke with one G1
        g1_cmds = [c for c in cmds if c.command == "G1"]
        assert len(g1_cmds) > 0

    def test_higher_density_more_dots(self):
        sparse = expand_stipple(50, 50, 80, 60, density=0.2)
        dense = expand_stipple(50, 50, 80, 60, density=0.8)
        assert len(dense) > len(sparse)


# ---------------------------------------------------------------------------
# TestExpandSpiral
# ---------------------------------------------------------------------------

class TestExpandSpiral:
    def test_basic(self):
        cmds = expand_spiral(100, 100, r_start=0, r_end=50, turns=5)
        _assert_stroke_structure(cmds)

    def test_stays_in_radius(self):
        cx, cy, r_end = 100, 100, 50
        cmds = expand_spiral(cx, cy, r_start=0, r_end=r_end, turns=3, segments=50)
        for cmd in cmds:
            if cmd.command == "G1" and cmd.x is not None:
                dist = math.sqrt((cmd.x - cx) ** 2 + (cmd.y - cy) ** 2)
                assert dist <= r_end + 0.5, f"Spiral point at distance {dist:.2f} exceeds r_end={r_end}"

    def test_segment_count(self):
        cmds = expand_spiral(100, 100, r_start=0, r_end=50, turns=3, segments=50)
        g1_cmds = [c for c in cmds if c.command == "G1"]
        assert len(g1_cmds) == 50


# ---------------------------------------------------------------------------
# TestExpandFlowField
# ---------------------------------------------------------------------------

class TestExpandFlowField:
    def test_produces_strokes(self):
        cmds = expand_flow_field(50, 50, 200, 200, cols=5, rows=5)
        assert len(cmds) > 0
        # Each stroke is: M5 + G0 + M3 + G1 + M5 = 5 commands
        # 5x5 grid = 25 strokes = 125 commands
        assert len(cmds) == 125

    def test_stroke_count_matches_grid(self):
        cmds = expand_flow_field(0, 0, 100, 100, cols=3, rows=4)
        m5_count = sum(1 for c in cmds if c.command == "M5")
        # Each stroke has 2 M5 (start and end), 3x4=12 strokes
        assert m5_count == 24

    def test_strokes_within_reasonable_bounds(self):
        x, y, w, h = 50, 50, 200, 150
        cmds = expand_flow_field(x, y, w, h, cols=6, rows=6, stroke_length=10)
        for cmd in cmds:
            if cmd.x is not None:
                # Allow some overshoot from stroke endpoints and noise
                assert x - 20 <= cmd.x <= x + w + 20
            if cmd.y is not None:
                assert y - 20 <= cmd.y <= y + h + 20

    def test_angle_variation_changes_output(self):
        flat = expand_flow_field(0, 0, 100, 100, cols=5, rows=5, angle_variation=0)
        swirl = expand_flow_field(0, 0, 100, 100, cols=5, rows=5, angle_variation=180)
        # Same number of commands, but different positions
        assert len(flat) == len(swirl)
        # At least some G1 endpoints differ
        flat_g1 = [(c.x, c.y) for c in flat if c.command == "G1"]
        swirl_g1 = [(c.x, c.y) for c in swirl if c.command == "G1"]
        assert flat_g1 != swirl_g1

    def test_spacing_noise(self):
        grid = expand_flow_field(0, 0, 100, 100, cols=4, rows=4, spacing_noise=0)
        noisy = expand_flow_field(0, 0, 100, 100, cols=4, rows=4, spacing_noise=5)
        # Same count, different positions
        grid_g0 = [(c.x, c.y) for c in grid if c.command == "G0"]
        noisy_g0 = [(c.x, c.y) for c in noisy if c.command == "G0"]
        assert grid_g0 != noisy_g0

    def test_expand_via_registry(self):
        """flow_field works through expand_primitive dispatcher."""
        cmds = expand_primitive("flow_field", {
            "x": 0, "y": 0, "width": 100, "height": 100,
            "cols": 3, "rows": 3,
        }, PEN)
        assert len(cmds) > 0


# ---------------------------------------------------------------------------
# TestExpandPrimitives (integration)
# ---------------------------------------------------------------------------

class TestExpandPrimitives:
    def test_mixed_program(self):
        """DrawProgram with both GCode and primitives expands correctly."""
        prog = DrawProgram(commands=[
            GCodeCommand(command="M5"),
            PrimitiveCommand(type="circle", params={"cx": 100, "cy": 100, "radius": 30}),
            GCodeCommand(command="G0", x=0, y=0),
        ])
        result = expand_primitives(prog, PEN)
        assert isinstance(result, GCodeProgram)
        # First command is M5 (passthrough)
        assert result.commands[0].command == "M5"
        # Last command is G0 x=0 y=0 (passthrough)
        assert result.commands[-1].command == "G0"
        assert result.commands[-1].x == 0
        # Should have many more commands than input (circle expanded)
        assert len(result.commands) > 10

    def test_pure_gcode_passthrough(self):
        """A DrawProgram with no primitives passes through all commands."""
        prog = DrawProgram(commands=[
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=50, y=50, f=2000),
            GCodeCommand(command="M5"),
        ])
        result = expand_primitives(prog, PEN)
        assert len(result.commands) == 5

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown primitive type"):
            expand_primitive("nonexistent", {}, PEN)

    def test_metadata_preserved(self):
        prog = DrawProgram(
            commands=[PrimitiveCommand(type="circle", params={"cx": 50, "cy": 50, "radius": 20})],
            metadata={"source": "test"},
        )
        result = expand_primitives(prog, PEN)
        assert result.metadata["source"] == "test"
        assert result.metadata["primitives_expanded"] is True

    def test_pen_config_injected(self):
        """Feed and S value from PenConfig are used in expanded commands."""
        pen = PenConfig(feed_rate=3000, pen_down_s_value=500)
        prog = DrawProgram(commands=[
            PrimitiveCommand(type="circle", params={"cx": 50, "cy": 50, "radius": 20}),
        ])
        result = expand_primitives(prog, pen)
        g1_cmds = [c for c in result.commands if c.command == "G1"]
        assert all(c.f == 3000 for c in g1_cmds)
        m3_cmds = [c for c in result.commands if c.command == "M3"]
        assert all(c.s == 500 for c in m3_cmds)


# ---------------------------------------------------------------------------
# TestDrawProgramParsing
# ---------------------------------------------------------------------------

class TestDrawProgramParsing:
    def test_from_json_dict(self):
        data = {
            "commands": [
                {"command": "M5"},
                {"command": "PRIMITIVE", "type": "circle", "params": {"cx": 100, "cy": 100, "radius": 40}},
                {"command": "G0", "x": 0, "y": 0},
            ]
        }
        prog = DrawProgram(**data)
        assert len(prog.commands) == 3
        assert isinstance(prog.commands[0], GCodeCommand)
        assert isinstance(prog.commands[1], PrimitiveCommand)
        assert isinstance(prog.commands[2], GCodeCommand)
        assert prog.has_primitives()

    def test_pure_gcode_draw_program(self):
        data = {
            "commands": [
                {"command": "M5"},
                {"command": "G0", "x": 10, "y": 10},
            ]
        }
        prog = DrawProgram(**data)
        assert not prog.has_primitives()
        assert all(isinstance(c, GCodeCommand) for c in prog.commands)

    def test_invalid_primitive_type_raises(self):
        data = {
            "commands": [
                {"command": "PRIMITIVE", "type": "hexaflexagon", "params": {}},
            ]
        }
        with pytest.raises(Exception):
            DrawProgram(**data)

    def test_primitive_command_validation(self):
        # command must be "PRIMITIVE"
        with pytest.raises(Exception):
            PrimitiveCommand(command="GCODE", type="circle", params={})

    def test_roundtrip_json(self):
        """Ensure DrawProgram can be constructed from raw JSON like LLM output."""
        raw = json.dumps({
            "commands": [
                {"command": "M5"},
                {"command": "PRIMITIVE", "type": "hatch",
                 "params": {"x": 50, "y": 50, "width": 80, "height": 60, "angle": 45, "spacing": 4}},
                {"command": "PRIMITIVE", "type": "spiral",
                 "params": {"cx": 200, "cy": 150, "r_start": 0, "r_end": 40, "turns": 3}},
                {"command": "G0", "x": 0, "y": 0},
            ]
        })
        data = json.loads(raw)
        prog = DrawProgram(**data)
        assert prog.has_primitives()
        assert len(prog.commands) == 4

        # Expand and verify valid GCode
        result = expand_primitives(prog, PEN)
        assert isinstance(result, GCodeProgram)
        assert len(result.commands) > 10


# ---------------------------------------------------------------------------
# TestPrimitiveRegistry
# ---------------------------------------------------------------------------

class TestPrimitiveRegistry:
    def test_all_types_registered(self):
        assert set(PRIMITIVE_REGISTRY.keys()) == VALID_PRIMITIVE_TYPES

    def test_all_types_callable(self):
        for name, fn in PRIMITIVE_REGISTRY.items():
            assert callable(fn)


# ---------------------------------------------------------------------------
# TestPrimitiveSchemas
# ---------------------------------------------------------------------------

class TestPrimitiveSchemas:
    def test_all_primitives_have_schemas(self):
        schemas = get_all_primitive_schemas()
        assert set(schemas.keys()) == VALID_PRIMITIVE_TYPES

    def test_schema_has_required_fields(self):
        schema = get_primitive_schema("circle", expand_circle)
        assert "cx" in schema["params"]["required"]
        assert "cy" in schema["params"]["required"]
        assert "radius" in schema["params"]["required"]

    def test_schema_excludes_hidden_params(self):
        schema = get_primitive_schema("circle", expand_circle)
        props = schema["params"]["properties"]
        assert "feed" not in props
        assert "s_value" not in props

    def test_schema_includes_defaults(self):
        schema = get_primitive_schema("circle", expand_circle)
        assert schema["params"]["properties"]["segments"]["default"] == 24

    def test_schema_includes_descriptions(self):
        schema = get_primitive_schema("circle", expand_circle)
        assert "description" in schema["params"]["properties"]["cx"]

    def test_format_for_prompt_contains_all_types(self):
        block = format_schemas_for_prompt()
        for name in VALID_PRIMITIVE_TYPES:
            assert name in block

    def test_format_includes_example_json(self):
        block = format_schemas_for_prompt()
        assert '"command": "PRIMITIVE"' in block or '"command":"PRIMITIVE"' in block
