"""
File-based async pipeline for PromptPlot v3.0

Adapted from drawStream async_foreman.py. Loads a .gcode file,
runs it through the shared post-processing pipeline, optionally
previews, then streams to plotter.
"""

from pathlib import Path
from typing import Optional, Tuple

from .models import GCodeCommand, GCodeProgram
from .config import PromptPlotConfig, get_config
from .postprocess import run_pipeline
from .plotter import BasePlotter, SimulatedPlotter
from .logger import WorkflowLogger

from rich.console import Console

console = Console()
logger = WorkflowLogger(console)


class FilePipeline:
    """Load a GCode file -> postprocess -> preview -> stream to plotter."""

    def __init__(self, config: Optional[PromptPlotConfig] = None):
        self.config = config or get_config()

    def load_gcode_file(self, filepath: str) -> GCodeProgram:
        """Parse a .gcode/.nc file into a GCodeProgram."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"GCode file not found: {filepath}")

        commands = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                try:
                    cmd = GCodeCommand.from_string(line)
                    commands.append(cmd)
                except Exception:
                    continue

        if not commands:
            raise ValueError(f"No valid GCode commands found in {filepath}")

        return GCodeProgram(
            commands=commands,
            metadata={"source_file": str(path), "original_count": len(commands)},
        )

    async def process_file(
        self,
        filepath: str,
        plotter: Optional[BasePlotter] = None,
        preview_only: bool = False,
        output_path: Optional[str] = None,
    ) -> Tuple[GCodeProgram, int, int]:
        """Full pipeline: load -> postprocess -> preview -> stream.

        Returns:
            (processed_program, success_count, error_count)
        """
        logger.pipeline_step(1, 4, "Load GCode file")
        program = self.load_gcode_file(filepath)
        logger.step_success(f"Loaded {len(program.commands)} commands from {filepath}")

        logger.pipeline_step(2, 4, "Post-processing")
        processed = run_pipeline(program, self.config)
        logger.step_success("Post-processing complete", {
            "Original": len(program.commands),
            "Processed": len(processed.commands),
        })

        logger.pipeline_step(3, 4, "Preview")
        try:
            from .visualizer import GCodeVisualizer
            viz = GCodeVisualizer(self.config)
            if output_path:
                save_to = output_path
            else:
                out_dir = Path(self.config.workflow.output_directory)
                out_dir.mkdir(parents=True, exist_ok=True)
                save_to = str(out_dir / f"preview_{Path(filepath).stem}.png")
            viz.preview(processed, save_to)
            logger.step_success(f"Preview saved to {save_to}")
        except ImportError:
            logger.step_warning("Visualizer not available (matplotlib missing)")

        if preview_only:
            logger.step_info("Preview-only mode, skipping plotter")
            return processed, 0, 0

        logger.pipeline_step(4, 4, "Stream to plotter")
        if plotter is None:
            plotter = SimulatedPlotter()

        async with plotter:
            success, errors = await plotter.stream_program(processed)

        logger.execution_summary(
            success + errors, success, errors,
            0.0,  # elapsed not tracked here
        )

        return processed, success, errors

    async def process_and_save(
        self,
        filepath: str,
        output_filepath: str,
    ) -> GCodeProgram:
        """Load, postprocess, and save to a new file (no plotter)."""
        program = self.load_gcode_file(filepath)
        processed = run_pipeline(program, self.config)

        with open(output_filepath, "w") as f:
            f.write(processed.to_gcode())

        logger.step_success(f"Processed GCode saved to {output_filepath}", {
            "Original": len(program.commands),
            "Processed": len(processed.commands),
        })
        return processed
