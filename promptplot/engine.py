"""
Custom workflow engine + DrawingSession for PromptPlot v3.0

Replaces LlamaIndex Workflow/Event/Context/step with lightweight equivalents.
DrawingSession is a unified state object for one drawing lifecycle.
"""

import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Union, get_type_hints, get_args, get_origin

from pydantic import BaseModel

from .config import PromptPlotConfig


# ---------------------------------------------------------------------------
# Workflow engine (mirrors LlamaIndex patterns)
# ---------------------------------------------------------------------------

class Event(BaseModel):
    model_config = {"arbitrary_types_allowed": True}


class StartEvent(Event):
    prompt: str = ""


class StopEvent(Event):
    result: Any = None


class Context:
    """Async key-value store replacing LlamaIndex Context."""

    def __init__(self):
        self._store: dict = {}

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    async def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)


def step(func):
    """Decorator that registers which Event type(s) a step handles."""
    hints = get_type_hints(func)
    ev_type = [v for k, v in hints.items() if k not in ("return", "self", "ctx")][0]
    if get_origin(ev_type) is Union:
        func._step_event_types = tuple(get_args(ev_type))
    else:
        func._step_event_types = (ev_type,)
    return func


class Workflow:
    """Lightweight workflow engine: scan @step methods, dispatch events until StopEvent."""

    def __init__(self, timeout: int = 10000, **kwargs):
        self._timeout = timeout
        self._dispatch: dict = {}
        for name in dir(self):
            method = getattr(self, name, None)
            if callable(method) and hasattr(method, "_step_event_types"):
                for et in method._step_event_types:
                    self._dispatch[et] = method

    async def run(self, **kwargs) -> Any:
        ctx = Context()
        event = StartEvent(**kwargs)
        while not isinstance(event, StopEvent):
            handler = self._dispatch.get(type(event))
            if handler is None:
                raise RuntimeError(f"No step for {type(event).__name__}")
            event = await asyncio.wait_for(handler(ctx, event), timeout=self._timeout)
        return event.result


# ---------------------------------------------------------------------------
# PenState — first-class pen state tracker
# ---------------------------------------------------------------------------

class PenStateError(Exception):
    """Raised when a GCode command violates pen state invariants."""

    def __init__(self, message: str, current_state: str, attempted_command: str):
        self.current_state = current_state
        self.attempted_command = attempted_command
        super().__init__(message)


class PenState:
    """Tracks pen up/down state and validates commands against it."""

    UP = "up"
    DOWN = "down"

    def __init__(self, initial: str = "up"):
        if initial not in (self.UP, self.DOWN):
            raise ValueError(f"initial must be '{self.UP}' or '{self.DOWN}', got '{initial}'")
        self._state: str = initial

    @property
    def is_down(self) -> bool:
        return self._state == self.DOWN

    @property
    def is_up(self) -> bool:
        return self._state == self.UP

    @property
    def state(self) -> str:
        return self._state

    def process(self, command: str) -> None:
        """Update state based on command. Raises PenStateError on violation.

        M3 -> DOWN, M5 -> UP.
        G0 requires pen UP, G1 requires pen DOWN.
        Other commands are ignored (no state change, no error).
        """
        cmd = command.strip().split()[0].upper() if command.strip() else ""
        if cmd == "M3":
            self._state = self.DOWN
        elif cmd == "M5":
            self._state = self.UP
        elif cmd == "G0":
            if self.is_down:
                raise PenStateError(
                    f"G0 travel move requires pen UP, but pen is DOWN",
                    self._state, command,
                )
        elif cmd == "G1":
            if self.is_up:
                raise PenStateError(
                    f"G1 draw move requires pen DOWN, but pen is UP",
                    self._state, command,
                )

    def process_safe(self, command: str) -> bool:
        """Like process() but returns False instead of raising."""
        try:
            self.process(command)
            return True
        except PenStateError:
            return False

    def set_up(self) -> None:
        """Force pen state to UP (bypasses validation)."""
        self._state = self.UP

    def set_down(self) -> None:
        """Force pen state to DOWN (bypasses validation)."""
        self._state = self.DOWN

    def reset(self) -> None:
        """Reset to initial UP state."""
        self._state = self.UP

    def snapshot(self) -> dict:
        return {"state": self._state}

    @classmethod
    def from_snapshot(cls, data: dict) -> "PenState":
        return cls(initial=data.get("state", "up"))


# ---------------------------------------------------------------------------
# Phase — drawing lifecycle phases with validated transitions
# ---------------------------------------------------------------------------

class Phase(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    GENERATING = "generating"
    STREAMING = "streaming"
    PAUSED = "paused"
    DONE = "done"


VALID_TRANSITIONS = {
    Phase.IDLE: {Phase.PLANNING, Phase.GENERATING, Phase.STREAMING},
    Phase.PLANNING: {Phase.GENERATING, Phase.DONE},
    Phase.GENERATING: {Phase.STREAMING, Phase.DONE},
    Phase.STREAMING: {Phase.DONE, Phase.PAUSED},
    Phase.PAUSED: {Phase.STREAMING, Phase.DONE},
    Phase.DONE: {Phase.IDLE},
}


class IllegalTransitionError(Exception):
    """Raised when a phase transition is not valid."""

    def __init__(self, current: Phase, target: Phase):
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid targets: {', '.join(p.value for p in VALID_TRANSITIONS.get(current, set()))}"
        )


# ---------------------------------------------------------------------------
# DrawingSession — unified state for one drawing lifecycle
# ---------------------------------------------------------------------------

class DrawingSession:
    """Single source of truth for one drawing lifecycle."""

    def __init__(self, config: PromptPlotConfig):
        self.config = config
        # Identity
        self.prompt: str = ""
        self.mode: str = ""  # "batch" / "live"
        # Phase
        self._phase: Phase = Phase.IDLE
        # Connection
        self.connected: bool = False
        self.plotter_port: str = ""
        self.plotter_type: str = "disconnected"
        # Provider
        self.provider: str = config.llm.default_provider
        self.model: str = getattr(config.llm, f"{config.llm.default_provider}_model", "?")
        self.paper: str = f"{config.paper.width:.0f}x{config.paper.height:.0f}mm"
        # Command log
        self.commands: deque = deque(maxlen=200)
        self.sent: int = 0
        self.errors: int = 0
        self.skipped: int = 0
        # Timing
        self._t0: float = 0.0
        self.elapsed: float = 0.0
        # Quality
        self.grade: str = "-"
        self.utilization: float = 0.0
        self.strokes: int = 0
        self.draw_travel: float = 0.0
        # Workflow context (replaces LlamaIndex Context for retry tracking etc.)
        self._store: dict = {}
        # Event listeners
        self._listeners: dict = {}

    # --- Phase transitions ---
    @property
    def phase(self) -> str:
        return self._phase.value

    def set_phase(self, new_phase: Phase, *, force: bool = False):
        old = self._phase
        if not force and new_phase not in VALID_TRANSITIONS.get(old, set()):
            raise IllegalTransitionError(old, new_phase)
        self._phase = new_phase
        if new_phase == Phase.GENERATING:
            self._t0 = time.time()
        self.elapsed = time.time() - self._t0 if self._t0 else 0.0
        self._emit("phase_change", old=old.value, new=new_phase.value)

    # --- Command logging ---
    def log_command(self, idx: int, gcode: str, status: str, warnings: list = None):
        self.commands.append((idx, gcode, status, warnings or []))
        if status == "ok":
            self.sent += 1
        elif status == "err":
            self.errors += 1
        elif status == "skip":
            self.skipped += 1
        self.elapsed = time.time() - self._t0 if self._t0 else 0.0
        self._emit("command", idx=idx, gcode=gcode, status=status)

    # --- Quality ---
    def set_quality(self, grade: str, utilization: float, strokes: int, draw_travel: float):
        self.grade = grade
        self.utilization = utilization
        self.strokes = strokes
        self.draw_travel = draw_travel
        self._emit("quality", grade=grade)

    # --- Context store (replaces LlamaIndex Context) ---
    async def ctx_set(self, key: str, value: Any):
        self._store[key] = value

    async def ctx_get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    # --- Event emission ---
    def on(self, event_name: str, handler: Callable):
        self._listeners.setdefault(event_name, []).append(handler)

    def _emit(self, event_name: str, **kwargs):
        for handler in self._listeners.get(event_name, []):
            handler(self, **kwargs)

    # --- Checkpoint support ---
    def checkpoint(self, command_index: int, pen_state: PenState,
                   position: tuple = (0.0, 0.0)) -> dict:
        """Create a checkpoint dict for resuming an interrupted drawing."""
        return {
            "prompt": self.prompt,
            "mode": self.mode,
            "phase": self._phase.value,
            "command_index": command_index,
            "pen_state": pen_state.snapshot(),
            "position": list(position),
            "sent": self.sent,
            "errors": self.errors,
            "skipped": self.skipped,
            "elapsed": self.elapsed,
            "grade": self.grade,
        }

    def restore_checkpoint(self, data: dict) -> dict:
        """Restore session state from a checkpoint dict. Returns resumption info."""
        self.prompt = data.get("prompt", "")
        self.mode = data.get("mode", "")
        self.sent = data.get("sent", 0)
        self.errors = data.get("errors", 0)
        self.skipped = data.get("skipped", 0)
        self.elapsed = data.get("elapsed", 0.0)
        self.grade = data.get("grade", "-")
        # Don't validate transition — we're restoring state
        phase_str = data.get("phase", "idle")
        self._phase = Phase(phase_str)
        return {
            "command_index": data.get("command_index", 0),
            "pen_state": PenState.from_snapshot(data.get("pen_state", {})),
            "position": tuple(data.get("position", [0.0, 0.0])),
        }

    # --- Reset for next drawing ---
    def reset(self):
        self.prompt = ""
        self.mode = ""
        self._phase = Phase.IDLE
        self.commands.clear()
        self.sent = 0
        self.errors = 0
        self.skipped = 0
        self.elapsed = 0.0
        self._t0 = 0.0
        self.grade = "-"
        self.utilization = 0.0
        self.strokes = 0
        self.draw_travel = 0.0
        self._store.clear()
        self._emit("reset")

    # --- Serializable snapshot ---
    def snapshot(self) -> dict:
        return {
            "prompt": self.prompt,
            "mode": self.mode,
            "phase": self._phase.value,
            "sent": self.sent,
            "errors": self.errors,
            "grade": self.grade,
            "utilization": self.utilization,
            "strokes": self.strokes,
            "draw_travel": self.draw_travel,
            "elapsed": self.elapsed,
            "command_count": len(self.commands),
        }
