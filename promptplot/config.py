"""
Unified configuration for PromptPlot v3.0

Merged from PromptPlot config/settings.py + drawStream config_handler.py.
Adds PlotterMode, BrushConfig, PenConfig with pen_up_delay/pen_down_delay wired up,
and configurable pen_down_s_value (default 1000).
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field, fields
from enum import Enum

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class PlotterMode(str, Enum):
    NORMAL = "normal"
    BRUSH = "brush"
    SIMULATION = "simulation"


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    default_provider: str = "ollama"

    openai_model: str = "gpt-4o-mini"
    openai_api_key: Optional[str] = None
    openai_timeout: int = 120

    gemini_model: str = "models/gemini-1.5-flash"
    gemini_api_key: Optional[str] = None
    gemini_timeout: int = 120

    azure_model: str = "gpt-4o"
    azure_deployment_name: str = "gpt-4o-gs"
    azure_api_key: Optional[str] = None
    azure_api_version: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_timeout: int = 1220

    ollama_model: str = "llama3.2:3b"
    ollama_base_url: Optional[str] = None
    ollama_timeout: int = 10000
    ollama_vision_model: str = "llama3.2-vision:11b"

    max_retries: int = 3
    temperature: float = 0.1

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if self.gemini_api_key is None:
            self.gemini_api_key = os.environ.get("GOOGLE_API_KEY")
        if self.azure_api_key is None:
            self.azure_api_key = os.environ.get("GPT4_API_KEY")
        if self.azure_api_version is None:
            self.azure_api_version = os.environ.get("GPT4_API_VERSION")
        if self.azure_endpoint is None:
            self.azure_endpoint = os.environ.get("GPT4_ENDPOINT")
        valid = ["openai", "gemini", "azure_openai", "ollama"]
        if self.default_provider not in valid:
            raise ValueError(f"Invalid LLM provider: {self.default_provider}. Must be one of {valid}")


@dataclass
class PaperConfig:
    """Paper/canvas configuration."""
    width: float = 210.0
    height: float = 297.0
    margin_x: float = 10.0
    margin_y: float = 10.0

    def get_drawable_area(self) -> Tuple[float, float, float, float]:
        return (self.margin_x, self.margin_y,
                self.width - self.margin_x, self.height - self.margin_y)

    def get_drawable_dimensions(self) -> Tuple[float, float]:
        x0, y0, x1, y1 = self.get_drawable_area()
        return x1 - x0, y1 - y0


@dataclass
class PenConfig:
    """Pen control configuration with delays and S-value."""
    up_position: float = 5.0
    down_position: float = 0.0
    up_speed: float = 500.0
    down_speed: float = 200.0
    pen_up_delay: float = 0.2       # seconds — wired to G4 dwell injection
    pen_down_delay: float = 0.2     # seconds — wired to G4 dwell injection
    pen_down_s_value: int = 1000    # S parameter for M3 command (was hardcoded S100)
    feed_rate: int = 2000            # F parameter for G1 draw commands

    def __post_init__(self):
        if self.up_position < self.down_position:
            raise ValueError("up_position must be >= down_position")
        if self.pen_down_s_value < 0:
            raise ValueError("pen_down_s_value must be non-negative")


@dataclass
class BrushConfig:
    """Brush/ink reload configuration."""
    charge_position: Tuple[float, float] = (10.0, 10.0)
    dip_height: float = 0.0
    dip_duration: float = 0.5       # seconds in ink
    drip_duration: float = 1.0      # seconds dripping
    strokes_before_reload: int = 10
    pause_after_move: float = 0.1   # seconds between moves in brush mode
    enabled: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> "BrushConfig":
        pos = data.get("charge_position", {})
        if isinstance(pos, dict) and "x" in pos and "y" in pos:
            position = (pos["x"], pos["y"])
        elif isinstance(pos, (list, tuple)) and len(pos) == 2:
            position = (pos[0], pos[1])
        else:
            position = (10.0, 10.0)
        return cls(
            charge_position=position,
            dip_height=data.get("dip_height", 0.0),
            dip_duration=data.get("dip_duration", 0.5),
            drip_duration=data.get("drip_duration", 1.0),
            strokes_before_reload=data.get("strokes_before_reload", 10),
            pause_after_move=data.get("pause_after_move", 0.1),
            enabled=data.get("enabled", False),
        )


@dataclass
class BoundsConfig:
    """Bounds validation configuration."""
    enforce: bool = True
    mode: str = "clamp"  # "clamp" | "reject" | "warn"

    def __post_init__(self):
        if self.mode not in ("clamp", "reject", "warn"):
            raise ValueError(f"Invalid bounds mode: {self.mode}. Must be clamp, reject, or warn")


@dataclass
class VisionConfig:
    """Multimodal vision configuration."""
    enabled: bool = False
    reference_image: Optional[str] = None
    preview_feedback: bool = False
    max_feedback_iterations: int = 1


@dataclass
class SerialConfig:
    """Serial port configuration."""
    port: str = "/dev/ttyUSB0"
    baud_rate: int = 115200
    timeout: float = 5.0


@dataclass
class VisualizationConfig:
    """Visualization/preview configuration."""
    figure_width: float = 10.0
    figure_height: float = 10.0
    figure_dpi: int = 100
    drawing_color: str = "blue"
    travel_color: str = "lightgray"
    line_width: float = 1.0


@dataclass
class MultiPassConfig:
    """Multi-pass generation configuration."""
    enabled: bool = False
    outline_style: str = "precise"
    detail_style: str = "artistic"


@dataclass
class WorkflowConfig:
    """Workflow execution configuration."""
    max_retries: int = 3
    max_steps: int = 50
    step_timeout: float = 30.0
    output_directory: str = "output"
    multipass: MultiPassConfig = field(default_factory=MultiPassConfig)


@dataclass
class PromptPlotConfig:
    """Top-level configuration container."""
    mode: PlotterMode = PlotterMode.NORMAL
    llm: LLMConfig = field(default_factory=LLMConfig)
    paper: PaperConfig = field(default_factory=PaperConfig)
    pen: PenConfig = field(default_factory=PenConfig)
    brush: BrushConfig = field(default_factory=BrushConfig)
    bounds: BoundsConfig = field(default_factory=BoundsConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    debug: bool = False
    log_level: str = "INFO"


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_config: Optional[PromptPlotConfig] = None


def load_config(config_path: Optional[Union[str, Path]] = None) -> PromptPlotConfig:
    """Load configuration from a JSON/YAML file, or return defaults."""
    global _config

    if config_path is None:
        _config = PromptPlotConfig()
        return _config

    config_path = Path(config_path)
    if not config_path.exists():
        _config = PromptPlotConfig()
        return _config

    with open(config_path, "r") as f:
        suffix = config_path.suffix.lower()
        if suffix in (".yaml", ".yml") and YAML_AVAILABLE:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    _config = _create_config_from_dict(data or {})
    return _config


def get_config() -> PromptPlotConfig:
    """Get current config singleton (loads defaults if not yet loaded)."""
    global _config
    if _config is None:
        _config = PromptPlotConfig()
    return _config


def _create_config_from_dict(data: Dict[str, Any]) -> PromptPlotConfig:
    llm = LLMConfig(**{k: v for k, v in data.get("llm", {}).items()
                       if k in {f.name for f in fields(LLMConfig)}})
    paper = PaperConfig(**{k: v for k, v in data.get("paper", data.get("canvas", {})).items()
                           if k in {f.name for f in fields(PaperConfig)}})
    pen_data = data.get("pen", {})
    pen = PenConfig(**{k: v for k, v in pen_data.items()
                       if k in {f.name for f in fields(PenConfig)}})
    brush = BrushConfig.from_dict(data.get("brush", {}))
    bounds = BoundsConfig(**{k: v for k, v in data.get("bounds", {}).items()
                              if k in {f.name for f in fields(BoundsConfig)}})
    vision = VisionConfig(**{k: v for k, v in data.get("vision", {}).items()
                              if k in {f.name for f in fields(VisionConfig)}})
    serial_data = data.get("serial", {})
    # Support drawStream-style keys
    if "serial_port" in data and "port" not in serial_data:
        serial_data.setdefault("port", data["serial_port"])
    if "baud_rate" in data and "baud_rate" not in serial_data:
        serial_data.setdefault("baud_rate", data["baud_rate"])
    serial = SerialConfig(**{k: v for k, v in serial_data.items()
                             if k in {f.name for f in fields(SerialConfig)}})
    viz = VisualizationConfig(**{k: v for k, v in data.get("visualization", {}).items()
                                 if k in {f.name for f in fields(VisualizationConfig)}})
    wf = WorkflowConfig(**{k: v for k, v in data.get("workflow", {}).items()
                           if k in {f.name for f in fields(WorkflowConfig)}})

    mode_str = data.get("mode", "normal")
    try:
        mode = PlotterMode(mode_str)
    except ValueError:
        mode = PlotterMode.NORMAL

    return PromptPlotConfig(
        mode=mode,
        llm=llm,
        paper=paper,
        pen=pen,
        brush=brush,
        bounds=bounds,
        vision=vision,
        serial=serial,
        visualization=viz,
        workflow=wf,
        debug=data.get("debug", False),
        log_level=data.get("log_level", "INFO"),
    )
