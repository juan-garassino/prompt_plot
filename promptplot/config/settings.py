"""
Centralized Configuration System for PromptPlot v2.0

This module implements centralized configuration management with validation,
default value management, and support for environment variables and configuration files.

Requirements addressed:
- 8.1: Configuration files for different components
- 8.4: Configuration validation and helpful error messages
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List, Type
from pathlib import Path
from dataclasses import dataclass, field, fields
from enum import Enum
import yaml

try:
    import tomli
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False


class ConfigFormat(str, Enum):
    """Supported configuration file formats"""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"


class ValidationLevel(str, Enum):
    """Configuration validation levels"""
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    # Provider settings
    default_provider: str = "ollama"
    
    # Azure OpenAI settings
    azure_model: str = "gpt-4o"
    azure_deployment_name: str = "gpt-4o-gs"
    azure_api_key: Optional[str] = None
    azure_api_version: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_timeout: int = 1220
    
    # Ollama settings
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: Optional[str] = None
    ollama_timeout: int = 10000
    
    # General LLM settings
    max_retries: int = 3
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    
    def __post_init__(self):
        """Post-initialization validation and environment variable loading"""
        # Load from environment variables if not set
        if self.azure_api_key is None:
            self.azure_api_key = os.environ.get("GPT4_API_KEY")
        if self.azure_api_version is None:
            self.azure_api_version = os.environ.get("GPT4_API_VERSION")
        if self.azure_endpoint is None:
            self.azure_endpoint = os.environ.get("GPT4_ENDPOINT")
        
        # Validate provider
        valid_providers = ["azure_openai", "ollama"]
        if self.default_provider not in valid_providers:
            raise ValueError(f"Invalid LLM provider: {self.default_provider}. Must be one of {valid_providers}")


class PaperSize(str, Enum):
    """Standard paper sizes"""
    A4 = "A4"          # 210 x 297 mm
    A3 = "A3"          # 297 x 420 mm
    A5 = "A5"          # 148 x 210 mm
    LETTER = "LETTER"  # 8.5 x 11 inches (215.9 x 279.4 mm)
    LEGAL = "LEGAL"    # 8.5 x 14 inches (215.9 x 355.6 mm)
    TABLOID = "TABLOID" # 11 x 17 inches (279.4 x 431.8 mm)
    CUSTOM = "CUSTOM"  # Custom dimensions


class PaperOrientation(str, Enum):
    """Paper orientation options"""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class Units(str, Enum):
    """Measurement units"""
    MM = "mm"
    INCHES = "inches"
    CM = "cm"


@dataclass
class PaperConfig:
    """Configuration for paper and drawing surface"""
    # Paper size and dimensions
    paper_size: PaperSize = PaperSize.A4
    orientation: PaperOrientation = PaperOrientation.PORTRAIT
    units: Units = Units.MM
    
    # Custom dimensions (used when paper_size is CUSTOM)
    custom_width: float = 210.0
    custom_height: float = 297.0
    
    # Margins (distance from paper edge where drawing should not occur)
    margin_top: float = 10.0
    margin_bottom: float = 10.0
    margin_left: float = 10.0
    margin_right: float = 10.0
    
    # Safe zones (additional buffer inside margins)
    safe_zone_top: float = 5.0
    safe_zone_bottom: float = 5.0
    safe_zone_left: float = 5.0
    safe_zone_right: float = 5.0
    
    # Paper thickness and pen settings
    paper_thickness: float = 0.1  # mm
    pen_up_height: float = 5.0    # mm above paper
    pen_down_pressure: float = 1.0 # relative pressure (0.0 to 1.0)
    
    def __post_init__(self):
        """Post-initialization validation and dimension calculation"""
        # Validate margins
        if any(margin < 0 for margin in [self.margin_top, self.margin_bottom, 
                                        self.margin_left, self.margin_right]):
            raise ValueError("Margins must be non-negative")
        
        # Validate safe zones
        if any(zone < 0 for zone in [self.safe_zone_top, self.safe_zone_bottom,
                                    self.safe_zone_left, self.safe_zone_right]):
            raise ValueError("Safe zones must be non-negative")
        
        # Validate pen settings
        if self.pen_down_pressure < 0.0 or self.pen_down_pressure > 1.0:
            raise ValueError("Pen down pressure must be between 0.0 and 1.0")
    
    def get_paper_dimensions(self) -> tuple[float, float]:
        """Get paper dimensions in configured units"""
        if self.paper_size == PaperSize.CUSTOM:
            width, height = self.custom_width, self.custom_height
        else:
            # Standard paper sizes in mm
            dimensions_mm = {
                PaperSize.A4: (210.0, 297.0),
                PaperSize.A3: (297.0, 420.0),
                PaperSize.A5: (148.0, 210.0),
                PaperSize.LETTER: (215.9, 279.4),
                PaperSize.LEGAL: (215.9, 355.6),
                PaperSize.TABLOID: (279.4, 431.8)
            }
            width, height = dimensions_mm[self.paper_size]
        
        # Apply orientation
        if self.orientation == PaperOrientation.LANDSCAPE:
            width, height = height, width
        
        # Convert units if needed
        if self.units == Units.INCHES:
            width /= 25.4
            height /= 25.4
        elif self.units == Units.CM:
            width /= 10.0
            height /= 10.0
        
        return width, height
    
    def get_drawable_area(self) -> tuple[float, float, float, float]:
        """Get drawable area coordinates (x_min, y_min, x_max, y_max)"""
        paper_width, paper_height = self.get_paper_dimensions()
        
        # Calculate drawable area considering margins and safe zones
        x_min = self.margin_left + self.safe_zone_left
        y_min = self.margin_bottom + self.safe_zone_bottom
        x_max = paper_width - (self.margin_right + self.safe_zone_right)
        y_max = paper_height - (self.margin_top + self.safe_zone_top)
        
        return x_min, y_min, x_max, y_max
    
    def get_drawable_dimensions(self) -> tuple[float, float]:
        """Get drawable area dimensions (width, height)"""
        x_min, y_min, x_max, y_max = self.get_drawable_area()
        return x_max - x_min, y_max - y_min


@dataclass
class PlotterConfig:
    """Configuration for plotter interfaces"""
    # Default plotter type
    default_type: str = "simulated"
    
    # Paper and drawing surface configuration
    paper: PaperConfig = field(default_factory=PaperConfig)
    
    # Serial plotter settings
    serial_port: str = "/dev/ttyUSB0"
    serial_baud_rate: int = 115200
    serial_timeout: float = 5.0
    serial_reconnect_attempts: int = 3
    serial_reconnect_delay: float = 2.0
    
    # Simulated plotter settings
    simulated_delay: float = 0.1
    simulated_visualization: bool = True
    
    # Physical plotter constraints
    max_drawing_width: float = 300.0   # Maximum width plotter can handle (mm)
    max_drawing_height: float = 400.0  # Maximum height plotter can handle (mm)
    coordinate_precision: int = 3       # Decimal places for coordinates
    
    # Movement and speed settings
    max_speed: int = 5000              # Maximum movement speed (mm/min)
    max_acceleration: int = 1000       # Maximum acceleration (mm/s²)
    drawing_speed: int = 2000          # Speed when pen is down (mm/min)
    travel_speed: int = 4000           # Speed when pen is up (mm/min)
    
    # Positioning settings
    home_position: tuple = (0.0, 0.0, 5.0)  # Home position (x, y, z)
    origin_offset: tuple = (0.0, 0.0)        # Offset from physical origin to drawing origin
    
    # Pen settings
    pen_change_position: tuple = (10.0, 10.0, 10.0)  # Position for pen changes
    pen_up_delay: float = 0.2          # Delay after pen up (seconds)
    pen_down_delay: float = 0.2        # Delay after pen down (seconds)
    
    def __post_init__(self):
        """Post-initialization validation"""
        valid_types = ["serial", "simulated"]
        if self.default_type not in valid_types:
            raise ValueError(f"Invalid plotter type: {self.default_type}. Must be one of {valid_types}")
        
        # Validate physical constraints
        if self.max_drawing_width <= 0 or self.max_drawing_height <= 0:
            raise ValueError("Maximum drawing dimensions must be positive")
        
        # Validate speeds
        if self.max_speed <= 0 or self.drawing_speed <= 0 or self.travel_speed <= 0:
            raise ValueError("Speeds must be positive")
        
        if self.drawing_speed > self.max_speed or self.travel_speed > self.max_speed:
            raise ValueError("Drawing and travel speeds cannot exceed maximum speed")
        
        # Check if paper fits in plotter
        paper_width, paper_height = self.paper.get_paper_dimensions()
        
        # Convert paper dimensions to mm for comparison
        if self.paper.units == Units.INCHES:
            paper_width *= 25.4
            paper_height *= 25.4
        elif self.paper.units == Units.CM:
            paper_width *= 10.0
            paper_height *= 10.0
        
        if paper_width > self.max_drawing_width or paper_height > self.max_drawing_height:
            raise ValueError(f"Paper size ({paper_width:.1f}x{paper_height:.1f}mm) exceeds plotter capacity "
                           f"({self.max_drawing_width}x{self.max_drawing_height}mm)")
    
    def get_effective_drawing_area(self) -> tuple[float, float, float, float]:
        """Get effective drawing area considering both paper and plotter constraints"""
        # Get paper drawable area
        paper_area = self.paper.get_drawable_area()
        
        # Convert to mm if needed for plotter constraint checking
        if self.paper.units == Units.INCHES:
            paper_area = tuple(coord * 25.4 for coord in paper_area)
        elif self.paper.units == Units.CM:
            paper_area = tuple(coord * 10.0 for coord in paper_area)
        
        # Apply plotter constraints
        x_min = max(paper_area[0], 0.0)
        y_min = max(paper_area[1], 0.0)
        x_max = min(paper_area[2], self.max_drawing_width)
        y_max = min(paper_area[3], self.max_drawing_height)
        
        # Convert back to paper units if needed
        if self.paper.units == Units.INCHES:
            return x_min / 25.4, y_min / 25.4, x_max / 25.4, y_max / 25.4
        elif self.paper.units == Units.CM:
            return x_min / 10.0, y_min / 10.0, x_max / 10.0, y_max / 10.0
        
        return x_min, y_min, x_max, y_max


@dataclass
class VisualizationConfig:
    """Configuration for visualization and plotting"""
    # Figure settings
    figure_width: float = 10.0
    figure_height: float = 10.0
    figure_dpi: int = 100
    
    # Grid settings
    enable_grid: bool = True
    grid_type: str = "major"  # none, major, minor, both
    major_grid_spacing: tuple = (10.0, 10.0)
    minor_grid_spacing: tuple = (1.0, 1.0)
    grid_color: str = "gray"
    grid_alpha: float = 0.6
    
    # Drawing settings
    line_width: float = 2.0
    movement_line_width: float = 1.0
    drawing_color: str = "green"
    movement_color: str = "blue"
    marker_size: float = 8.0
    
    # Animation settings
    enable_animation: bool = False
    animation_interval: int = 100
    
    # Export settings
    default_format: str = "png"
    export_dpi: int = 150
    
    def __post_init__(self):
        """Post-initialization validation"""
        valid_grid_types = ["none", "major", "minor", "both"]
        if self.grid_type not in valid_grid_types:
            raise ValueError(f"Invalid grid type: {self.grid_type}. Must be one of {valid_grid_types}")
        
        valid_formats = ["png", "pdf", "svg", "eps"]
        if self.default_format not in valid_formats:
            raise ValueError(f"Invalid export format: {self.default_format}. Must be one of {valid_formats}")


@dataclass
class WorkflowConfig:
    """Configuration for workflow execution"""
    # General workflow settings
    default_workflow: str = "simple_batch"
    max_steps: int = 50
    step_timeout: float = 30.0
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_reflection: bool = True
    
    # Validation settings
    validation_level: str = "basic"  # none, basic, comprehensive, strict
    enable_auto_recovery: bool = True
    
    # Progress tracking
    enable_progress_tracking: bool = True
    progress_update_interval: int = 5
    
    # Output settings
    save_intermediate_results: bool = False
    output_directory: str = "results"
    
    def __post_init__(self):
        """Post-initialization validation"""
        valid_workflows = ["simple_batch", "advanced_sequential", "simple_streaming", "advanced_streaming", "plot_enhanced"]
        if self.default_workflow not in valid_workflows:
            raise ValueError(f"Invalid workflow: {self.default_workflow}. Must be one of {valid_workflows}")
        
        valid_validation_levels = ["none", "basic", "comprehensive", "strict"]
        if self.validation_level not in valid_validation_levels:
            raise ValueError(f"Invalid validation level: {self.validation_level}. Must be one of {valid_validation_levels}")


@dataclass
class VisionConfig:
    """Configuration for computer vision and plot analysis"""
    # Plot analysis settings
    enable_plot_analysis: bool = True
    coordinate_precision: int = 3
    grid_resolution: float = 1.0
    
    # Context management
    max_plot_history: int = 10
    snapshot_interval: int = 5
    enable_caching: bool = True
    
    # Visual feedback settings
    enable_visual_feedback: bool = True
    feedback_threshold: float = 0.8
    
    # Image processing settings
    image_format: str = "png"
    image_dpi: int = 100
    image_quality: int = 95
    
    # Multi-modal settings
    enable_multimodal: bool = True
    max_image_size: int = 1024  # pixels
    
    def __post_init__(self):
        """Post-initialization validation"""
        valid_formats = ["png", "jpg", "jpeg", "bmp"]
        if self.image_format not in valid_formats:
            raise ValueError(f"Invalid image format: {self.image_format}. Must be one of {valid_formats}")


@dataclass
class PromptPlotConfig:
    """Main configuration class containing all component configurations"""
    # Component configurations
    llm: LLMConfig = field(default_factory=LLMConfig)
    plotter: PlotterConfig = field(default_factory=PlotterConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    
    # Global settings
    debug: bool = False
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Validation settings
    validation_level: ValidationLevel = ValidationLevel.BASIC
    strict_mode: bool = False
    
    def __post_init__(self):
        """Post-initialization validation"""
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")


class ConfigurationManager:
    """
    Centralized configuration manager with validation and file support
    
    Provides:
    - Configuration validation and default value management
    - Support for environment variables and configuration files
    - Multiple file format support (JSON, YAML, TOML)
    - Configuration merging and inheritance
    """
    
    def __init__(self):
        """Initialize configuration manager"""
        self._config: Optional[PromptPlotConfig] = None
        self._config_file: Optional[Path] = None
        self._config_format: Optional[ConfigFormat] = None
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def load_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        config_format: Optional[ConfigFormat] = None,
        merge_env: bool = True
    ) -> PromptPlotConfig:
        """
        Load configuration from file or create default
        
        Args:
            config_path: Path to configuration file
            config_format: Configuration file format (auto-detected if None)
            merge_env: Whether to merge environment variables
            
        Returns:
            Loaded configuration object
        """
        try:
            if config_path:
                config_path = Path(config_path)
                self._config_file = config_path
                
                # Auto-detect format if not specified
                if config_format is None:
                    config_format = self._detect_format(config_path)
                
                self._config_format = config_format
                
                # Load configuration data
                if config_path.exists():
                    config_data = self._load_file(config_path, config_format)
                    self._config = self._create_config_from_dict(config_data)
                    self.logger.info(f"Configuration loaded from {config_path}")
                else:
                    self.logger.warning(f"Configuration file not found: {config_path}")
                    self._config = PromptPlotConfig()
            else:
                # Create default configuration
                self._config = PromptPlotConfig()
                self.logger.info("Using default configuration")
            
            # Merge environment variables if requested
            if merge_env:
                self._merge_environment_variables()
            
            # Validate configuration
            self._validate_config()
            
            return self._config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            # Return default configuration on error
            self._config = PromptPlotConfig()
            return self._config
    
    def save_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        config_format: Optional[ConfigFormat] = None
    ) -> bool:
        """
        Save current configuration to file
        
        Args:
            config_path: Path to save configuration (uses loaded path if None)
            config_format: Format to save in (uses loaded format if None)
            
        Returns:
            True if save successful
        """
        if self._config is None:
            self.logger.error("No configuration to save")
            return False
        
        try:
            # Determine save path and format
            save_path = Path(config_path) if config_path else self._config_file
            save_format = config_format or self._config_format or ConfigFormat.JSON
            
            if save_path is None:
                save_path = Path("promptplot_config.json")
                save_format = ConfigFormat.JSON
            
            # Convert config to dictionary
            config_dict = self._config_to_dict(self._config)
            
            # Save to file
            self._save_file(save_path, config_dict, save_format)
            
            self.logger.info(f"Configuration saved to {save_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def get_config(self) -> PromptPlotConfig:
        """
        Get current configuration, loading default if none exists
        
        Returns:
            Current configuration object
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def reset_config(self) -> PromptPlotConfig:
        """
        Reset to default configuration
        
        Returns:
            Default configuration object
        """
        self._config = PromptPlotConfig()
        self._config_file = None
        self._config_format = None
        self.logger.info("Configuration reset to defaults")
        return self._config
    
    def validate_config(self, config: Optional[PromptPlotConfig] = None) -> List[str]:
        """
        Validate configuration and return list of errors
        
        Args:
            config: Configuration to validate (uses current if None)
            
        Returns:
            List of validation error messages
        """
        if config is None:
            config = self.get_config()
        
        errors = []
        
        try:
            # Validate each component
            self._validate_component(config.llm, "LLM", errors)
            self._validate_component(config.plotter, "Plotter", errors)
            self._validate_component(config.visualization, "Visualization", errors)
            self._validate_component(config.workflow, "Workflow", errors)
            self._validate_component(config.vision, "Vision", errors)
            
            # Cross-component validation
            self._validate_cross_component(config, errors)
            
        except Exception as e:
            errors.append(f"Configuration validation failed: {str(e)}")
        
        return errors
    
    def _detect_format(self, config_path: Path) -> ConfigFormat:
        """Detect configuration file format from extension"""
        suffix = config_path.suffix.lower()
        
        if suffix in ['.json']:
            return ConfigFormat.JSON
        elif suffix in ['.yaml', '.yml']:
            return ConfigFormat.YAML
        elif suffix in ['.toml']:
            return ConfigFormat.TOML
        elif suffix in ['.env']:
            return ConfigFormat.ENV
        else:
            # Default to JSON
            return ConfigFormat.JSON
    
    def _load_file(self, config_path: Path, config_format: ConfigFormat) -> Dict[str, Any]:
        """Load configuration data from file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_format == ConfigFormat.JSON:
                return json.load(f)
            elif config_format == ConfigFormat.YAML:
                return yaml.safe_load(f)
            elif config_format == ConfigFormat.TOML:
                if not TOML_AVAILABLE:
                    raise ImportError("TOML support requires 'tomli' package: pip install tomli")
                return tomli.load(f.buffer)
            elif config_format == ConfigFormat.ENV:
                return self._load_env_file(f)
            else:
                raise ValueError(f"Unsupported configuration format: {config_format}")
    
    def _save_file(self, config_path: Path, config_dict: Dict[str, Any], config_format: ConfigFormat) -> None:
        """Save configuration data to file"""
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            if config_format == ConfigFormat.JSON:
                json.dump(config_dict, f, indent=2, default=str)
            elif config_format == ConfigFormat.YAML:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            elif config_format == ConfigFormat.TOML:
                # Note: TOML writing would require additional library
                raise NotImplementedError("TOML writing not implemented")
            else:
                raise ValueError(f"Unsupported save format: {config_format}")
    
    def _load_env_file(self, file_handle) -> Dict[str, Any]:
        """Load environment-style configuration file"""
        config_dict = {}
        
        for line in file_handle:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Convert to nested dict structure
                    self._set_nested_value(config_dict, key.strip(), value.strip())
        
        return config_dict
    
    def _set_nested_value(self, config_dict: Dict[str, Any], key: str, value: str) -> None:
        """Set nested dictionary value from dot-notation key"""
        keys = key.split('.')
        current = config_dict
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Convert value to appropriate type
        current[keys[-1]] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate Python type"""
        # Remove quotes
        value = value.strip('\'"')
        
        # Boolean conversion
        if value.lower() in ['true', 'yes', '1']:
            return True
        elif value.lower() in ['false', 'no', '0']:
            return False
        
        # Number conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _create_config_from_dict(self, config_dict: Dict[str, Any]) -> PromptPlotConfig:
        """Create configuration object from dictionary"""
        # Create component configs
        llm_config = LLMConfig(**config_dict.get('llm', {}))
        plotter_config = PlotterConfig(**config_dict.get('plotter', {}))
        visualization_config = VisualizationConfig(**config_dict.get('visualization', {}))
        workflow_config = WorkflowConfig(**config_dict.get('workflow', {}))
        vision_config = VisionConfig(**config_dict.get('vision', {}))
        
        # Create main config
        main_config_data = {k: v for k, v in config_dict.items() 
                           if k not in ['llm', 'plotter', 'visualization', 'workflow', 'vision']}
        
        return PromptPlotConfig(
            llm=llm_config,
            plotter=plotter_config,
            visualization=visualization_config,
            workflow=workflow_config,
            vision=vision_config,
            **main_config_data
        )
    
    def _config_to_dict(self, config: PromptPlotConfig) -> Dict[str, Any]:
        """Convert configuration object to dictionary"""
        result = {}
        
        # Convert each field
        for field_info in fields(config):
            value = getattr(config, field_info.name)
            
            if hasattr(value, '__dataclass_fields__'):
                # Convert dataclass to dict
                result[field_info.name] = {
                    f.name: getattr(value, f.name) 
                    for f in fields(value)
                }
            else:
                result[field_info.name] = value
        
        return result
    
    def _merge_environment_variables(self) -> None:
        """Merge environment variables into configuration"""
        if self._config is None:
            return
        
        # Define environment variable mappings
        env_mappings = {
            'PROMPTPLOT_DEBUG': ('debug', bool),
            'PROMPTPLOT_LOG_LEVEL': ('log_level', str),
            'PROMPTPLOT_LOG_FILE': ('log_file', str),
            
            # LLM settings
            'PROMPTPLOT_LLM_PROVIDER': ('llm.default_provider', str),
            'GPT4_API_KEY': ('llm.azure_api_key', str),
            'GPT4_API_VERSION': ('llm.azure_api_version', str),
            'GPT4_ENDPOINT': ('llm.azure_endpoint', str),
            
            # Plotter settings
            'PROMPTPLOT_PLOTTER_TYPE': ('plotter.default_type', str),
            'PROMPTPLOT_SERIAL_PORT': ('plotter.serial_port', str),
            
            # Workflow settings
            'PROMPTPLOT_MAX_STEPS': ('workflow.max_steps', int),
            'PROMPTPLOT_MAX_RETRIES': ('workflow.max_retries', int),
        }
        
        for env_var, (config_path, value_type) in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                try:
                    # Convert value to appropriate type
                    if value_type == bool:
                        converted_value = env_value.lower() in ['true', 'yes', '1']
                    elif value_type == int:
                        converted_value = int(env_value)
                    elif value_type == float:
                        converted_value = float(env_value)
                    else:
                        converted_value = env_value
                    
                    # Set nested value
                    self._set_config_value(config_path, converted_value)
                    
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid environment variable {env_var}={env_value}: {str(e)}")
    
    def _set_config_value(self, config_path: str, value: Any) -> None:
        """Set configuration value using dot notation path"""
        if self._config is None:
            return
        
        parts = config_path.split('.')
        current = self._config
        
        for part in parts[:-1]:
            current = getattr(current, part)
        
        setattr(current, parts[-1], value)
    
    def _validate_config(self) -> None:
        """Validate current configuration"""
        if self._config is None:
            return
        
        errors = self.validate_config(self._config)
        
        if errors:
            if self._config.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
            else:
                for error in errors:
                    self.logger.warning(f"Configuration warning: {error}")
    
    def _validate_component(self, component: Any, component_name: str, errors: List[str]) -> None:
        """Validate individual configuration component"""
        try:
            # Component validation is handled in __post_init__ methods
            pass
        except Exception as e:
            errors.append(f"{component_name} configuration error: {str(e)}")
    
    def _validate_cross_component(self, config: PromptPlotConfig, errors: List[str]) -> None:
        """Validate cross-component dependencies"""
        # Check LLM provider availability
        if config.llm.default_provider == "azure_openai":
            if not all([config.llm.azure_api_key, config.llm.azure_api_version, config.llm.azure_endpoint]):
                errors.append("Azure OpenAI provider requires api_key, api_version, and endpoint")
        
        # Check plotter configuration
        if config.plotter.default_type == "serial" and not config.plotter.serial_port:
            errors.append("Serial plotter requires serial_port configuration")
        
        # Check visualization settings
        if config.visualization.enable_animation and not config.visualization.enable_grid:
            # This is just a warning, not an error
            pass


# Global configuration manager instance
_config_manager = ConfigurationManager()


def get_config() -> PromptPlotConfig:
    """
    Get current global configuration
    
    Returns:
        Current configuration object
    """
    return _config_manager.get_config()


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    config_format: Optional[ConfigFormat] = None,
    merge_env: bool = True
) -> PromptPlotConfig:
    """
    Load configuration from file
    
    Args:
        config_path: Path to configuration file
        config_format: Configuration file format
        merge_env: Whether to merge environment variables
        
    Returns:
        Loaded configuration object
    """
    return _config_manager.load_config(config_path, config_format, merge_env)


def save_config(
    config_path: Optional[Union[str, Path]] = None,
    config_format: Optional[ConfigFormat] = None
) -> bool:
    """
    Save current configuration to file
    
    Args:
        config_path: Path to save configuration
        config_format: Format to save in
        
    Returns:
        True if save successful
    """
    return _config_manager.save_config(config_path, config_format)


def reset_config() -> PromptPlotConfig:
    """
    Reset to default configuration
    
    Returns:
        Default configuration object
    """
    return _config_manager.reset_config()


def validate_config(config: Optional[PromptPlotConfig] = None) -> List[str]:
    """
    Validate configuration
    
    Args:
        config: Configuration to validate (uses current if None)
        
    Returns:
        List of validation error messages
    """
    return _config_manager.validate_config(config)