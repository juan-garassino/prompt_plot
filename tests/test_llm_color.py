"""LLM color assignment: palette prompt block + primitive color propagation."""

from promptplot.config import PaperConfig, PenConfig, PromptPlotConfig
from promptplot.llm import build_gcode_prompt
from promptplot.models import DrawProgram
from promptplot.primitives import expand_primitives
from promptplot.orchestrate import merge_chunks, split_color_layers


def test_prompt_has_no_color_block_by_default():
    p = build_gcode_prompt("a cat", PaperConfig(), PenConfig())
    assert "COLOR LAYERS" not in p


def test_prompt_injects_palette_block():
    p = build_gcode_prompt("a house", PaperConfig(), PenConfig(), palette=["black", "red", "green"])
    assert "COLOR LAYERS" in p
    assert "0=black" in p and "1=red" in p and "2=green" in p
    assert '"color"' in p


def test_primitive_color_propagates_to_expanded_commands():
    dp = DrawProgram(
        commands=[
            {
                "command": "PRIMITIVE",
                "type": "circle",
                "color": 1,
                "params": {"cx": 50, "cy": 50, "radius": 20},
            },
            {
                "command": "FREEFORM",
                "type": "hatch_region",
                "color": 2,
                "params": {"x": 10, "y": 10, "width": 40, "height": 40},
            },
        ]
    )
    gp = expand_primitives(dp, PenConfig())
    colors = {c.color for c in gp.commands if c.command == "G1"}
    assert colors == {1, 2}


def test_llm_style_color_program_splits_into_layers():
    cfg = PromptPlotConfig()
    cfg.paper = PaperConfig.from_size("a5")
    cfg.color.enabled = True
    cfg.color.palette = ["black", "red", "blue"]
    dp = DrawProgram(
        commands=[
            {
                "command": "PRIMITIVE",
                "type": "circle",
                "color": 0,
                "params": {"cx": 40, "cy": 40, "radius": 15},
            },
            {
                "command": "PRIMITIVE",
                "type": "circle",
                "color": 1,
                "params": {"cx": 80, "cy": 80, "radius": 15},
            },
            {
                "command": "PRIMITIVE",
                "type": "circle",
                "color": 2,
                "params": {"cx": 60, "cy": 120, "radius": 15},
            },
        ]
    )
    gp = expand_primitives(dp, cfg.pen)
    prog = merge_chunks([list(gp.commands)], cfg)
    layers = split_color_layers(prog)
    assert len({c for c, _ in layers}) == 3
