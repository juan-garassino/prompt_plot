"""
LlamaIndex Workflows for PromptPlot v3.0

LLM-driven GCode generation workflows:
- BatchGCodeWorkflow: full program in one LLM call -> validate -> postprocess -> return
- StreamingGCodeWorkflow: one command at a time -> validate -> send to plotter
"""

import json
import tempfile
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
from datetime import datetime

from llama_index.core.workflow import (
    Event, StartEvent, StopEvent, Workflow, step, Context,
)
from pydantic import ValidationError as PydanticValidationError

from .models import GCodeCommand, GCodeProgram, WorkflowResult
from .config import get_config, PromptPlotConfig
from .llm import (
    LLMProvider, get_llm_provider,
    build_gcode_prompt, build_reflection_prompt, build_next_command_prompt,
    GCODE_PROGRAM_TEMPLATE, REFLECTION_PROMPT,
)
from .postprocess import run_pipeline
from .scoring import score_gcode, QualityReport
from .memory import DrawingMemory
from .logger import WorkflowLogger

from rich.console import Console

console = Console()
logger = WorkflowLogger(console)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class GenerateGCodeEvent(Event):
    prompt: str

class GCodeExtractionDone(Event):
    output: str
    prompt: str

class GCodeValidationErrorEvent(Event):
    error: str
    issues: str
    prompt: str

class ValidatedGCodeEvent(Event):
    program: GCodeProgram
    gcode_text: str
    prompt: str

class RefinementEvent(Event):
    program: GCodeProgram
    prompt: str
    iteration: int


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clean_llm_output(output: str) -> str:
    output = output.strip()
    if "```json" in output:
        start = output.find("```json") + 7
        end = output.rfind("```")
        output = output[start:end].strip()
    elif "```" in output:
        start = output.find("```") + 3
        end = output.rfind("```")
        output = output[start:end].strip()
    return output


def _extract_json(output: str) -> str:
    start = output.find("{")
    end = output.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("No valid JSON object found in output")
    return output[start:end]


def _validate_output(output: str):
    """Returns GCodeProgram or GCodeCommand on success, Exception on failure."""
    cleaned = _clean_llm_output(output)
    json_str = _extract_json(cleaned)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return ValueError(f"Invalid JSON: {e}")

    if "commands" in data:
        try:
            return GCodeProgram(**data)
        except PydanticValidationError as e:
            return ValueError(f"Program validation failed: {e}")
    else:
        try:
            return GCodeCommand(**data)
        except PydanticValidationError as e:
            return ValueError(f"Command validation failed: {e}")


def _check_bounds(program: GCodeProgram, config: PromptPlotConfig) -> Optional[str]:
    """Check if any commands exceed paper bounds. Returns error message or None."""
    if not config.bounds.enforce:
        return None
    x0, y0, x1, y1 = config.paper.get_drawable_area()
    violations = []
    for i, cmd in enumerate(program.commands):
        if cmd.x is not None and (cmd.x < 0 or cmd.x > config.paper.width):
            violations.append(f"Command {i}: X={cmd.x} outside [0, {config.paper.width}]")
        if cmd.y is not None and (cmd.y < 0 or cmd.y > config.paper.height):
            violations.append(f"Command {i}: Y={cmd.y} outside [0, {config.paper.height}]")
    if violations:
        return (
            f"Out-of-bounds coordinates detected. Valid X: [0, {config.paper.width}], "
            f"Valid Y: [0, {config.paper.height}]. Drawable area: X[{x0}-{x1}], Y[{y0}-{y1}]. "
            f"Violations: {'; '.join(violations[:5])}"
        )
    return None


# ---------------------------------------------------------------------------
# BatchGCodeWorkflow
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Diagnostic retry (Phase 3)
# ---------------------------------------------------------------------------

def diagnose_failure(program: Optional[GCodeProgram], config: PromptPlotConfig,
                     error: Optional[str] = None) -> str:
    """Generate a targeted diagnosis message for failed GCode generation."""
    hints = []

    if error:
        hints.append(f"Previous error: {error}")

    if program is not None:
        n = len(program.commands)
        if n < 10:
            hints.append(f"Generate at least 30 GCode commands. Your previous attempt had only {n}.")

        drawing = [c for c in program.commands if c.command == "G1"]
        if not drawing:
            hints.append("Your output must contain G1 drawing commands, not just travel moves.")

        # Check bounds
        x0, y0, x1, y1 = config.paper.get_drawable_area()
        oob = []
        for cmd in program.commands:
            if cmd.x is not None and (cmd.x < 0 or cmd.x > config.paper.width):
                oob.append(f"X={cmd.x:.1f}")
            if cmd.y is not None and (cmd.y < 0 or cmd.y > config.paper.height):
                oob.append(f"Y={cmd.y:.1f}")
        if oob:
            hints.append(
                f"Keep all coordinates within X:{x0:.1f}-{x1:.1f}, Y:{y0:.1f}-{y1:.1f}. "
                f"Out-of-range values: {', '.join(oob[:5])}"
            )

        # Check pen lifts
        has_m5 = any(c.command == "M5" for c in program.commands)
        has_m3 = any(c.command == "M3" for c in program.commands)
        if not has_m5 or not has_m3:
            s_val = config.pen.pen_down_s_value
            hints.append(
                f"Add M5 (pen up) before G0 travel moves and M3 S{s_val} "
                f"(pen down) before G1 draw moves."
            )

        # Check utilization
        try:
            report = score_gcode(program, config.paper)
            if report.canvas_utilization < 0.2:
                pct = int(report.canvas_utilization * 100)
                hints.append(
                    f"Use more of the canvas. Your drawing only covers {pct}% — aim for 60-80%."
                )
        except Exception:
            pass

    if not hints:
        hints.append("Review the error and try again with valid GCode.")

    return "\n".join(f"- {h}" for h in hints)


class BatchGCodeWorkflow(Workflow):
    """Generate a full GCode program in one LLM call, validate, post-process."""

    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm: Optional[LLMProvider] = None,
                 config: Optional[PromptPlotConfig] = None,
                 max_retries: int = 3, style: str = "artistic",
                 style_profile: Optional[Any] = None, **kwargs):
        kwargs.setdefault("timeout", 10000)
        super().__init__(**kwargs)
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.max_retries = max_retries
        self.style = style
        self.style_profile = style_profile
        self.memory = DrawingMemory()

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> GenerateGCodeEvent:
        prompt = getattr(ev, "prompt", "draw a simple square")
        logger.workflow_start("G-Code Generation Workflow", prompt)
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("prompt", prompt)
        logger.step_start("Initialize Workflow")
        logger.step_info("Configuration loaded", {
            "Max retries": self.max_retries,
            "Prompt": prompt,
        })
        return GenerateGCodeEvent(prompt=prompt)

    @step
    async def generate_gcode(self, ctx: Context,
                              ev: Union[GenerateGCodeEvent, GCodeValidationErrorEvent]
                              ) -> GCodeExtractionDone:
        logger.step_start("G-Code Generation")
        task_key = "gcode_retries"
        retries = await ctx.get(task_key, default=0)
        max_r = await ctx.get("max_retries")

        if retries >= max_r:
            logger.step_error("Max retries exceeded")
            fallback = json.dumps({"commands": [
                {"command": "M5"}, {"command": "G0", "x": 0, "y": 0}
            ]})
            return GCodeExtractionDone(output=fallback, prompt=ev.prompt)

        await ctx.set(task_key, retries + 1)

        if isinstance(ev, GCodeValidationErrorEvent):
            logger.retry_attempt(retries, max_r, "Validation failed")
            # Use diagnostic retry instead of generic reflection
            diag_program = None
            try:
                diag_result = _validate_output(ev.issues)
                if isinstance(diag_result, GCodeProgram):
                    diag_program = diag_result
            except Exception:
                pass
            diagnosis = diagnose_failure(diag_program, self.config, ev.error)
            prompt = build_reflection_prompt(ev.issues, ev.error, self.config.paper)
            prompt += f"\n\nSPECIFIC ISSUES:\n{diagnosis}\n"
        else:
            # Use multimodal if reference image is provided
            if (self.config.vision.enabled and self.config.vision.reference_image):
                prompt = build_gcode_prompt(
                    ev.prompt, self.config.paper, self.config.pen, self.style
                )
                prompt += "\n\nA reference image is attached. Match its composition and style using pen strokes."
                image_paths = [Path(self.config.vision.reference_image)]
                logger.llm_call(type(self.llm).__name__, "", ev.prompt[:50])
                response = await self.llm.acomplete_multimodal(prompt, image_paths)
                logger.step_success("LLM response received (multimodal)")
                return GCodeExtractionDone(output=response, prompt=ev.prompt)
            else:
                # Check memory for similar past drawing
                memory_entry = None
                try:
                    similar = self.memory.find_similar(ev.prompt, top_k=1)
                    if similar:
                        memory_entry = similar[0]
                except Exception:
                    pass

                prompt = build_gcode_prompt(
                    ev.prompt, self.config.paper, self.config.pen, self.style,
                    style_profile=self.style_profile,
                    memory_entry=memory_entry,
                )

        logger.llm_call(type(self.llm).__name__, "", ev.prompt[:50])
        response = await self.llm.acomplete(prompt)
        logger.step_success("LLM response received")
        return GCodeExtractionDone(output=response, prompt=ev.prompt)

    @step
    async def validate_gcode(self, ctx: Context,
                              ev: GCodeExtractionDone
                              ) -> Union[GCodeValidationErrorEvent, ValidatedGCodeEvent,
                                         RefinementEvent]:
        logger.step_start("G-Code Validation")
        result = _validate_output(ev.output)

        if isinstance(result, Exception):
            error_msg = str(result)
            logger.validation_result(False, 0, [error_msg])
            return GCodeValidationErrorEvent(error=error_msg, issues=ev.output, prompt=ev.prompt)

        program = result

        # Check bounds
        bounds_error = _check_bounds(program, self.config)
        if bounds_error:
            logger.validation_result(False, len(program.commands), [bounds_error])
            return GCodeValidationErrorEvent(
                error=bounds_error, issues=ev.output, prompt=ev.prompt
            )

        logger.validation_result(True, len(program.commands))

        # If vision preview feedback is enabled, route to refinement
        if (self.config.vision.enabled and self.config.vision.preview_feedback
                and self.config.vision.max_feedback_iterations > 0):
            return RefinementEvent(program=program, prompt=ev.prompt, iteration=0)

        return ValidatedGCodeEvent(
            program=program, gcode_text=program.to_gcode(), prompt=ev.prompt
        )

    @step
    async def refine_with_preview(self, ctx: Context,
                                   ev: RefinementEvent
                                   ) -> Union[RefinementEvent, ValidatedGCodeEvent]:
        """Render preview, feed back to LLM for refinement."""
        logger.step_start(f"Vision Refinement (iteration {ev.iteration + 1})")

        max_iter = self.config.vision.max_feedback_iterations
        if ev.iteration >= max_iter:
            return ValidatedGCodeEvent(
                program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
            )

        try:
            from .visualizer import GCodeVisualizer
            viz = GCodeVisualizer(self.config)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preview_path = tmp.name
            viz.preview(ev.program, preview_path)

            refinement_prompt = (
                f"Here is a preview of your drawing. The original request was: '{ev.prompt}'. "
                f"Improve the drawing: add more detail, fix proportions, use more of the canvas "
                f"({self.config.paper.get_drawable_dimensions()[0]:.0f}mm x "
                f"{self.config.paper.get_drawable_dimensions()[1]:.0f}mm). "
                f"Return the complete improved GCode as a JSON with 'commands' list."
            )

            response = await self.llm.acomplete_multimodal(
                refinement_prompt, [Path(preview_path)]
            )

            result = _validate_output(response)
            if isinstance(result, Exception) or not isinstance(result, GCodeProgram):
                logger.step_warning("Refinement produced invalid output, keeping original")
                return ValidatedGCodeEvent(
                    program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
                )

            # Accept if the refined version has more commands (more detail)
            if len(result.commands) >= len(ev.program.commands):
                logger.step_success(f"Refinement improved: {len(ev.program.commands)} -> {len(result.commands)} commands")
                return RefinementEvent(
                    program=result, prompt=ev.prompt, iteration=ev.iteration + 1
                )
            else:
                return ValidatedGCodeEvent(
                    program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
                )
        except ImportError:
            logger.step_warning("matplotlib not available for preview feedback")
            return ValidatedGCodeEvent(
                program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
            )

    @step
    async def end(self, ctx: Context, ev: ValidatedGCodeEvent) -> StopEvent:
        logger.step_start("Post-Processing")

        # Multi-pass generation
        program = ev.program
        if self.config.workflow.multipass.enabled:
            try:
                logger.step_info("Multi-pass: generating detail pass")
                outline_gcode = program.to_gcode()
                detail_prompt = build_gcode_prompt(
                    ev.prompt, self.config.paper, self.config.pen,
                    self.config.workflow.multipass.detail_style,
                    style_profile=self.style_profile,
                )
                detail_prompt += (
                    f"\n\nAn outline has already been drawn:\n{outline_gcode[:500]}\n\n"
                    "Add detail, texture, and fill to complement this outline. "
                    "Do NOT redraw the outline. Return complete JSON with 'commands' list."
                )
                response = await self.llm.acomplete(detail_prompt)
                detail_result = _validate_output(response)
                if isinstance(detail_result, GCodeProgram):
                    # Merge: outline + detail
                    merged_cmds = list(program.commands[:-1])  # drop final M5/G0
                    merged_cmds.extend(detail_result.commands)
                    program = GCodeProgram(
                        commands=merged_cmds,
                        metadata={**(program.metadata or {}), "multipass": True},
                    )
                    logger.step_success(f"Multi-pass merged: {len(program.commands)} commands")
            except Exception as e:
                logger.step_warning(f"Multi-pass detail failed, using outline only: {e}")

        optimized = run_pipeline(program, self.config)
        gcode_text = optimized.to_gcode()
        gcode_lines = gcode_text.split("\n")

        logger.step_success("Post-processing complete", {
            "Original commands": len(ev.program.commands),
            "Final commands": len(optimized.commands),
        })
        logger.workflow_complete(True, len(optimized.commands), gcode_lines)

        # Save to memory if grade is A or B
        try:
            report = score_gcode(optimized, self.config.paper)
            if report.grade in ("A", "B"):
                self.memory.save(
                    prompt=ev.prompt,
                    gcode=gcode_text,
                    grade=report.grade,
                    canvas_utilization=report.canvas_utilization,
                    draw_travel_ratio=report.draw_travel_ratio,
                    command_count=report.command_count,
                )
                logger.step_info(f"Drawing saved to memory (grade {report.grade})")
        except Exception:
            pass

        return StopEvent(result={
            "prompt": ev.prompt,
            "commands_count": len(optimized.commands),
            "gcode": gcode_text,
            "program": optimized.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


# ---------------------------------------------------------------------------
# StreamingGCodeWorkflow
# ---------------------------------------------------------------------------

class StreamingGCodeWorkflow(Workflow):
    """Generate GCode one command at a time and optionally stream to plotter."""

    def __init__(self, llm: Optional[LLMProvider] = None,
                 config: Optional[PromptPlotConfig] = None,
                 max_steps: int = 50, **kwargs):
        kwargs.setdefault("timeout", 10000)
        super().__init__(**kwargs)
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.max_steps = max_steps

    async def generate_gcode(self, prompt: str) -> WorkflowResult:
        """Run streaming generation (not using LlamaIndex events for simplicity)."""
        commands: List[GCodeCommand] = []
        logger.stream_start("Streaming G-Code Generation", prompt, self.max_steps)

        for step_num in range(self.max_steps):
            history = "\n".join(
                f"Step {i+1}: {c.to_gcode()}" for i, c in enumerate(commands)
            ) if commands else "No previous commands"

            llm_prompt = build_next_command_prompt(
                prompt, history, self.config.paper, self.config.pen
            )
            response = await self.llm.acomplete(llm_prompt)
            result = _validate_output(response)

            if isinstance(result, Exception):
                logger.stream_command(step_num + 1, f"ERROR: {result}", "error")
                continue

            if isinstance(result, GCodeCommand):
                if result.command == "COMPLETE":
                    logger.stream_command(step_num + 1, "COMPLETE", "success")
                    break
                commands.append(result)
                logger.stream_command(step_num + 1, result.to_gcode(), "success")

        if not commands:
            return WorkflowResult(
                success=False, prompt=prompt, commands_count=0, gcode="",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message="No commands generated",
            )

        program = GCodeProgram(commands=commands)
        optimized = run_pipeline(program, self.config)

        return WorkflowResult(
            success=True, prompt=prompt,
            commands_count=len(optimized.commands),
            gcode=optimized.to_gcode(),
            program=optimized,
            step_count=len(commands),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
