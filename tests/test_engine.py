"""Tests for the custom workflow engine and DrawingSession."""

import pytest
from typing import Union

from promptplot.config import PromptPlotConfig
from promptplot.engine import (
    Event, StartEvent, StopEvent, Context, step, Workflow,
    DrawingSession, Phase, IllegalTransitionError, VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# Event tests
# ---------------------------------------------------------------------------

class TestEvents:
    def test_start_event_default_prompt(self):
        ev = StartEvent()
        assert ev.prompt == ""

    def test_start_event_with_prompt(self):
        ev = StartEvent(prompt="draw a circle")
        assert ev.prompt == "draw a circle"

    def test_stop_event_default_result(self):
        ev = StopEvent()
        assert ev.result is None

    def test_stop_event_with_result(self):
        ev = StopEvent(result={"ok": True})
        assert ev.result == {"ok": True}

    def test_custom_event(self):
        class MyEvent(Event):
            value: int = 0
        ev = MyEvent(value=42)
        assert ev.value == 42


# ---------------------------------------------------------------------------
# Context tests
# ---------------------------------------------------------------------------

class TestContext:
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        ctx = Context()
        await ctx.set("key", "value")
        assert await ctx.get("key") == "value"

    @pytest.mark.asyncio
    async def test_get_default(self):
        ctx = Context()
        assert await ctx.get("missing", default=42) == 42

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        ctx = Context()
        assert await ctx.get("missing") is None


# ---------------------------------------------------------------------------
# step decorator tests
# ---------------------------------------------------------------------------

class TestStepDecorator:
    def test_step_registers_single_type(self):
        @step
        async def handler(self, ctx: Context, ev: StartEvent) -> StopEvent:
            return StopEvent()
        assert handler._step_event_types == (StartEvent,)

    def test_step_registers_union_types(self):
        class EventA(Event):
            pass
        class EventB(Event):
            pass

        @step
        async def handler(self, ctx: Context, ev: Union[EventA, EventB]) -> StopEvent:
            return StopEvent()
        assert set(handler._step_event_types) == {EventA, EventB}


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------

class TestWorkflow:
    @pytest.mark.asyncio
    async def test_simple_workflow(self):
        class SimpleWorkflow(Workflow):
            @step
            async def handle_start(self, ctx: Context, ev: StartEvent) -> StopEvent:
                return StopEvent(result=f"got: {ev.prompt}")

        wf = SimpleWorkflow()
        result = await wf.run(prompt="hello")
        assert result == "got: hello"

    @pytest.mark.asyncio
    async def test_multi_step_workflow(self):
        class MiddleEvent(Event):
            data: str = ""

        class TwoStepWorkflow(Workflow):
            @step
            async def first(self, ctx: Context, ev: StartEvent) -> MiddleEvent:
                return MiddleEvent(data=ev.prompt.upper())

            @step
            async def second(self, ctx: Context, ev: MiddleEvent) -> StopEvent:
                return StopEvent(result=ev.data)

        wf = TwoStepWorkflow()
        result = await wf.run(prompt="test")
        assert result == "TEST"

    @pytest.mark.asyncio
    async def test_no_handler_raises(self):
        class EmptyWorkflow(Workflow):
            pass

        wf = EmptyWorkflow()
        with pytest.raises(RuntimeError, match="No step for StartEvent"):
            await wf.run(prompt="hello")

    @pytest.mark.asyncio
    async def test_union_dispatch(self):
        class RetryEvent(Event):
            attempt: int = 0

        class RetryWorkflow(Workflow):
            @step
            async def start(self, ctx: Context, ev: StartEvent) -> RetryEvent:
                return RetryEvent(attempt=1)

            @step
            async def handle(self, ctx: Context, ev: Union[RetryEvent, StartEvent]) -> StopEvent:
                if isinstance(ev, RetryEvent):
                    return StopEvent(result=ev.attempt)
                return StopEvent(result=0)

        wf = RetryWorkflow()
        # StartEvent dispatches to `start`, which returns RetryEvent, which dispatches to `handle`
        result = await wf.run(prompt="test")
        assert result == 1


# ---------------------------------------------------------------------------
# DrawingSession tests
# ---------------------------------------------------------------------------

class TestDrawingSession:
    def test_default_state(self):
        session = DrawingSession(PromptPlotConfig())
        assert session.phase == "idle"
        assert session.connected is False
        assert session.sent == 0
        assert session.grade == "-"

    def test_paper_string(self):
        session = DrawingSession(PromptPlotConfig())
        assert "210" in session.paper
        assert "297" in session.paper

    def test_phase_transition(self):
        session = DrawingSession(PromptPlotConfig())
        events = []
        session.on("phase_change", lambda s, **kw: events.append(kw))
        session.set_phase(Phase.GENERATING)
        assert session.phase == "generating"
        assert len(events) == 1
        assert events[0]["new"] == "generating"

    def test_log_command_ok(self):
        session = DrawingSession(PromptPlotConfig())
        events = []
        session.on("command", lambda s, **kw: events.append(kw))
        session.log_command(1, "G1 X10 Y20 F2000", "ok")
        assert session.sent == 1
        assert len(session.commands) == 1
        assert len(events) == 1

    def test_log_command_err(self):
        session = DrawingSession(PromptPlotConfig())
        session.log_command(1, "bad", "err")
        assert session.errors == 1

    def test_log_command_skip(self):
        session = DrawingSession(PromptPlotConfig())
        session.log_command(1, "skip", "skip")
        assert session.skipped == 1

    def test_set_quality(self):
        session = DrawingSession(PromptPlotConfig())
        events = []
        session.on("quality", lambda s, **kw: events.append(kw))
        session.set_quality("B", 0.65, 12, 3.2)
        assert session.grade == "B"
        assert session.utilization == 0.65
        assert session.strokes == 12
        assert session.draw_travel == 3.2
        assert len(events) == 1

    def test_reset(self):
        session = DrawingSession(PromptPlotConfig())
        session.prompt = "test"
        session.log_command(1, "G1", "ok")
        session.set_quality("A", 0.8, 5, 2.0)
        events = []
        session.on("reset", lambda s, **kw: events.append(True))
        session.reset()
        assert session.prompt == ""
        assert session.sent == 0
        assert session.grade == "-"
        assert session.phase == "idle"
        assert len(session.commands) == 0
        assert len(events) == 1

    def test_snapshot(self):
        session = DrawingSession(PromptPlotConfig())
        session.prompt = "spiral"
        session.mode = "batch"
        snap = session.snapshot()
        assert snap["prompt"] == "spiral"
        assert snap["mode"] == "batch"
        assert snap["phase"] == "idle"
        assert isinstance(snap["sent"], int)

    @pytest.mark.asyncio
    async def test_ctx_set_get(self):
        session = DrawingSession(PromptPlotConfig())
        await session.ctx_set("retries", 2)
        assert await session.ctx_get("retries") == 2
        assert await session.ctx_get("missing", default=0) == 0


# ---------------------------------------------------------------------------
# Phase transition validation tests
# ---------------------------------------------------------------------------

class TestPhaseTransitions:
    def test_valid_idle_to_generating(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.GENERATING)
        assert session.phase == "generating"

    def test_valid_idle_to_planning(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.PLANNING)
        assert session.phase == "planning"

    def test_valid_idle_to_streaming(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.STREAMING)
        assert session.phase == "streaming"

    def test_valid_generating_to_done(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.GENERATING)
        session.set_phase(Phase.DONE)
        assert session.phase == "done"

    def test_valid_streaming_to_paused(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.STREAMING)
        session.set_phase(Phase.PAUSED)
        assert session.phase == "paused"

    def test_valid_paused_to_streaming(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.STREAMING)
        session.set_phase(Phase.PAUSED)
        session.set_phase(Phase.STREAMING)
        assert session.phase == "streaming"

    def test_invalid_idle_to_done_raises(self):
        session = DrawingSession(PromptPlotConfig())
        with pytest.raises(IllegalTransitionError) as exc_info:
            session.set_phase(Phase.DONE)
        assert exc_info.value.current == Phase.IDLE
        assert exc_info.value.target == Phase.DONE

    def test_invalid_generating_to_paused_raises(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.GENERATING)
        with pytest.raises(IllegalTransitionError):
            session.set_phase(Phase.PAUSED)

    def test_force_bypasses_validation(self):
        session = DrawingSession(PromptPlotConfig())
        # IDLE -> DONE is normally invalid
        session.set_phase(Phase.DONE, force=True)
        assert session.phase == "done"

    def test_planning_to_generating(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.PLANNING)
        session.set_phase(Phase.GENERATING)
        assert session.phase == "generating"

    def test_done_to_idle(self):
        session = DrawingSession(PromptPlotConfig())
        session.set_phase(Phase.GENERATING)
        session.set_phase(Phase.DONE)
        session.set_phase(Phase.IDLE)
        assert session.phase == "idle"

    def test_all_valid_transitions_covered(self):
        """Ensure VALID_TRANSITIONS has an entry for every Phase."""
        for phase in Phase:
            assert phase in VALID_TRANSITIONS

    def test_planning_and_paused_phases_exist(self):
        assert Phase.PLANNING.value == "planning"
        assert Phase.PAUSED.value == "paused"
