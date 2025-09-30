"""
Centralized exception handling for PromptPlot v2.0

This module contains the custom exception hierarchy that replaces scattered
exception handling throughout the codebase with a centralized approach,
providing proper error context and recovery mechanisms.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime


class PromptPlotException(Exception):
    """
    Base exception for all PromptPlot system errors
    
    Provides a foundation for structured error handling with context
    and recovery information.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, 
                 recovery_suggestions: Optional[List[str]] = None):
        """
        Initialize the base exception
        
        Args:
            message: Human-readable error message
            details: Additional error context and debugging information
            recovery_suggestions: List of suggested recovery actions
        """
        self.message = message
        self.details = details or {}
        self.recovery_suggestions = recovery_suggestions or []
        self.timestamp = datetime.now().isoformat()
        
        # Add system context to details
        self.details.update({
            "timestamp": self.timestamp,
            "exception_type": self.__class__.__name__
        })
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization"""
        return {
            "message": self.message,
            "details": self.details,
            "recovery_suggestions": self.recovery_suggestions,
            "timestamp": self.timestamp,
            "exception_type": self.__class__.__name__
        }
    
    def __str__(self) -> str:
        """Enhanced string representation with context"""
        base_msg = self.message
        if self.details:
            context_items = [f"{k}: {v}" for k, v in self.details.items() 
                           if k not in ["timestamp", "exception_type"]]
            if context_items:
                base_msg += f" (Context: {', '.join(context_items)})"
        return base_msg


class LLMException(PromptPlotException):
    """
    Exception for LLM-related errors
    
    Handles errors from language model interactions including API failures,
    timeout errors, and response validation issues.
    """
    
    def __init__(self, message: str, llm_provider: Optional[str] = None,
                 model_name: Optional[str] = None, prompt: Optional[str] = None,
                 response: Optional[str] = None, **kwargs):
        """
        Initialize LLM exception with provider-specific context
        
        Args:
            message: Error message
            llm_provider: Name of the LLM provider (e.g., "ollama", "azure_openai")
            model_name: Name of the model being used
            prompt: The prompt that caused the error (truncated for logging)
            response: The response that caused the error (truncated for logging)
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "llm_provider": llm_provider,
            "model_name": model_name,
            "prompt_length": len(prompt) if prompt else 0,
            "response_length": len(response) if response else 0
        })
        
        # Truncate long strings for logging
        if prompt and len(prompt) > 500:
            details["prompt_preview"] = prompt[:500] + "..."
        elif prompt:
            details["prompt_preview"] = prompt
            
        if response and len(response) > 500:
            details["response_preview"] = response[:500] + "..."
        elif response:
            details["response_preview"] = response
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check LLM provider configuration and API keys",
            "Verify network connectivity to LLM service",
            "Try reducing prompt complexity or length",
            "Consider switching to a different LLM provider",
            "Check if the model supports the requested operation"
        ])
        
        super().__init__(message, details, recovery_suggestions)


class VisionException(PromptPlotException):
    """
    Exception for computer vision errors
    
    Handles errors from image processing, camera interface, and visual
    feedback analysis operations.
    """
    
    def __init__(self, message: str, operation: Optional[str] = None,
                 image_source: Optional[str] = None, image_format: Optional[str] = None,
                 **kwargs):
        """
        Initialize vision exception with image processing context
        
        Args:
            message: Error message
            operation: The vision operation that failed (e.g., "capture", "process", "analyze")
            image_source: Source of the image (e.g., "camera", "file", "url")
            image_format: Format of the image (e.g., "PNG", "JPEG")
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "operation": operation,
            "image_source": image_source,
            "image_format": image_format
        })
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check camera connection and permissions",
            "Verify image file exists and is readable",
            "Ensure image format is supported",
            "Try reducing image resolution or quality",
            "Check available system memory for image processing"
        ])
        
        super().__init__(message, details, recovery_suggestions)


class PlotterException(PromptPlotException):
    """
    Exception for plotter communication and control errors
    
    Handles errors from serial communication, command execution,
    and plotter hardware interactions.
    """
    
    def __init__(self, message: str, plotter_type: Optional[str] = None,
                 port: Optional[str] = None, command: Optional[str] = None,
                 response: Optional[str] = None, **kwargs):
        """
        Initialize plotter exception with hardware context
        
        Args:
            message: Error message
            plotter_type: Type of plotter ("real", "simulated")
            port: Serial port or connection identifier
            command: The command that caused the error
            response: The plotter's response (if any)
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "plotter_type": plotter_type,
            "port": port,
            "command": command,
            "response": response
        })
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check plotter power and connection",
            "Verify serial port configuration and permissions",
            "Try reconnecting to the plotter",
            "Check for hardware errors or obstructions",
            "Verify G-code command syntax and parameters"
        ])
        
        super().__init__(message, details, recovery_suggestions)


class PlotterConnectionException(PlotterException):
    """
    Specific exception for plotter connection errors
    
    Raised when connection to plotter fails or is lost.
    """
    
    def __init__(self, message: str, **kwargs):
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check plotter power and USB/serial connection",
            "Verify correct port is specified",
            "Check port permissions (may need sudo/admin rights)",
            "Try different USB port or cable",
            "Restart plotter hardware"
        ])
        kwargs['recovery_suggestions'] = recovery_suggestions
        super().__init__(message, **kwargs)


class PlotterCommandException(PlotterException):
    """
    Specific exception for plotter command errors
    
    Raised when G-code command sending or execution fails.
    """
    
    def __init__(self, message: str, **kwargs):
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Verify G-code command syntax",
            "Check if plotter is ready to receive commands",
            "Ensure command parameters are within valid ranges",
            "Try sending a simpler test command first",
            "Check plotter firmware compatibility"
        ])
        kwargs['recovery_suggestions'] = recovery_suggestions
        super().__init__(message, **kwargs)


class ValidationException(PromptPlotException):
    """
    Exception for G-code validation and data validation errors
    
    Handles errors from Pydantic model validation, G-code syntax checking,
    and data format validation.
    """
    
    def __init__(self, message: str, field: Optional[str] = None,
                 invalid_value: Any = None, expected_type: Optional[str] = None,
                 validation_context: Optional[str] = None, **kwargs):
        """
        Initialize validation exception with validation context
        
        Args:
            message: Error message
            field: The field that failed validation
            invalid_value: The value that failed validation
            expected_type: The expected type or format
            validation_context: Context where validation occurred
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "field": field,
            "invalid_value": str(invalid_value) if invalid_value is not None else None,
            "invalid_value_type": type(invalid_value).__name__ if invalid_value is not None else None,
            "expected_type": expected_type,
            "validation_context": validation_context
        })
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check data format and type requirements",
            "Verify all required fields are provided",
            "Ensure numeric values are within valid ranges",
            "Check for proper JSON syntax if applicable",
            "Review field validation rules and constraints"
        ])
        
        super().__init__(message, details, recovery_suggestions)


class WorkflowException(PromptPlotException):
    """
    Exception for workflow execution errors
    
    Handles errors from workflow state management, step execution,
    and workflow coordination issues. Enhanced from the existing
    WorkflowException in boilerplate files.
    """
    
    def __init__(self, message: str, workflow_name: Optional[str] = None,
                 current_step: Optional[str] = None, step_count: Optional[int] = None,
                 **kwargs):
        """
        Initialize workflow exception with execution context
        
        Args:
            message: Error message
            workflow_name: Name of the workflow that failed
            current_step: The step where the error occurred
            step_count: Number of steps completed before error
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "workflow_name": workflow_name,
            "current_step": current_step,
            "step_count": step_count
        })
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check workflow configuration and parameters",
            "Verify all required dependencies are available",
            "Try restarting the workflow from the beginning",
            "Check for resource constraints (memory, disk space)",
            "Review workflow logs for additional error details"
        ])
        
        super().__init__(message, details, recovery_suggestions)


class ConfigurationException(PromptPlotException):
    """
    Exception for configuration and settings errors
    
    Handles errors from configuration file parsing, environment variable
    validation, and system setup issues.
    """
    
    def __init__(self, message: str, config_file: Optional[str] = None,
                 config_key: Optional[str] = None, **kwargs):
        """
        Initialize configuration exception
        
        Args:
            message: Error message
            config_file: Path to configuration file that caused error
            config_key: Specific configuration key that failed
            **kwargs: Additional context passed to base class
        """
        details = kwargs.get('details', {})
        details.update({
            "config_file": config_file,
            "config_key": config_key
        })
        
        recovery_suggestions = kwargs.get('recovery_suggestions', [
            "Check configuration file syntax and format",
            "Verify all required configuration keys are present",
            "Check file permissions for configuration files",
            "Validate environment variable values",
            "Review configuration documentation and examples"
        ])
        
        super().__init__(message, details, recovery_suggestions)


# Error Recovery Utilities

class ErrorRecoveryManager:
    """
    Manages error recovery strategies and retry logic
    
    Provides centralized error recovery mechanisms that can be used
    across different components of the system.
    """
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.5):
        """
        Initialize error recovery manager
        
        Args:
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    async def retry_with_backoff(self, operation, *args, **kwargs):
        """
        Execute operation with exponential backoff retry
        
        Args:
            operation: Async function to retry
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of successful operation
            
        Raises:
            Last exception if all retries fail
        """
        import asyncio
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate backoff delay
                    delay = (self.backoff_factor ** attempt)
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    break
        
        # All retries failed, raise the last exception
        raise last_exception
    
    def should_retry(self, exception: Exception) -> bool:
        """
        Determine if an exception should trigger a retry
        
        Args:
            exception: The exception to evaluate
            
        Returns:
            True if retry is recommended, False otherwise
        """
        # Don't retry validation errors (they won't fix themselves)
        if isinstance(exception, ValidationException):
            return False
        
        # Don't retry configuration errors
        if isinstance(exception, ConfigurationException):
            return False
        
        # Retry LLM and plotter errors (might be transient)
        if isinstance(exception, (LLMException, PlotterException)):
            return True
        
        # Retry vision errors (might be temporary camera issues)
        if isinstance(exception, VisionException):
            return True
        
        # Default: retry workflow exceptions
        if isinstance(exception, WorkflowException):
            return True
        
        # Don't retry unknown exceptions
        return False


# Exception Context Manager

class ExceptionContext:
    """
    Context manager for enhanced exception handling
    
    Provides structured exception handling with automatic context
    capture and recovery suggestion generation.
    """
    
    def __init__(self, operation_name: str, **context):
        """
        Initialize exception context
        
        Args:
            operation_name: Name of the operation being performed
            **context: Additional context to capture
        """
        self.operation_name = operation_name
        self.context = context
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and not isinstance(exc_value, PromptPlotException):
            # Wrap non-PromptPlot exceptions with context
            enhanced_exception = PromptPlotException(
                message=f"Error in {self.operation_name}: {str(exc_value)}",
                details={
                    "operation": self.operation_name,
                    "original_exception": str(exc_value),
                    "original_exception_type": exc_type.__name__,
                    **self.context
                },
                recovery_suggestions=[
                    f"Review the {self.operation_name} operation for errors",
                    "Check system logs for additional details",
                    "Verify all prerequisites are met",
                    "Try the operation again with different parameters"
                ]
            )
            
            # Replace the original exception
            raise enhanced_exception from exc_value
        
        # Let PromptPlot exceptions pass through unchanged
        return False