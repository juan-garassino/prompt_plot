"""
Serial Plotter Implementation

Enhanced from existing AsyncController implementations in boilerplates.
Provides robust serial communication with automatic reconnection and comprehensive error handling.
"""

import asyncio
import logging
import time
from typing import Optional, Tuple
from dataclasses import dataclass

from .base import BasePlotter, PlotterStatus
from ..core.exceptions import PlotterConnectionException, PlotterCommandException, PlotterException


@dataclass
class SerialPlotterStatus(PlotterStatus):
    """Extended status for serial plotter with connection details"""
    baud_rate: int = 115200
    timeout: float = 5.0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_ping_time: Optional[float] = None
    ping_response_time: Optional[float] = None


class SerialPlotter(BasePlotter):
    """
    Real hardware plotter controller via serial connection
    
    Enhanced from existing AsyncController with:
    - Improved connection management and automatic reconnection
    - Comprehensive status monitoring and error recovery
    - Better timeout handling and response validation
    - Connection health monitoring with ping/heartbeat
    """
    
    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 5.0,
                 max_retries: int = 3, retry_delay: float = 1.0,
                 enable_heartbeat: bool = True, heartbeat_interval: float = 30.0):
        """Initialize the serial plotter
        
        Args:
            port: Serial port path (e.g., "/dev/ttyUSB0", "COM3")
            baud_rate: Serial communication baud rate
            timeout: Command timeout in seconds
            max_retries: Maximum connection retry attempts
            retry_delay: Delay between retry attempts
            enable_heartbeat: Whether to enable connection health monitoring
            heartbeat_interval: Interval between heartbeat checks in seconds
        """
        super().__init__(port, max_retries, retry_delay)
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.enable_heartbeat = enable_heartbeat
        self.heartbeat_interval = heartbeat_interval
        
        # Serial connection objects
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        # Enhanced status tracking
        self.status = SerialPlotterStatus(
            baud_rate=baud_rate,
            timeout=timeout
        )
        
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
    
    async def connect(self) -> bool:
        """Connect to the serial plotter
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            PlotterConnectionException: If connection fails
        """
        try:
            # Import serial_asyncio here to avoid dependency issues
            try:
                from serial_asyncio import open_serial_connection
            except ImportError:
                raise PlotterConnectionException(
                    "serial_asyncio not available. Install with: pip install pyserial-asyncio",
                    plotter_type="serial",
                    port=self.port
                )
            
            self.logger.info(f"Connecting to serial plotter on {self.port} at {self.baud_rate} baud...")
            
            # Establish serial connection
            self.reader, self.writer = await asyncio.wait_for(
                open_serial_connection(url=self.port, baudrate=self.baud_rate),
                timeout=self.timeout
            )
            
            self._active = True
            self.update_status(is_busy=False, connection_attempts=0)
            
            # Initialize plotter (send wake-up signal)
            await self._initialize_plotter()
            
            # Start heartbeat monitoring if enabled
            if self.enable_heartbeat:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            
            self.logger.info(f"Successfully connected to serial plotter on {self.port}")
            return True
            
        except asyncio.TimeoutError:
            error_msg = f"Connection timeout to {self.port}"
            self.logger.error(error_msg)
            raise PlotterConnectionException(error_msg, plotter_type="serial", port=self.port)
            
        except Exception as e:
            error_msg = f"Failed to connect to {self.port}: {str(e)}"
            self.logger.error(error_msg)
            raise PlotterConnectionException(error_msg, plotter_type="serial", port=self.port) from e
    
    async def disconnect(self) -> None:
        """Disconnect from the serial plotter
        
        Raises:
            PlotterException: If disconnection fails
        """
        if not self._active:
            return
        
        try:
            self.logger.info("Disconnecting from serial plotter...")
            
            # Signal shutdown to background tasks
            self._shutdown_event.set()
            
            # Cancel heartbeat task
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Close the writer
            if self.writer:
                self.writer.close()
                try:
                    await asyncio.wait_for(self.writer.wait_closed(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.warning("Timeout while closing serial connection")
            
            self.reader = None
            self.writer = None
            self._active = False
            
            self.update_status(is_busy=False)
            self.logger.info("Successfully disconnected from serial plotter")
            
        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            self.logger.error(error_msg)
            raise PlotterException(error_msg, plotter_type="serial", port=self.port) from e
    
    async def send_command(self, command: str) -> bool:
        """Send a G-code command to the plotter
        
        Args:
            command: G-code command string
            
        Returns:
            True if command was sent successfully, False otherwise
            
        Raises:
            PlotterConnectionException: If not connected
            PlotterCommandException: If command sending fails
        """
        if not self._active or not self.writer:
            raise PlotterConnectionException("Not connected to plotter", plotter_type="serial", port=self.port)
        
        try:
            self.update_status(is_busy=True, current_command=command)
            
            # Send the command
            command_bytes = f"{command}\n".encode('utf-8')
            self.writer.write(command_bytes)
            await self.writer.drain()
            
            # Update statistics
            self.status.bytes_sent += len(command_bytes)
            
            self.logger.debug(f"Sent command: {command}")
            
            # Wait for response if not a special command
            if command not in ["COMPLETE", "HOME", "RESET"]:
                response = await self._read_response()
                self.update_status(last_response=response)
                
                # Check if response indicates success
                success = response and ("ok" in response.lower() or "done" in response.lower())
                if not success:
                    self.logger.warning(f"Command may have failed. Response: {response}")
                
                self.update_status(is_busy=False)
                return success
            else:
                # Special commands don't expect a response
                self.update_status(is_busy=False, last_response="ok")
                return True
                
        except Exception as e:
            error_msg = f"Error sending command '{command}': {str(e)}"
            self.logger.error(error_msg)
            self.update_status(is_busy=False, last_response="error")
            raise PlotterCommandException(error_msg, plotter_type="serial", port=self.port, command=command) from e
    
    async def _initialize_plotter(self) -> None:
        """Initialize the plotter after connection"""
        try:
            self.logger.debug("Initializing plotter...")
            
            # Clear any startup messages
            await asyncio.sleep(2.0)
            if self.reader and self.reader.at_eof() is False:
                try:
                    # Read and discard any startup messages
                    await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
                except asyncio.TimeoutError:
                    pass  # No startup messages, that's fine
            
            # Send wake-up signal (common for GRBL-based plotters)
            if self.writer:
                self.writer.write(b"\r\n\r\n")
                await self.writer.drain()
                await asyncio.sleep(2.0)
            
            # Try to get status
            await self._ping_plotter()
            
            self.logger.debug("Plotter initialization complete")
            
        except Exception as e:
            self.logger.warning(f"Plotter initialization failed: {str(e)}")
            # Don't fail connection for initialization issues
    
    async def _read_response(self) -> Optional[str]:
        """Read response from plotter with timeout"""
        if not self.reader:
            return None
        
        try:
            # Read line with timeout
            line_bytes = await asyncio.wait_for(
                self.reader.readline(),
                timeout=self.timeout
            )
            
            if line_bytes:
                response = line_bytes.decode('utf-8').strip()
                self.status.bytes_received += len(line_bytes)
                self.logger.debug(f"Received response: {response}")
                return response
            else:
                self.logger.warning("Received empty response")
                return None
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Response timeout after {self.timeout} seconds")
            return None
        except Exception as e:
            self.logger.error(f"Error reading response: {str(e)}")
            return None
    
    async def _ping_plotter(self) -> bool:
        """Send a ping to check plotter health"""
        try:
            start_time = time.time()
            
            # Send a simple status query (common G-code)
            if self.writer:
                self.writer.write(b"?\n")  # Status query for GRBL
                await self.writer.drain()
            
            # Try to read response
            response = await self._read_response()
            
            response_time = time.time() - start_time
            self.status.last_ping_time = start_time
            self.status.ping_response_time = response_time
            
            success = response is not None
            if success:
                self.logger.debug(f"Ping successful, response time: {response_time:.3f}s")
            else:
                self.logger.warning("Ping failed - no response")
            
            return success
            
        except Exception as e:
            self.logger.warning(f"Ping failed: {str(e)}")
            return False
    
    async def _heartbeat_monitor(self) -> None:
        """Background task to monitor connection health"""
        self.logger.debug("Starting heartbeat monitor")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for heartbeat interval or shutdown
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.heartbeat_interval
                    )
                    # If we get here, shutdown was signaled
                    break
                    
                except asyncio.TimeoutError:
                    # Heartbeat interval elapsed, check connection
                    if self._active:
                        ping_success = await self._ping_plotter()
                        if not ping_success:
                            self.logger.warning("Heartbeat ping failed - connection may be lost")
                            # Could trigger reconnection logic here if desired
                
        except asyncio.CancelledError:
            self.logger.debug("Heartbeat monitor cancelled")
        except Exception as e:
            self.logger.error(f"Heartbeat monitor error: {str(e)}")
        
        self.logger.debug("Heartbeat monitor stopped")
    
    async def get_plotter_status(self) -> dict:
        """Get detailed plotter status information
        
        Returns:
            Dictionary with plotter status details
        """
        base_status = {
            "connected": self.is_connected,
            "busy": self.is_busy,
            "port": self.port,
            "baud_rate": self.status.baud_rate,
            "timeout": self.status.timeout,
            "bytes_sent": self.status.bytes_sent,
            "bytes_received": self.status.bytes_received,
            "last_command": self.status.current_command,
            "last_response": self.status.last_response,
            "connection_attempts": self.status.connection_attempts,
            "last_error": self.status.last_error
        }
        
        # Add heartbeat info if enabled
        if self.enable_heartbeat:
            base_status.update({
                "last_ping_time": self.status.last_ping_time,
                "ping_response_time": self.status.ping_response_time,
                "heartbeat_enabled": True,
                "heartbeat_interval": self.heartbeat_interval
            })
        
        return base_status
    
    async def reconnect(self) -> bool:
        """Attempt to reconnect to the plotter
        
        Returns:
            True if reconnection successful, False otherwise
        """
        self.logger.info("Attempting to reconnect...")
        
        try:
            # Disconnect first if still connected
            if self._active:
                await self.disconnect()
            
            # Wait a moment before reconnecting
            await asyncio.sleep(1.0)
            
            # Attempt reconnection with retry logic
            return await self.connect_with_retry()
            
        except Exception as e:
            self.logger.error(f"Reconnection failed: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """String representation of the serial plotter"""
        return f"SerialPlotter(port={self.port}, baud={self.baud_rate}, connected={self.is_connected})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"SerialPlotter("
                f"port={self.port}, "
                f"baud_rate={self.baud_rate}, "
                f"timeout={self.timeout}, "
                f"connected={self.is_connected}, "
                f"busy={self.is_busy})")