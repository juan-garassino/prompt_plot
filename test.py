#!/usr/bin/env python3
import asyncio
import logging
import argparse
import os
import tempfile
from serial_asyncio import open_serial_connection
import logging
from colorama import Fore, Style, init
from dataclasses import dataclass
from typing import Optional, List
import time
from collections import deque

init(autoreset=True)

@dataclass
class PlotterStatus:
    """Tracks the current status of the plotter"""
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    queue_size: int = 0
    last_update: float = time.time()

class Dispatcher:
    """Manages the real-time streaming of plotting tasks."""

    def __init__(self, max_buffer_size=5, command_delay=0.1):
        self.command_queue = deque(maxlen=max_buffer_size)
        self.max_buffer_size = max_buffer_size
        self.command_delay = command_delay
        self.status = PlotterStatus()
        self.logger = logging.getLogger(__name__)
        self._active = False
        self._processing = False

    def is_buffer_full(self) -> bool:
        """Check if the command buffer is full"""
        return len(self.command_queue) >= self.max_buffer_size

    async def add_command(self, command: str) -> bool:
        """Add a command to the queue if there's space"""
        if self.is_buffer_full():
            await asyncio.sleep(self.command_delay)
            if self.is_buffer_full():
                return False
        
        self.command_queue.append(command)
        self.status.queue_size = len(self.command_queue)
        return True

    async def get_next_command(self) -> Optional[str]:
        """Get the next command from the queue"""
        if self.command_queue:
            command = self.command_queue.popleft()
            self.status.queue_size = len(self.command_queue)
            return command
        return None

    async def process_file(self, filename: str) -> bool:
        """Process a GCode file line by line without loading it entirely into memory"""
        self._active = True
        self._processing = True
        
        try:
            with open(filename, 'r') as f:
                while self._active:
                    # Read a chunk of lines
                    lines = []
                    for _ in range(self.max_buffer_size * 2):  # Read ahead
                        line = f.readline()
                        if not line:
                            break
                        line = line.strip()
                        if line and not line.startswith(';'):
                            lines.append(line)
                    
                    if not lines:
                        break  # End of file
                    
                    # Add lines to queue with backpressure
                    for line in lines:
                        while self._active:
                            if await self.add_command(line):
                                break
                            await asyncio.sleep(self.command_delay)
                    
                    # Give time for processing
                    await asyncio.sleep(self.command_delay)
            
            # Wait for queue to empty
            while self._active and self.command_queue:
                await asyncio.sleep(self.command_delay)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error processing file: {str(e)}")
            return False
        finally:
            self._processing = False
            self._active = False

    def stop_processing(self):
        """Stop processing commands"""
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_processing(self) -> bool:
        return self._processing

class AsyncController:
    def __init__(self, port: str, baud_rate: int):
        self.port = port
        self.baud_rate = baud_rate
        self.reader = None
        self.writer = None
        self.logger = logging.getLogger(__name__)
        self.dispatcher = Dispatcher()
        self._active = False

    async def wire_up(self) -> bool:
        """Establish connection with the plotter"""
        try:
            self.reader, self.writer = await open_serial_connection(
                url=self.port, baudrate=self.baud_rate)
            self.logger.info(f"Connection established on {self.port}")
            self._active = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to open serial port: {e}")
            return False

    async def send_signal(self, signal: str) -> Optional[str]:
        """Send a single command and wait for response"""
        if not self.writer:
            self.logger.error("Cannot send signal: Not connected to the plotter.")
            return None

        try:
            self.writer.write(f"{signal}\n".encode())
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            return response.decode().strip()
        except asyncio.TimeoutError:
            self.logger.error("Timeout waiting for plotter response")
            return None
        except Exception as e:
            self.logger.error(f"Error sending signal to plotter: {e}")
            return None

    async def stream_file(self, filename: str):
        """Stream a GCode file through the dispatcher"""
        if not self._active:
            self.logger.error("Controller is not active")
            return False

        # Start file processing in background
        process_task = asyncio.create_task(self.dispatcher.process_file(filename))
        
        try:
            while self.dispatcher.is_active or self.dispatcher.command_queue:
                command = await self.dispatcher.get_next_command()
                if command:
                    self.logger.debug(f"Sending command: {command}")
                    response = await self.send_signal(command)
                    if response is None:  # Command failed
                        self.dispatcher.stop_processing()
                        return False
                    
                    # Update status
                    self.dispatcher.status.last_response = response
                    self.dispatcher.status.current_command = command
                    self.dispatcher.status.last_update = time.time()
                    
                    # Visual feedback
                    print(f"\r{Fore.CYAN}📡 Queue: {self.dispatcher.status.queue_size} | Last: {command[:30]}...{Style.RESET_ALL}", end='')
                
                await asyncio.sleep(self.dispatcher.command_delay)
            
            print("\n")  # Clear the last status line
            return True

        except Exception as e:
            self.logger.error(f"Error during streaming: {e}")
            self.dispatcher.stop_processing()
            return False
        finally:
            # Ensure process task is completed
            if not process_task.done():
                process_task.cancel()
                try:
                    await process_task
                except asyncio.CancelledError:
                    pass

    async def disconnect(self):
        """Disconnect from the plotter"""
        self._active = False
        self.dispatcher.stop_processing()
        
        if self.writer:
            self.writer.close()
            try:
                await asyncio.wait_for(self.writer.wait_closed(), timeout=5.0)
                self.logger.info("Serial connection closed")
            except asyncio.TimeoutError:
                self.logger.warning("Timeout while closing serial connection")
        
        self.reader = None
        self.writer = None

    async def __aenter__(self):
        await self.wire_up()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()


def generate_square_gcode(x_start=10, y_start=10, size=50, file_path=None):
    """Generate GCode for drawing a square
    
    Args:
        x_start: Starting X coordinate
        y_start: Starting Y coordinate
        size: Size of the square
        file_path: Path to save the GCode file (if None, a temporary file is created)
        
    Returns:
        Path to the generated GCode file
    """
    if file_path is None:
        fd, file_path = tempfile.mkstemp(suffix='.gcode')
        os.close(fd)
    
    with open(file_path, 'w') as f:
        # GCode header
        f.write("; GCode for drawing a square\n")
        f.write("; Generated by Pen Plotter Square Script\n")
        f.write("\n")
        
        # Setup - home and set speed
        f.write("G21 ; Set units to millimeters\n")
        f.write("G90 ; Set absolute positioning\n")
        f.write("G92 X0 Y0 ; Set current position as origin\n")
        f.write("G1 F3000 ; Set feed rate (speed)\n")
        
        # Lift pen (Z up) - assuming Z controls pen up/down
        f.write("G1 Z5 ; Lift pen\n")
        
        # Move to starting position
        f.write(f"G1 X{x_start} Y{y_start} ; Move to starting position\n")
        
        # Lower pen (Z down)
        f.write("G1 Z0 ; Lower pen\n")
        
        # Draw square
        f.write(f"G1 X{x_start + size} Y{y_start} ; Draw bottom line\n")
        f.write(f"G1 X{x_start + size} Y{y_start + size} ; Draw right line\n")
        f.write(f"G1 X{x_start} Y{y_start + size} ; Draw top line\n")
        f.write(f"G1 X{x_start} Y{y_start} ; Draw left line (complete square)\n")
        
        # Lift pen again
        f.write("G1 Z5 ; Lift pen\n")
        
        # Return to home
        f.write("G1 X0 Y0 ; Return to home position\n")
    
    print(f"GCode for square generated and saved to {file_path}")
    return file_path


async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Stream GCode for a square to pen plotter')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port connected to plotter')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate for serial connection')
    parser.add_argument('--size', type=int, default=50, help='Size of square in mm')
    parser.add_argument('--x', type=int, default=10, help='X starting position in mm')
    parser.add_argument('--y', type=int, default=10, help='Y starting position in mm')
    parser.add_argument('--output', help='Output path for GCode file (optional)')
    args = parser.parse_args()
    
    # Generate GCode for a square
    gcode_file = generate_square_gcode(
        x_start=args.x,
        y_start=args.y,
        size=args.size,
        file_path=args.output
    )
    
    print(f"{Fore.GREEN}Connecting to plotter on {args.port} at {args.baud} baud...{Style.RESET_ALL}")
    
    # Create controller and connect to plotter
    async with AsyncController(args.port, args.baud) as controller:
        if controller._active:
            print(f"{Fore.GREEN}Connected! Starting to stream GCode...{Style.RESET_ALL}")
            result = await controller.stream_file(gcode_file)
            
            if result:
                print(f"{Fore.GREEN}✅ Square drawing completed successfully!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Failed to complete the drawing.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Failed to connect to the plotter.{Style.RESET_ALL}")
    
    # Clean up temp file if we created one
    if args.output is None:
        try:
            os.remove(gcode_file)
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())