"""Workflow Event dataclasses.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

from typing import Any, List

from ..engine import Event
from ..models import GCodeProgram


# ===== sliced body (event classes) =====
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


class PlanEvent(Event):
    plan: Any = None
    prompt: str = ""
    creative_mode: str = "figurative"


class SupervisorPlanEvent(Event):
    prompt: str
    regions: List[Any] = []
    plan: Any = None


class WorkersDoneEvent(Event):
    prompt: str
    regions: List[Any] = []
    chunks: List[Any] = []
    plan: Any = None


class CritiqueDoneEvent(Event):
    prompt: str
    program: GCodeProgram
    weak_indices: List[int] = []
    regions: List[Any] = []
    chunks: List[Any] = []
    plan: Any = None
