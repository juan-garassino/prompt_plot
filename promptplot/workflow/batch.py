"""BatchGCodeWorkflow — full program in one LLM call → validate → postprocess.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

import json
from pathlib import Path
from typing import Union, Optional, List, Any
from datetime import datetime


from ..engine import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
    DrawingSession,
    Phase,
)
from ..models import (
    GCodeProgram,
    CompositionPlan,
    FigurativeCompositionPlan,
    AbstractCompositionPlan,
    DrawProgram,
)
from ..config import get_config, PromptPlotConfig
from ..llm import (
    LLMProvider,
    get_llm_provider,
    build_gcode_prompt,
    build_reflection_prompt,
    build_composition_plan_prompt,
    build_preview_reflection_prompt,
    estimate_complexity,
    classify_creative_mode,
)
from ..postprocess import run_pipeline
from ..scoring import score_gcode
from ..memory import DrawingMemory

from ._shared import (
    logger,
    _clean_llm_output,
    _extract_json,
    _validate_output,
    _check_bounds,
    _supports_multimodal,
    _analysis_output_dir,
    _select_candidate_report,
    diagnose_failure,
)
from .events import (
    GenerateGCodeEvent,
    GCodeExtractionDone,
    GCodeValidationErrorEvent,
    ValidatedGCodeEvent,
    RefinementEvent,
    PlanEvent,
)


# ===== sliced body (BatchGCodeWorkflow) =====
class BatchGCodeWorkflow(Workflow):
    """Generate a full GCode program in one LLM call, validate, post-process."""

    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        config: Optional[PromptPlotConfig] = None,
        max_retries: int = 3,
        style: str = "artistic",
        style_profile: Optional[Any] = None,
        session: Optional[DrawingSession] = None,
        **kwargs,
    ):
        kwargs.setdefault("timeout", 10000)
        super().__init__(**kwargs)
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.max_retries = max_retries
        self.style = style
        self.style_profile = style_profile
        self.memory = DrawingMemory()
        self.session = session

    @step
    async def start(self, ctx: Context, ev: StartEvent) -> Union[GenerateGCodeEvent, PlanEvent]:
        prompt = getattr(ev, "prompt", "draw a simple square")
        logger.workflow_start("G-Code Generation Workflow", prompt)
        await ctx.set("max_retries", self.max_retries)
        await ctx.set("prompt", prompt)
        logger.step_start("Initialize Workflow")
        creative_mode = self.config.workflow.creative_mode
        if creative_mode == "auto":
            creative_mode = classify_creative_mode(prompt)
        await ctx.set("creative_mode", creative_mode)

        # Auto-enable multipass for complex prompts to get denser output
        complexity = estimate_complexity(prompt)
        if complexity in ("moderate", "complex") and not self.config.workflow.multipass.enabled:
            self.config.workflow.multipass.enabled = True
            logger.step_info("Auto-enabled multi-pass for complex prompt")
        if complexity in ("moderate", "complex") and not self.config.workflow.planning_enabled:
            self.config.workflow.planning_enabled = True
            logger.step_info("Auto-enabled composition planning")

        logger.step_info(
            "Configuration loaded",
            {
                "Max retries": self.max_retries,
                "Prompt": prompt,
                "Complexity": complexity,
                "Multi-pass": self.config.workflow.multipass.enabled,
                "Creative mode": creative_mode,
                "Candidate count": self.config.workflow.candidate_count,
            },
        )
        if self.session:
            self.session.prompt = prompt

        if self.config.workflow.planning_enabled:
            if self.session:
                self.session.set_phase(Phase.PLANNING)
            return PlanEvent(prompt=prompt, creative_mode=creative_mode)

        if self.session:
            self.session.set_phase(Phase.GENERATING)
        return GenerateGCodeEvent(prompt=prompt)

    @step
    async def plan_composition(self, ctx: Context, ev: PlanEvent) -> GenerateGCodeEvent:
        """LLM-driven composition planning step."""
        logger.step_start("Composition Planning")
        try:
            candidate_count = max(
                1, self.config.workflow.candidate_count if _supports_multimodal(self.llm) else 1
            )
            plans: List[Any] = []
            for idx in range(candidate_count):
                plan_prompt = build_composition_plan_prompt(
                    ev.prompt,
                    self.config.paper,
                    self.style,
                    creative_mode=ev.creative_mode,
                    candidate_index=idx,
                )
                response = await self.llm.acomplete(plan_prompt)
                cleaned = _clean_llm_output(response)
                json_str = _extract_json(cleaned)
                import json as _json

                plan_data = _json.loads(json_str)
                if ev.creative_mode == "abstract":
                    plan = AbstractCompositionPlan(**plan_data)
                else:
                    # Hybrid reuses the figurative region plan for now
                    try:
                        plan = FigurativeCompositionPlan(**plan_data)
                    except Exception:
                        plan = CompositionPlan(**plan_data)
                plans.append(plan)

            await ctx.set("composition_plan_candidates", plans)
            await ctx.set("composition_plan", plans[0] if plans else None)
            logger.step_success(f"Composition plans: {len(plans)} candidates")
        except Exception as e:
            logger.step_warning(f"Planning failed, proceeding without plan: {e}")

        if self.session:
            self.session.set_phase(Phase.GENERATING)
        return GenerateGCodeEvent(prompt=ev.prompt)

    @step
    async def generate_gcode(
        self, ctx: Context, ev: Union[GenerateGCodeEvent, GCodeValidationErrorEvent]
    ) -> GCodeExtractionDone:
        logger.step_start("G-Code Generation")
        task_key = "gcode_retries"
        retries = await ctx.get(task_key, default=0)
        max_r = await ctx.get("max_retries")

        if retries >= max_r:
            logger.step_error("Max retries exceeded")
            fallback = json.dumps(
                {"commands": [{"command": "M5"}, {"command": "G0", "x": 0, "y": 0}]}
            )
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
            creative_mode = await ctx.get("creative_mode", default="figurative")
            # Use multimodal if reference image is provided
            if self.config.vision.enabled and self.config.vision.reference_image:
                prompt = build_gcode_prompt(
                    ev.prompt,
                    self.config.paper,
                    self.config.pen,
                    self.style,
                    creative_mode=creative_mode,
                    palette=(self.config.color.palette if self.config.color.enabled else None),
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
                    similar = self.memory.find_similar(
                        ev.prompt, top_k=1, creative_mode=creative_mode
                    )
                    if similar:
                        memory_entry = similar[0]
                except Exception:
                    pass

                prompt = build_gcode_prompt(
                    ev.prompt,
                    self.config.paper,
                    self.config.pen,
                    self.style,
                    style_profile=self.style_profile,
                    memory_entry=memory_entry,
                    creative_mode=creative_mode,
                    palette=(self.config.color.palette if self.config.color.enabled else None),
                )

        # Inject composition plan guidance if available
        composition_plan = await ctx.get("composition_plan")
        composition_plan_candidates = await ctx.get("composition_plan_candidates", default=[])
        creative_mode = await ctx.get("creative_mode", default="figurative")
        candidate_count = max(
            1, self.config.workflow.candidate_count if _supports_multimodal(self.llm) else 1
        )
        best_response = None
        best_tuple = None
        best_plan = composition_plan

        candidate_plans = composition_plan_candidates or [composition_plan]
        candidate_plans = candidate_plans[:candidate_count] if candidate_plans else [None]

        for idx in range(max(candidate_count, len(candidate_plans))):
            candidate_prompt = prompt
            plan_for_candidate = (
                candidate_plans[min(idx, len(candidate_plans) - 1)] if candidate_plans else None
            )
            if plan_for_candidate is not None:
                candidate_prompt += f"\n\n{plan_for_candidate.to_prompt_guidance()}\n"
            if idx > 0:
                candidate_prompt += (
                    f"\n\nCANDIDATE EXPLORATION {idx + 1}: vary focal placement, density, "
                    "and support regions while preserving the prompt intent.\n"
                )

            logger.llm_call(type(self.llm).__name__, "", ev.prompt[:50])
            response = await self.llm.acomplete(candidate_prompt)
            result = _validate_output(response)
            if isinstance(result, DrawProgram):
                from ..primitives import expand_primitives

                result = expand_primitives(result, self.config.pen)
            if isinstance(result, Exception) or not isinstance(result, GCodeProgram):
                continue
            report = score_gcode(result, self.config.paper, creative_mode=creative_mode)
            score_tuple = _select_candidate_report(report, creative_mode)
            if best_tuple is None or score_tuple > best_tuple:
                best_tuple = score_tuple
                best_response = response
                best_plan = plan_for_candidate

        if best_plan is not None:
            await ctx.set("composition_plan", best_plan)
        if best_response is None:
            logger.step_warning(
                "Candidate search found no valid outputs; falling back to single attempt"
            )
            logger.llm_call(type(self.llm).__name__, "", ev.prompt[:50])
            best_response = await self.llm.acomplete(prompt)
        logger.step_success("LLM response received")
        return GCodeExtractionDone(output=best_response, prompt=ev.prompt)

    @step
    async def validate_gcode(
        self, ctx: Context, ev: GCodeExtractionDone
    ) -> Union[GCodeValidationErrorEvent, ValidatedGCodeEvent, RefinementEvent]:
        logger.step_start("G-Code Validation")
        result = _validate_output(ev.output)

        if isinstance(result, Exception):
            error_msg = str(result)
            logger.validation_result(False, 0, [error_msg])
            return GCodeValidationErrorEvent(error=error_msg, issues=ev.output, prompt=ev.prompt)

        # Expand primitives if present
        if isinstance(result, DrawProgram):
            try:
                from ..primitives import expand_primitives

                result = expand_primitives(result, self.config.pen)
                logger.step_info(f"Expanded primitives → {len(result.commands)} GCode commands")
            except Exception as e:
                error_msg = f"Primitive expansion failed: {e}"
                logger.validation_result(False, 0, [error_msg])
                return GCodeValidationErrorEvent(
                    error=error_msg, issues=ev.output, prompt=ev.prompt
                )

        program = result

        # Check bounds
        bounds_error = _check_bounds(program, self.config)
        if bounds_error:
            logger.validation_result(False, len(program.commands), [bounds_error])
            return GCodeValidationErrorEvent(error=bounds_error, issues=ev.output, prompt=ev.prompt)

        logger.validation_result(True, len(program.commands))
        creative_mode = await ctx.get("creative_mode", default="figurative")
        program.metadata = {**(program.metadata or {}), "creative_mode": creative_mode}

        # If vision preview feedback is enabled, route to refinement
        if (
            self.config.vision.preview_feedback
            and self.config.vision.max_feedback_iterations > 0
            and _supports_multimodal(self.llm)
        ):
            return RefinementEvent(program=program, prompt=ev.prompt, iteration=0)

        return ValidatedGCodeEvent(program=program, gcode_text=program.to_gcode(), prompt=ev.prompt)

    @step
    async def refine_with_preview(
        self, ctx: Context, ev: RefinementEvent
    ) -> Union[RefinementEvent, ValidatedGCodeEvent]:
        """Render preview, feed back to LLM for refinement."""
        logger.step_start(f"Vision Refinement (iteration {ev.iteration + 1})")

        max_iter = self.config.vision.max_feedback_iterations
        if ev.iteration >= max_iter:
            return ValidatedGCodeEvent(
                program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
            )

        try:
            from ..visualizer import GCodeVisualizer

            viz = GCodeVisualizer(self.config)
            active_plan = await ctx.get("composition_plan")
            creative_mode = ev.program.metadata.get("creative_mode", "figurative")
            artifact_dir = _analysis_output_dir(self.config, ev.prompt, ev.iteration)
            artifacts = viz.save_analysis_artifacts(
                ev.program,
                str(artifact_dir),
                creative_mode=creative_mode,
                plan=active_plan,
                prefix="preview_analysis",
            )
            await ctx.set("last_analysis_artifacts", artifacts)
            preview_path = artifacts["preview_path"]
            analysis = artifacts["analysis"]
            baseline_report = score_gcode(
                ev.program, self.config.paper, creative_mode=creative_mode
            )
            if baseline_report.grade in ("A", "B") and not baseline_report.failure_reasons:
                return ValidatedGCodeEvent(
                    program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
                )

            critique = {
                "dominant_issue": baseline_report.dominant_issue,
                "silhouette_clarity": baseline_report.structure_score,
                "canvas_balance": baseline_report.composition_score,
                "density_variation": baseline_report.texture_score,
                "geometry_strength": 1.0 - baseline_report.central_clustering_penalty,
                "freeform_quality": baseline_report.texture_score,
                "failure_reasons": baseline_report.failure_reasons,
                "creative_mode": creative_mode,
                "readability_score": baseline_report.readability_score,
                "focal_balance_score": baseline_report.focal_balance_score,
                "weak_regions": analysis.get("weak_regions", []),
                "region_analysis": analysis.get("global", {}),
            }

            if _supports_multimodal(self.llm):
                critique_prompt = (
                    f"Critique this pen-plot preview for the prompt '{ev.prompt}'. "
                    f"Creative mode: {creative_mode}. "
                    f"Current weak regions: {json.dumps(analysis.get('weak_regions', []))}. "
                    "Return JSON with keys: dominant_issue, silhouette_clarity, canvas_balance, "
                    "density_variation, geometry_strength, freeform_quality, failure_reasons, "
                    "regions_to_change. dominant_issue must be one of composition, structure, texture, efficiency."
                )
                try:
                    critique_response = await self.llm.acomplete_multimodal(
                        critique_prompt, [Path(preview_path)]
                    )
                    cleaned = _clean_llm_output(critique_response)
                    critique_json = _extract_json(cleaned)
                    critique.update(json.loads(critique_json))
                except Exception:
                    logger.step_info("Vision critique fallback to local scoring heuristics")

            refinement_prompt = build_preview_reflection_prompt(
                ev.prompt, critique, self.config.paper, self.style, creative_mode=creative_mode
            )
            weak_regions = critique.get("regions_to_change") or analysis.get("weak_regions", [])
            if weak_regions:
                refinement_prompt += (
                    f"\nTarget these regions specifically: {json.dumps(weak_regions)}\n"
                )

            if critique.get("dominant_issue") in {"composition", "structure"}:
                response = (
                    await self.llm.acomplete_multimodal(refinement_prompt, [Path(preview_path)])
                    if _supports_multimodal(self.llm)
                    else await self.llm.acomplete(refinement_prompt)
                )
            else:
                detail_prompt = (
                    refinement_prompt
                    + "\nPreserve the existing broad composition and improve detail/texture only."
                )
                response = (
                    await self.llm.acomplete_multimodal(detail_prompt, [Path(preview_path)])
                    if _supports_multimodal(self.llm)
                    else await self.llm.acomplete(detail_prompt)
                )

            result = _validate_output(response)
            if isinstance(result, DrawProgram):
                from ..primitives import expand_primitives

                result = expand_primitives(result, self.config.pen)
            if isinstance(result, Exception) or not isinstance(result, GCodeProgram):
                logger.step_warning("Refinement produced invalid output, keeping original")
                return ValidatedGCodeEvent(
                    program=ev.program, gcode_text=ev.program.to_gcode(), prompt=ev.prompt
                )

            refined_report = score_gcode(result, self.config.paper, creative_mode=creative_mode)
            baseline_tuple = (*_select_candidate_report(baseline_report, creative_mode),)
            refined_tuple = (*_select_candidate_report(refined_report, creative_mode),)
            if refined_tuple >= baseline_tuple:
                logger.step_success(
                    f"Refinement improved: grade {baseline_report.grade} -> {refined_report.grade}"
                )
                await ctx.set(
                    "last_refinement_action",
                    (
                        "plan_and_detail"
                        if critique.get("dominant_issue") in {"composition", "structure"}
                        else "detail"
                    ),
                )
                return RefinementEvent(program=result, prompt=ev.prompt, iteration=ev.iteration + 1)

            logger.step_info("Refinement did not improve score; keeping best-so-far")
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
                    ev.prompt,
                    self.config.paper,
                    self.config.pen,
                    self.config.workflow.multipass.detail_style,
                    style_profile=self.style_profile,
                )
                detail_prompt += (
                    f"\n\nAn outline has already been drawn with these strokes:\n{outline_gcode[:800]}\n\n"
                    "Now ADD 100-200 commands of detail, texture, and fill to complement this outline:\n"
                    "- Add hatching/shading lines inside shapes (parallel lines 3-5mm apart).\n"
                    "- Add texture: ground ripples, bark lines on trees, water ripples in rivers.\n"
                    "- Add small decorative elements: rocks, grass tufts, cloud wisps.\n"
                    "- Fill empty canvas areas with environmental detail.\n"
                    "- Use short G1 segments (3-8mm) for organic textures.\n"
                    "Do NOT redraw the outline. Return complete JSON with 'commands' list.\n"
                    "Generate at LEAST 100 G1 drawing commands in this detail pass."
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

        logger.step_success(
            "Post-processing complete",
            {
                "Original commands": len(ev.program.commands),
                "Final commands": len(optimized.commands),
            },
        )
        logger.workflow_complete(True, len(optimized.commands), gcode_lines)

        # Save to memory if grade is A or B
        try:
            creative_mode = optimized.metadata.get(
                "creative_mode", await ctx.get("creative_mode", default="figurative")
            )
            report = score_gcode(optimized, self.config.paper, creative_mode=creative_mode)
            if report.grade in ("A", "B"):
                self.memory.save(
                    prompt=ev.prompt,
                    gcode=gcode_text,
                    grade=report.grade,
                    canvas_utilization=report.canvas_utilization,
                    draw_travel_ratio=report.draw_travel_ratio,
                    command_count=report.command_count,
                    creative_mode=creative_mode,
                    figurative_score=report.figurative_score,
                    abstract_score=report.abstract_score,
                )
                logger.step_info(f"Drawing saved to memory (grade {report.grade})")
            if self.session:
                self.session.set_quality(
                    report.grade,
                    report.canvas_utilization,
                    report.stroke_count,
                    report.draw_travel_ratio,
                )
        except Exception:
            pass

        if self.session:
            self.session.set_phase(Phase.DONE)

        return StopEvent(
            result={
                "prompt": ev.prompt,
                "commands_count": len(optimized.commands),
                "gcode": gcode_text,
                "program": optimized.model_dump(),
                "analysis_artifacts": await ctx.get("last_analysis_artifacts"),
                "refinement_action": await ctx.get("last_refinement_action"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
