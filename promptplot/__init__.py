"""
PromptPlot v2.0 - LLM-controlled pen plotter system

A modular, extensible pen plotter control system that transforms natural language
prompts into G-code instructions through intelligent LLM processing and computer
vision feedback.
"""

__version__ = "2.0.0"
__author__ = "PromptPlot Team"

# Import core components for easy access
from .core import (
    GCodeCommand,
    GCodeProgram,
    BasePromptPlotWorkflow,
    DrawingStrategy,
    PromptPlotException,
    ValidationError,
    WorkflowResult
)

# Import strategy components
from .strategies import (
    StrategySelector,
    PromptComplexity,
    ComplexityLevel,
    OrthogonalStrategy,
    NonOrthogonalStrategy
)

# Import configuration system
from .config import (
    PromptPlotConfig,
    get_config,
    load_config,
    save_config,
    get_profile_manager,
    switch_profile
)

# Import LLM providers
from .llm import (
    LLMProvider,
    AzureOpenAIProvider,
    OllamaProvider,
    PromptTemplateManager
)

# Import workflows
from .workflows import (
    SimpleGCodeWorkflow,
    SequentialGCodeWorkflow,
    SimplePlotterStreamWorkflow,
    AdvancedPlotterStreamWorkflow,
    FilePlottingWorkflow
)

# Import converters
from .converters import (
    FileFormatDetector,
    SVGConverter,
    GCodeLoader,
    DXFConverter
)

__all__ = [
    # Core components
    'GCodeCommand',
    'GCodeProgram', 
    'BasePromptPlotWorkflow',
    'DrawingStrategy',
    'PromptPlotException',
    'ValidationError',
    'WorkflowResult',
    
    # Strategy system
    'StrategySelector',
    'PromptComplexity',
    'ComplexityLevel',
    'OrthogonalStrategy',
    'NonOrthogonalStrategy',
    
    # Configuration
    'PromptPlotConfig',
    'get_config',
    'load_config',
    'save_config',
    'get_profile_manager',
    'switch_profile',
    
    # LLM providers
    'LLMProvider',
    'AzureOpenAIProvider',
    'OllamaProvider',
    'PromptTemplateManager',
    
    # Workflows
    'SimpleGCodeWorkflow',
    'SequentialGCodeWorkflow',
    'SimplePlotterStreamWorkflow',
    'AdvancedPlotterStreamWorkflow',
    'FilePlottingWorkflow',
    
    # File converters
    'FileFormatDetector',
    'SVGConverter',
    'GCodeLoader',
    'DXFConverter'
]