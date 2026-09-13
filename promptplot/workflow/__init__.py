"""Workflow package — LLM-driven GCode generation workflows.

Re-exports the public surface that used to live in the flat ``workflow.py``
so existing imports (``from promptplot.workflow import X``) keep working.
"""

from ._shared import diagnose_failure, console, logger
from .events import (
    GenerateGCodeEvent,
    GCodeExtractionDone,
    GCodeValidationErrorEvent,
    ValidatedGCodeEvent,
    RefinementEvent,
    PlanEvent,
    SupervisorPlanEvent,
    WorkersDoneEvent,
    CritiqueDoneEvent,
)
from .batch import BatchGCodeWorkflow
from .supervisor import SupervisorWorkerWorkflow
from .streaming import StreamingGCodeWorkflow
from .livedraw import LiveDrawWorkflow

__all__ = [
    "BatchGCodeWorkflow",
    "SupervisorWorkerWorkflow",
    "StreamingGCodeWorkflow",
    "LiveDrawWorkflow",
    "diagnose_failure",
]
