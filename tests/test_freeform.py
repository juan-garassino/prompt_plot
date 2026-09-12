"""Tests for structured freeform drawing expansion."""

from promptplot.config import PenConfig
from promptplot.models import DrawProgram, FreeformCommand, GCodeProgram
from promptplot.primitives import expand_primitives


class TestFreeformExpansion:
    def test_silhouette_outline_expands_to_gcode(self):
        program = DrawProgram(
            commands=[
                FreeformCommand(
                    type="silhouette_outline",
                    params={"points": [[10, 10], [30, 30], [50, 10]], "closed": False},
                )
            ]
        )
        expanded = expand_primitives(program, PenConfig())
        assert isinstance(expanded, GCodeProgram)
        assert any(cmd.command == "G1" for cmd in expanded.commands)
        assert expanded.metadata["primitive_mix"]["freeform_count"] == 1

    def test_texture_strokes_expand_to_multiple_marks(self):
        program = DrawProgram(
            commands=[
                FreeformCommand(
                    type="texture_strokes",
                    params={
                        "centers": [[20, 20], [25, 23], [30, 27]],
                        "stroke_length": 5,
                        "angle": 40,
                    },
                )
            ]
        )
        expanded = expand_primitives(program, PenConfig())
        draw_cmds = [cmd for cmd in expanded.commands if cmd.command == "G1"]
        assert len(draw_cmds) >= 3

    def test_abstract_field_stack_expands(self):
        program = DrawProgram(
            commands=[
                FreeformCommand(
                    type="field_stack",
                    params={"x": 20, "y": 20, "width": 80, "height": 60, "layers": 2},
                )
            ]
        )
        expanded = expand_primitives(program, PenConfig())
        assert any(cmd.command == "G1" for cmd in expanded.commands)

    def test_figurative_shading_region_expands(self):
        program = DrawProgram(
            commands=[
                FreeformCommand(
                    type="shading_region",
                    params={"x": 30, "y": 30, "width": 60, "height": 40, "spacing": 6},
                )
            ]
        )
        expanded = expand_primitives(program, PenConfig())
        assert any(cmd.command == "G1" for cmd in expanded.commands)
