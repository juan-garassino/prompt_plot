"""
Centralized logging configuration for PromptPlot v2.0

This module provides a unified logging system with configurable levels,
formatters, and output destinations for all PromptPlot components.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

from ..config import get_config


class LogLevel(str, Enum):
    """Available logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Available log formats"""
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"
    COLORED = "colored"


class PromptPlotLogger:
    """Centralized logger for PromptPlot system"""
    
    _instance: Optional['PromptPlotLogger'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'PromptPlotLogger':
        """Singleton pattern for logger instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize logger configuration"""
        if not self._initialized:
            self.config = get_config()
            self.loggers: Dict[str, logging.Logger] = {}
            self._setup_logging()
            self._initialized = True
    
    def _setup_logging(self) -> None:
        """Set up logging configuration"""
        # Create logs directory if it doesn't exist
        log_dir = Path("results/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger("promptplot")
        root_logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.config.log_level.upper()))
        console_handler.setFormatter(self._get_formatter("colored"))
        root_logger.addHandler(console_handler)
        
        # Add file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "promptplot.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self._get_formatter("detailed"))
        root_logger.addHandler(file_handler)
        
        # Add error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "promptplot_errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(self._get_formatter("detailed"))
        root_logger.addHandler(error_handler)
        
        # Store root logger
        self.loggers["root"] = root_logger
    
    def _get_formatter(self, format_type: str) -> logging.Formatter:
        """Get formatter based on type"""
        if format_type == "simple":
            return logging.Formatter('%(levelname)s: %(message)s')
        elif format_type == "detailed":
            return logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
        elif format_type == "json":
            return JsonFormatter()
        elif format_type == "colored":
            return ColoredFormatter()
        else:
            return logging.Formatter('%(levelname)s: %(message)s')
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger for a specific component"""
        if name not in self.loggers:
            logger = logging.getLogger(f"promptplot.{name}")
            self.loggers[name] = logger
        return self.loggers[name]
    
    def set_level(self, level: Union[str, LogLevel]) -> None:
        """Set logging level for all loggers"""
        if isinstance(level, str):
            level = LogLevel(level.upper())
        
        log_level = getattr(logging, level.value)
        for logger in self.loggers.values():
            logger.setLevel(log_level)
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(log_level)
    
    def add_file_handler(self, filepath: Union[str, Path], level: Union[str, LogLevel] = LogLevel.INFO) -> None:
        """Add additional file handler"""
        if isinstance(level, str):
            level = LogLevel(level.upper())
        
        handler = logging.FileHandler(filepath)
        handler.setLevel(getattr(logging, level.value))
        handler.setFormatter(self._get_formatter("detailed"))
        
        for logger in self.loggers.values():
            logger.addHandler(handler)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']
        
        # Format the message
        formatted = f"{log_color}[{record.levelname}]{reset_color} {record.getMessage()}"
        
        # Add location info for debug level
        if record.levelno <= logging.DEBUG:
            formatted += f" ({record.filename}:{record.lineno})"
        
        return formatted


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        import json
        
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'filename': record.filename,
            'lineno': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


# Global logger instance
_logger_instance: Optional[PromptPlotLogger] = None


def get_logger(name: str = "root") -> logging.Logger:
    """Get logger instance for a component
    
    Args:
        name: Component name (e.g., 'workflow', 'plotter', 'llm')
        
    Returns:
        Logger instance for the component
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PromptPlotLogger()
    return _logger_instance.get_logger(name)


def set_log_level(level: Union[str, LogLevel]) -> None:
    """Set global logging level
    
    Args:
        level: Log level to set
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PromptPlotLogger()
    _logger_instance.set_level(level)


def add_log_file(filepath: Union[str, Path], level: Union[str, LogLevel] = LogLevel.INFO) -> None:
    """Add additional log file
    
    Args:
        filepath: Path to log file
        level: Minimum log level for this file
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PromptPlotLogger()
    _logger_instance.add_file_handler(filepath, level)


def configure_logging(
    level: Union[str, LogLevel] = LogLevel.INFO,
    format_type: LogFormat = LogFormat.COLORED,
    log_file: Optional[Union[str, Path]] = None
) -> None:
    """Configure logging system
    
    Args:
        level: Global log level
        format_type: Log format to use
        log_file: Optional additional log file
    """
    global _logger_instance
    _logger_instance = PromptPlotLogger()
    _logger_instance.set_level(level)
    
    if log_file:
        _logger_instance.add_file_handler(log_file, level)


# Convenience functions for common logging operations
def log_workflow_start(workflow_name: str, prompt: str) -> None:
    """Log workflow start"""
    logger = get_logger("workflow")
    logger.info(f"Starting workflow: {workflow_name}")
    logger.debug(f"Prompt: {prompt}")


def log_workflow_complete(workflow_name: str, duration: float, commands_generated: int) -> None:
    """Log workflow completion"""
    logger = get_logger("workflow")
    logger.info(f"Workflow completed: {workflow_name} ({duration:.2f}s, {commands_generated} commands)")


def log_plotter_command(command: str, success: bool, response_time: float) -> None:
    """Log plotter command execution"""
    logger = get_logger("plotter")
    status = "SUCCESS" if success else "FAILED"
    logger.debug(f"Command {command} - {status} ({response_time:.3f}s)")


def log_llm_request(provider: str, model: str, prompt_length: int, response_time: float) -> None:
    """Log LLM request"""
    logger = get_logger("llm")
    logger.debug(f"LLM request: {provider}/{model} ({prompt_length} chars, {response_time:.2f}s)")


def log_error(component: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log error with context"""
    logger = get_logger(component)
    error_msg = f"Error in {component}: {str(error)}"
    if context:
        error_msg += f" | Context: {context}"
    logger.error(error_msg, exc_info=True)