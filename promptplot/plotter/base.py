"""
Base Plotter Interface

Extracted from common patterns in existing plotter implementations.
Provides a unified interface for all plotter types with consistent error handling.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time
import logging
from ..core.exceptions import PlotterException, PlotterConnectionException, PlotterCommandException


@dataclass
class PlotterStatus:
    """Tracks the current status of the plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    queue_size: int = 0
    last_update: float = time.time()
    connection_attempts: int = 0
    last_error: Optional[str] = None


class BasePlotter(ABC):
    """
    Base interface for all plotter implementations
    
    Extracted from common patterns in RealPenPlotter and SimulatedPenPlotter
    to provide a consistent interface across different plotter types.
    
    Features:
    - Context manager support for automatic connection/disconnection
    - Consistent error handling with custom exceptions
    - Status monitoring and logging
    - Command validation and formatting
    - Automatic reconnection capabilities
    """
    
    def __init__(self, port: str, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize the plotter with a port identifier
        
        Args:
            port: Port identifier (e.g., "/dev/ttyUSB0" or "SIMULATED")
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay between retry attempts in seconds
        """
        self.port = port
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.status = PlotterStatus()
        self._active = False
        self.logger = logging.getLogger(f"{self.__class__.__name__}({port})")
        self.command_history: List[str] = []

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the plotter
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            PlotterConnectionException: If connection fails after all retries
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the plotter
        
        Raises:
            PlotterException: If disconnection fails
        """
        pass

    @abstractmethod
    async def send_command(self, command: str) -> bool:
        """Send a G-code command to the plotter
        
        Args:
            command: G-code command string
            
        Returns:
            True if command was sent successfully, False otherwise
            
        Raises:
            PlotterCommandException: If command sending fails
            PlotterConnectionException: If not connected
        """
        pass

    async def connect_with_retry(self) -> bool:
        """Connect to the plotter with automatic retry logic
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            PlotterConnectionException: If all connection attempts fail
        """
        import asyncio
        
        for attempt in range(self.max_retries):
            self.status.connection_attempts = attempt + 1
            
            try:
                self.logger.info(f"Connection attempt {attempt + 1}/{self.max_retries}")
                success = await self.connect()
                
                if success:
                    self.logger.info("Connection successful")
                    self.status.last_error = None
                    return True
                    
            except Exception as e:
                error_msg = f"Connection attempt {attempt + 1} failed: {str(e)}"
                self.logger.warning(error_msg)
                self.status.last_error = error_msg
                
                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
        
        # All attempts failed
        final_error = f"Failed to connect after {self.max_retries} attempts"
        self.logger.error(final_error)
        raise PlotterConnectionException(final_error)

    async def send_command_safe(self, command: str) -> bool:
        """Send a command with error handling and logging
        
        Args:
            command: G-code command string
            
        Returns:
            True if command was sent successfully, False otherwise
            
        Raises:
            PlotterConnectionException: If not connected
            PlotterCommandException: If command is invalid or sending fails
        """
        if not self.is_connected:
            raise PlotterConnectionException("Not connected to plotter")
        
        # Validate command format
        if not self.validate_command(command):
            raise PlotterCommandException(f"Invalid command format: {command}")
        
        # Log the command
        self.logger.debug(f"Sending command: {command}")
        self.command_history.append(command)
        
        try:
            result = await self.send_command(command)
            if result:
                self.logger.debug(f"Command sent successfully: {command}")
            else:
                self.logger.warning(f"Command failed: {command}")
            return result
            
        except Exception as e:
            error_msg = f"Error sending command '{command}': {str(e)}"
            self.logger.error(error_msg)
            self.status.last_error = error_msg
            raise PlotterCommandException(error_msg) from e

    def format_command(self, command_dict: Dict[str, Any]) -> str:
        """Convert command dictionary to G-code string
        
        Common formatting logic extracted from existing implementations.
        
        Args:
            command_dict: Dictionary containing command and parameters
            
        Returns:
            Formatted G-code string
        """
        if command_dict.get("command") == "COMPLETE":
            return "COMPLETE"
            
        gcode = command_dict["command"]
        for key, value in command_dict.items():
            if key != "command" and value is not None:
                if isinstance(value, float):
                    gcode += f" {key.upper()}{value:.3f}"
                else:
                    gcode += f" {key.upper()}{value}"
        return gcode

    def validate_command(self, command: str) -> bool:
        """Validate G-code command format
        
        Args:
            command: G-code command string
            
        Returns:
            True if command is valid, False otherwise
        """
        if not command or not isinstance(command, str):
            return False
            
        command = command.strip()
        if not command:
            return False
            
        # Special commands
        if command in ["COMPLETE", "HOME", "RESET"]:
            return True
            
        # G-code commands should start with a letter
        if not command[0].isalpha():
            return False
            
        return True

    def get_command_history(self, limit: Optional[int] = None) -> List[str]:
        """Get command history
        
        Args:
            limit: Maximum number of commands to return (None for all)
            
        Returns:
            List of recent commands
        """
        if limit is None:
            return self.command_history.copy()
        return self.command_history[-limit:]

    def clear_command_history(self) -> None:
        """Clear the command history"""
        self.command_history.clear()
        self.logger.debug("Command history cleared")

    @property
    def is_connected(self) -> bool:
        """Check if plotter is connected"""
        return self._active

    @property
    def is_busy(self) -> bool:
        """Check if plotter is busy executing commands"""
        return self.status.is_busy

    def update_status(self, **kwargs) -> None:
        """Update plotter status
        
        Args:
            **kwargs: Status fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)
        self.status.last_update = time.time()

    async def __aenter__(self):
        """Context manager entry - connect to plotter with retry logic"""
        await self.connect_with_retry()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Context manager exit - disconnect from plotter"""
        try:
            await self.disconnect()
        except Exception as e:
            self.logger.error(f"Error during disconnect: {str(e)}")
            # Don't raise exception in __aexit__ unless it's critical

    def __str__(self) -> str:
        """String representation of the plotter"""
        return f"{self.__class__.__name__}(port={self.port}, connected={self.is_connected})"

    def __repr__(self) -> str:
        """Detailed string representation of the plotter"""
        return (f"{self.__class__.__name__}("
                f"port={self.port}, "
                f"connected={self.is_connected}, "
                f"busy={self.is_busy})")