"""
PromptPlot v3.0 — LLM-driven pen plotter GCode generator

Flat module structure merging PromptPlot + drawStream into one clean project.
"""

__version__ = "3.0.0"
__author__ = "PromptPlot Team"

from .models import GCodeCommand, GCodeProgram, WorkflowResult
from .config import PromptPlotConfig, load_config, get_config
from .workflow import BatchGCodeWorkflow, StreamingGCodeWorkflow, LiveDrawWorkflow
from .pipeline import FilePipeline
from .plotter import BasePlotter, SerialPlotter, SimulatedPlotter
from .llm import LLMProvider, create_llm_provider, get_llm_provider
from .postprocess import run_pipeline
from .visualizer import GCodeVisualizer
from .scoring import score_gcode, QualityReport
from .logger import WorkflowLogger

__all__ = [
    # Models
    "GCodeCommand",
    "GCodeProgram",
    "WorkflowResult",
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
    # LLM
    "LLMProvider",
    "create_llm_provider",
    "get_llm_provider",
    # Post-processing
    "run_pipeline",
    # Visualizer
    "GCodeVisualizer",
    # Scoring
    "score_gcode",
    "QualityReport",
    # Logger
    "WorkflowLogger",
]
