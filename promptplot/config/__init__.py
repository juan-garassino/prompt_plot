"""
Configuration and Settings Management for PromptPlot v2.0

This module provides centralized configuration management with support for
environment variables, configuration files, validation, default values,
configuration profiles, and runtime hot-reloading.
"""

from .settings import (
    PromptPlotConfig,
    LLMConfig,
    PlotterConfig,
    PaperConfig,
    PaperSize,
    PaperOrientation,
    Units,
    VisualizationConfig,
    WorkflowConfig,
    VisionConfig,
    ConfigFormat,
    ValidationLevel,
    get_config,
    load_config,
    save_config,
    reset_config,
    validate_config
)

from .profiles import (
    ConfigurationProfile,
    ProfileManager,
    ProfileType,
    InheritanceMode,
    get_profile_manager,
    switch_profile,
    get_active_profile,
    list_profiles,
    create_profile
)

from .runtime import (
    RuntimeConfigManager,
    ConfigChangeType,
    UpdateResult,
    get_runtime_manager,
    start_runtime_config,
    stop_runtime_config,
    update_config_field,
    register_change_callback
)

__all__ = [
    # Core configuration
    "PromptPlotConfig",
    "LLMConfig", 
    "PlotterConfig",
    "PaperConfig",
    "PaperSize",
    "PaperOrientation", 
    "Units",
    "VisualizationConfig",
    "WorkflowConfig",
    "VisionConfig",
    "ConfigFormat",
    "ValidationLevel",
    "get_config",
    "load_config",
    "save_config",
    "reset_config",
    "validate_config",
    
    # Profiles
    "ConfigurationProfile",
    "ProfileManager",
    "ProfileType",
    "InheritanceMode",
    "get_profile_manager",
    "switch_profile",
    "get_active_profile",
    "list_profiles",
    "create_profile",
    
    # Runtime management
    "RuntimeConfigManager",
    "ConfigChangeType",
    "UpdateResult",
    "get_runtime_manager",
    "start_runtime_config",
    "stop_runtime_config",
    "update_config_field",
    "register_change_callback"
]