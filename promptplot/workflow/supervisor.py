"""SupervisorWorkerWorkflow — fan-out per region, merge, critique, retry.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

import asyncio
import json
from typing import Union, Optional, List
from datetime import datetime


from ..engine import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
    DrawingSession,
)
from ..models import (
    GCodeCommand,
    CompositionPlan,
    FigurativeCompositionPlan,
    AbstractCompositionPlan,
)
from ..config import get_config, PromptPlotConfig
from ..llm import (
    LLMProvider,
    get_llm_provider,
    build_composition_plan_prompt,
)

from ._shared import (
    logger,
    _clean_llm_output,
    _extract_json,
)
from .events import (
    ValidatedGCodeEvent,
    SupervisorPlanEvent,
    WorkersDoneEvent,
    CritiqueDoneEvent,
)


# ===== sliced body (SupervisorWorkerWorkflow) =====
class SupervisorWorkerWorkflow(Workflow):
    """Plan -> N worker LLM calls in parallel -> merge -> per-region critique -> retry weak."""

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        config: Optional[PromptPlotConfig] = None,
        regions: int = 4,
        strategy: str = "grid_2x2",
        style: str = "artistic",
        session: Optional[DrawingSession] = None,
        **kwargs,
    ):
        kwargs.setdefault("timeout", 10000)
        super().__init__(**kwargs)
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.regions_count = regions
        self.strategy = strategy
        self.style = style
        self.session = session

    @step
    async def plan_step(self, ctx: Context, ev: StartEvent) -> SupervisorPlanEvent:
        from ..orchestrate import plan_regions

        prompt = getattr(ev, "prompt", "")
        plan = None
        if self.config.workflow.planning_enabled:
            try:
                plan_prompt = build_composition_plan_prompt(
                    prompt,
                    self.config.paper,
                    self.style,
                )
                response = await self.llm.acomplete(plan_prompt)
                cleaned = _clean_llm_output(response)
                data = json.loads(_extract_json(cleaned))
                try:
                    plan = FigurativeCompositionPlan(**data)
                except Exception:
                    try:
                        plan = AbstractCompositionPlan(**data)
                    except Exception:
                        plan = CompositionPlan(**data)
            except Exception as e:
                logger.step_warning(f"Plan failed, using strategy={self.strategy}: {e}")

        if plan is not None and self.strategy == "composition_plan":
            regions_list = plan_regions(
                (0.0, 0.0, self.config.paper.x_extent, self.config.paper.y_extent),
                strategy="composition_plan",
                composition_plan=plan,
            )
        else:
            strat = self.strategy
            if strat == "grid_2x2" and self.regions_count >= 9:
                strat = "grid_3x3"
            regions_list = plan_regions(
                (0.0, 0.0, self.config.paper.x_extent, self.config.paper.y_extent),
                strategy=strat,
            )
            if self.regions_count and self.regions_count < len(regions_list):
                regions_list = regions_list[: self.regions_count]
        return SupervisorPlanEvent(prompt=prompt, regions=regions_list, plan=plan)

    @step
    async def dispatch_workers(self, ctx: Context, ev: SupervisorPlanEvent) -> WorkersDoneEvent:
        from ..orchestrate import generate_region

        plan_context = None
        if ev.plan is not None and hasattr(ev.plan, "to_prompt_guidance"):
            try:
                plan_context = ev.plan.to_prompt_guidance()
            except Exception:
                plan_context = None
        tasks = [
            generate_region(ev.prompt, region, self.llm, self.config, plan_context=plan_context)
            for region in ev.regions
        ]
        chunks = await asyncio.gather(*tasks, return_exceptions=True)
        clean_chunks: List[List[GCodeCommand]] = []
        for c in chunks:
            if isinstance(c, Exception):
                clean_chunks.append([])
            else:
                clean_chunks.append(c)
        return WorkersDoneEvent(
            prompt=ev.prompt,
            regions=ev.regions,
            chunks=clean_chunks,
            plan=ev.plan,
        )

    @step
    async def merge_step(self, ctx: Context, ev: WorkersDoneEvent) -> CritiqueDoneEvent:
        from ..orchestrate import merge_chunks

        program = merge_chunks(ev.chunks, self.config)
        return CritiqueDoneEvent(
            prompt=ev.prompt,
            program=program,
            weak_indices=[],
            regions=ev.regions,
            chunks=ev.chunks,
            plan=ev.plan,
        )

    @step
    async def critique_step(
        self, ctx: Context, ev: CritiqueDoneEvent
    ) -> Union[CritiqueDoneEvent, ValidatedGCodeEvent]:
        from ..orchestrate import score_chunk

        # Already retried once?
        retried = await ctx.get("supervisor_retried", default=False)
        weak: List[int] = []
        for i, (region, chunk) in enumerate(zip(ev.regions, ev.chunks)):
            metrics = score_chunk(chunk, region)
            if metrics.coverage < 0.25 or metrics.segment_count < 10:
                weak.append(i)
        if retried or not weak:
            return ValidatedGCodeEvent(
                program=ev.program,
                gcode_text=ev.program.to_gcode(),
                prompt=ev.prompt,
            )
        await ctx.set("supervisor_retried", True)
        return await self.retry_weak_regions(
            ctx,
            CritiqueDoneEvent(
                prompt=ev.prompt,
                program=ev.program,
                weak_indices=weak,
                regions=ev.regions,
                chunks=ev.chunks,
                plan=ev.plan,
            ),
        )

    async def retry_weak_regions(self, ctx: Context, ev: CritiqueDoneEvent) -> ValidatedGCodeEvent:
        from ..orchestrate import generate_region, merge_chunks

        plan_context = None
        if ev.plan is not None and hasattr(ev.plan, "to_prompt_guidance"):
            try:
                plan_context = ev.plan.to_prompt_guidance()
            except Exception:
                plan_context = None
        tasks = [
            generate_region(
                ev.prompt, ev.regions[i], self.llm, self.config, plan_context=plan_context
            )
            for i in ev.weak_indices
        ]
        new_chunks = await asyncio.gather(*tasks, return_exceptions=True)
        chunks = list(ev.chunks)
        for slot, idx in enumerate(ev.weak_indices):
            new = new_chunks[slot]
            if not isinstance(new, Exception) and new:
                chunks[idx] = new
        program = merge_chunks(chunks, self.config)
        logger.step_info(f"Retried {len(ev.weak_indices)} weak regions")
        return ValidatedGCodeEvent(
            program=program,
            gcode_text=program.to_gcode(),
            prompt=ev.prompt,
        )

    @step
    async def end(self, ctx: Context, ev: ValidatedGCodeEvent) -> StopEvent:
        return StopEvent(
            result={
                "prompt": ev.prompt,
                "commands_count": len(ev.program.commands),
                "gcode": ev.gcode_text,
                "program": ev.program.model_dump(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
