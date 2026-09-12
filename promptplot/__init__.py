"""
PromptPlot v3.0 — LLM-driven pen plotter GCode generator

Flat module structure merging PromptPlot + drawStream into one clean project.
"""

__version__ = "3.1.0"
__author__ = "PromptPlot Team"

from .models import (
    GCodeCommand,
    GCodeProgram,
    WorkflowResult,
    CompositionSubject,
    CompositionPlan,
    FigurativeRegion,
    FigurativeCompositionPlan,
    AbstractRegion,
    AbstractCompositionPlan,
    PrimitiveCommand,
    FreeformCommand,
    DrawProgram,
    DrawCommand,
)
from .config import PromptPlotConfig, load_config, get_config
from .workflow import BatchGCodeWorkflow, StreamingGCodeWorkflow, LiveDrawWorkflow
from .pipeline import FilePipeline
from .plotter import BasePlotter, SerialPlotter, SimulatedPlotter, ConnectionState, PlotterStateMachine
from .llm import LLMProvider, create_llm_provider, get_llm_provider, classify_creative_mode
from .engine import (
    DrawingSession, Phase, Workflow, Event, StartEvent, StopEvent, Context, step,
    PenState, PenStateError, IllegalTransitionError, VALID_TRANSITIONS,
)
from .primitives import (
    expand_primitives, expand_primitive, PRIMITIVE_REGISTRY,
    get_primitive_schema, get_all_primitive_schemas, format_schemas_for_prompt,
)
from .postprocess import run_pipeline
from .visualizer import GCodeVisualizer
from .scoring import score_gcode, QualityReport
from .logger import WorkflowLogger
from .checkpoint import CheckpointManager
from .models import Region, ChunkMetrics
from .orchestrate import (
    plan_regions,
    generate_region,
    merge_chunks,
    score_chunk,
    validate_chunk,
    load_and_continue,
    stream_chunk,
    stream_pen_layers,
    split_color_layers,
    trace_frame,
    compose_and_stream,
    PauseSignal,
)

__all__ = [
    # Models
    "GCodeCommand",
    "GCodeProgram",
    "WorkflowResult",
    "CompositionSubject",
    "CompositionPlan",
    "FigurativeRegion",
    "FigurativeCompositionPlan",
    "AbstractRegion",
    "AbstractCompositionPlan",
    "PrimitiveCommand",
    "FreeformCommand",
    "DrawProgram",
    "DrawCommand",
    # Config
    "PromptPlotConfig",
    "load_config",
    "get_config",
    # Workflows
    "BatchGCodeWorkflow",
    "StreamingGCodeWorkflow",
    "LiveDrawWorkflow",
    # Pipeline
    "FilePipeline",
    # Plotter
    "BasePlotter",
    "SerialPlotter",
    "SimulatedPlotter",
    "ConnectionState",
    "PlotterStateMachine",
    # LLM
    "LLMProvider",
    "create_llm_provider",
    "get_llm_provider",
    "classify_creative_mode",
    # Engine
    "DrawingSession",
    "Phase",
    "Workflow",
    "Event",
    "StartEvent",
    "StopEvent",
    "Context",
    "step",
    "PenState",
    "PenStateError",
    "IllegalTransitionError",
    "VALID_TRANSITIONS",
    # Primitives
    "expand_primitives",
    "expand_primitive",
    "PRIMITIVE_REGISTRY",
    "get_primitive_schema",
    "get_all_primitive_schemas",
    "format_schemas_for_prompt",
    # Post-processing
    "run_pipeline",
    # Visualizer
    "GCodeVisualizer",
    # Scoring
    "score_gcode",
    "QualityReport",
    # Logger
    "WorkflowLogger",
    # Checkpoint
    "CheckpointManager",
    # Orchestrate
    "Region",
    "ChunkMetrics",
    "plan_regions",
    "generate_region",
    "merge_chunks",
    "score_chunk",
    "validate_chunk",
    "load_and_continue",
    "stream_chunk",
    "stream_pen_layers",
    "split_color_layers",
    "trace_frame",
    "compose_and_stream",
    "PauseSignal",
]
