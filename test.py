#!/usr/bin/env python3
#
# GRBL-based Pen Plotter G-code Streamer
#
import argparse
import os
import tempfile
import time
import sys

try:
    import serial
except ImportError:
    print("Error: The 'pyserial' package is required. Install it with 'pip install pyserial'")
    sys.exit(1)

# Terminal colors
class Colors:
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

# Tree symbols for structured logging
class TreeSymbols:
    BRANCH = "├── "
    LAST = "└── "
    PIPE = "│   "
    SPACE = "    "
    
    # Status indicators
    ACTION = "[*]"
    SUCCESS = "[+]"
    ERROR = "[!]"
    INFO = "[?]"
    WARNING = "[W]"

# Global debug flag
debug_mode = False
# Current indentation level
indent_level = 0
# Track if current item is last in its group
is_last_item = False

def print_tree(message, symbol=TreeSymbols.ACTION, is_last=False, level=0, status_color=Colors.CYAN):
    """Print a message in tree format with the specified indentation level"""
    prefix = ""
    
    # Build the prefix based on indentation level
    for i in range(level):
        if i == level - 1 and is_last:
            prefix += TreeSymbols.LAST
        elif i == level - 1:
            prefix += TreeSymbols.BRANCH
        else:
            prefix += TreeSymbols.PIPE
    
    # Print the message with appropriate formatting
    print(f"{prefix}{status_color}{symbol}{Colors.RESET} {message}")

def print_sub_message(message, symbol=TreeSymbols.INFO, is_last=True):
    """Print a sub-message (explanation, detail) with proper indentation"""
    global indent_level
    prefix = ""
    
    # Build proper indentation prefix
    for i in range(indent_level):
        prefix += TreeSymbols.PIPE
    
    if is_last:
        prefix += TreeSymbols.LAST
    else:
        prefix += TreeSymbols.BRANCH
    
    # Print with muted color for explanations
    print(f"{prefix}{Colors.CYAN}{symbol}{Colors.RESET} {message}")

class GrblPlotter:
    """Standard GRBL-compatible pen plotter controller"""
    
    def __init__(self, port, baud_rate=115200, timeout=0.1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial = None
        self.connected = False
    
    def connect(self):
        """Connect to the GRBL device"""
        global indent_level
        
        print_tree("Connecting to plotter", level=indent_level)
        indent_level += 1
        
        try:
            print_tree("Opening serial port", level=indent_level)
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                writeTimeout=self.timeout
            )
            
            print_tree("Initializing connection", level=indent_level)
            indent_level += 1
            
            # Clear startup text and wait for GRBL to initialize
            time.sleep(2)
            self.serial.flushInput()
            
            print_tree("Sending wake-up signal", level=indent_level)
            # Send a newline to wake up GRBL
            self.serial.write(b"\r\n\r\n")
            time.sleep(2)
            
            # Check if we get a response
            response = self.read_response()
            if response:
                print_sub_message(f"Received: {response}")
            
            # Get GRBL status
            print_tree("Getting device info", level=indent_level, is_last=True)
            response = self.send_command('$I', display_tree=False)
            if response:
                print_sub_message(f"Device info: {response}")
            
            indent_level -= 1
            
            self.connected = True
            print_tree("Connection established", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
            indent_level -= 1
            return True
        
        except Exception as e:
            print_tree(f"Connection failed: {e}", symbol=TreeSymbols.ERROR, level=indent_level, is_last=True, status_color=Colors.RED)
            indent_level -= 1
            
            if self.serial:
                self.serial.close()
                self.serial = None
            return False
    
    def disconnect(self):
        """Disconnect from the GRBL device"""
        if self.serial:
            global indent_level
            print_tree("Disconnecting from plotter", level=indent_level)
            indent_level += 1
            
            # Send the plotter back to origin
            try:
                print_tree("Sending to home position", level=indent_level)
                self.send_command("G0 X0 Y0", display_tree=False)
                print_tree("Turning off spindle", level=indent_level, is_last=True)
                self.send_command("M5", display_tree=False)  # Turn off spindle (pen up for some plotters)
            except:
                pass
            
            self.serial.close()
            self.serial = None
            self.connected = False
            
            print_tree("Disconnected successfully", symbol=TreeSymbols.SUCCESS, is_last=True, level=indent_level-1, status_color=Colors.GREEN)
            indent_level -= 1
    
    def read_response(self, timeout=1.0):
        """Read response from GRBL, with timeout"""
        if not self.serial:
            return None
        
        response = ""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode('utf-8').strip()
                if line:
                    response += line + "\n"
                    if line == "ok" or line.startswith("error:"):
                        break
            time.sleep(0.01)
        
        return response.strip()
    
    def send_command(self, command, wait_for_ok=True, display_tree=True):
        """Send a command to GRBL and wait for response"""
        if not self.serial:
            if display_tree:
                print_tree("Not connected to plotter", symbol=TreeSymbols.ERROR, status_color=Colors.RED)
            return None
        
        # Log the command if needed
        if display_tree and debug_mode:
            print_tree(f"CMD: {command}", symbol=TreeSymbols.ACTION)
        
        # Send the command
        self.serial.write(f"{command}\n".encode())
        self.serial.flush()
        
        # Wait for response
        if wait_for_ok:
            response = self.read_response()
            if display_tree and debug_mode:
                if response and response.startswith("error:"):
                    print_tree(f"Error: {response}", symbol=TreeSymbols.WARNING, status_color=Colors.YELLOW)
                elif debug_mode:
                    print_sub_message(f"Response: {response}")
            return response
        return None
    
    def stream_file(self, filename):
        """Stream a G-code file to the plotter"""
        global indent_level
        
        if not self.connected or not self.serial:
            print_tree("Not connected to plotter", symbol=TreeSymbols.ERROR, status_color=Colors.RED)
            return False
        
        print_tree("Streaming G-code file", level=indent_level)
        indent_level += 1
        
        try:
            # Open the G-code file
            with open(filename, 'r') as f:
                # Preview the first few commands
                print_tree("Analyzing G-code content", level=indent_level)
                indent_level += 1
                
                first_lines = []
                for i, line in enumerate(f):
                    if i >= 5:  # Limit to first 5 commands for preview
                        break
                    line = line.strip()
                    if line and not line.startswith('%') and not line.startswith('(') and not line.startswith(';'):
                        first_lines.append(line)
                
                if first_lines:
                    print_tree("First few commands", level=indent_level, is_last=True)
                    for i, line in enumerate(first_lines):
                        is_last = (i == len(first_lines) - 1)
                        print_sub_message(line, is_last=is_last)
                
                indent_level -= 1
                
                # Reset file pointer to beginning
                f.seek(0)
                
                # Initialize progress tracking
                line_count = sum(1 for _ in f)
                f.seek(0)
                
                print_tree("Executing G-code commands", level=indent_level)
                indent_level += 1
                
                # Send commands line by line
                line_number = 0
                error_count = 0
                
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('%') or line.startswith('(') or line.startswith(';'):
                        continue
                    
                    # Special handling for program number
                    if line.startswith('O'):
                        continue
                    
                    # Send the command and wait for response
                    response = self.send_command(line, display_tree=False)
                    if response and response.startswith("error:"):
                        error_count += 1
                        if debug_mode:
                            print_tree(f"Error ({line}): {response}", symbol=TreeSymbols.WARNING, level=indent_level, status_color=Colors.YELLOW)
                    
                    # Update progress
                    line_number += 1
                    progress = line_number / line_count * 100
                    print(f"\r{Colors.CYAN}Progress: {progress:.1f}% | Current: {line[:30]}...{Colors.RESET}", end='')
                    
                    # Give GRBL time to process
                    time.sleep(0.05)
                
                print()  # Clear the progress line
                
                if error_count > 0:
                    print_tree(f"Completed with {error_count} errors", symbol=TreeSymbols.WARNING, level=indent_level, is_last=True, status_color=Colors.YELLOW)
                else:
                    print_tree("All commands executed successfully", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
                
                indent_level -= 1
                print_tree("File streaming complete", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
                indent_level -= 1
                
            return True
            
        except Exception as e:
            print_tree(f"Error streaming file: {e}", symbol=TreeSymbols.ERROR, level=indent_level, is_last=True, status_color=Colors.RED)
            indent_level -= 1
            return False

def generate_square_gcode(x_start=10, y_start=10, size=50, file_path=None):
    """Generate GCode for drawing a square"""
    global indent_level
    
    print_tree("Generating square G-code", level=indent_level)
    indent_level += 1
    
    if file_path is None:
        print_tree("Creating temporary file", level=indent_level)
        fd, file_path = tempfile.mkstemp(suffix='.gcode')
        os.close(fd)
    else:
        print_tree(f"Using output file: {file_path}", level=indent_level)
    
    print_tree("Writing G-code content", level=indent_level)
    
    with open(file_path, 'w') as f:
        # GCode header
        f.write("; GCode for drawing a square - GRBL compatible\n")
        f.write("\n")
        
        # Setup
        f.write("G21 ; Set units to millimeters\n")
        f.write("G90 ; Set absolute positioning\n")
        f.write("G1 F3000 ; Set feed rate (speed)\n")
        
        # Pen up
        f.write("M3 S0 ; Pen up\n")
        f.write("G4 P0.5 ; Wait for pen to move\n")
        
        # Move to starting position
        f.write(f"G0 X{x_start} Y{y_start} ; Move to starting position\n")
        
        # Pen down
        f.write("M3 S1000 ; Pen down\n")
        f.write("G4 P0.5 ; Wait for pen to move\n")
        
        # Draw square
        f.write(f"G1 X{x_start + size} Y{y_start} ; Draw bottom line\n")
        f.write(f"G1 X{x_start + size} Y{y_start + size} ; Draw right line\n")
        f.write(f"G1 X{x_start} Y{y_start + size} ; Draw top line\n")
        f.write(f"G1 X{x_start} Y{y_start} ; Draw left line (complete square)\n")
        
        # Pen up
        f.write("M3 S0 ; Pen up\n")
        f.write("G4 P0.5 ; Wait for pen to move\n")
        
        # Return to home
        f.write("G0 X0 Y0 ; Return to home position\n")
    
    print_tree(f"G-code file created: {file_path}", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
    indent_level -= 1
    
    return file_path

def main():
    global debug_mode, indent_level
    
    # Print compact title
    print(f"{Colors.CYAN}GRBL Pen Plotter G-code Streamer{Colors.RESET}")
    print()
    
    # Start workflow tree
    print_tree("Initialize Workflow")
    indent_level = 1
    
    # Parse command line arguments
    print_tree("Processing command line arguments", level=indent_level)
    indent_level += 1
    
    parser = argparse.ArgumentParser(description='GRBL-based Pen Plotter G-code Streamer')
    parser.add_argument('--port', required=True, help='Serial port connected to plotter')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate for serial connection')
    parser.add_argument('--size', type=int, default=50, help='Size of square in mm')
    parser.add_argument('--x', type=int, default=10, help='X starting position in mm')
    parser.add_argument('--y', type=int, default=10, help='Y starting position in mm')
    parser.add_argument('--output', help='Output path for GCode file (optional)')
    parser.add_argument('--file', help='Path to existing .gcode or .nc file to stream')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with verbose logging')
    args = parser.parse_args()
    
    # Set debug mode based on flag
    debug_mode = args.debug
    if debug_mode:
        print_sub_message("Debug mode enabled")
    
    print_tree("Configuration loaded", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
    indent_level -= 1
    
    # Start file processing
    print_tree("Prepare G-code file", level=indent_level)
    indent_level += 1
    
    # Determine which file to stream
    if args.file:
        # User provided an existing file to stream
        if not os.path.exists(args.file):
            print_tree(f"File not found: {args.file}", symbol=TreeSymbols.ERROR, level=indent_level, is_last=True, status_color=Colors.RED)
            return
        
        file_ext = os.path.splitext(args.file)[1].lower()
        if file_ext not in ['.gcode', '.nc']:
            print_tree(f"Unusual file extension: {file_ext}", symbol=TreeSymbols.WARNING, level=indent_level, status_color=Colors.YELLOW)
            print_sub_message("Will attempt to process as G-code anyway")
        
        gcode_file = args.file
        print_tree(f"Using existing file: {os.path.basename(gcode_file)}", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
    else:
        # Generate GCode for a square
        print_tree(f"No file specified, generating square pattern", level=indent_level)
        print_sub_message(f"Size: {args.size}mm × {args.size}mm at ({args.x}, {args.y})")
        
        gcode_file = generate_square_gcode(
            x_start=args.x,
            y_start=args.y,
            size=args.size,
            file_path=args.output
        )
        
        print_tree("Square G-code ready", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
    
    indent_level -= 1
    
    # Start plotter control workflow
    print_tree("Begin plotter operation", level=indent_level)
    indent_level += 1
    
    print_sub_message(f"Port: {args.port}, Baud rate: {args.baud}")
    
    # Create plotter controller and connect
    plotter = GrblPlotter(args.port, args.baud)
    try:
        if plotter.connect():
            # Try to unlock GRBL if needed
            print_tree("Unlocking controller", level=indent_level)
            plotter.send_command("$X", display_tree=False)
            
            # Stream the file
            result = plotter.stream_file(gcode_file)
            
            if result:
                print_tree("Drawing completed successfully", symbol=TreeSymbols.SUCCESS, level=indent_level, is_last=True, status_color=Colors.GREEN)
            else:
                print_tree("Drawing failed", symbol=TreeSymbols.ERROR, level=indent_level, is_last=True, status_color=Colors.RED)
        else:
            print_tree("Connection failed", symbol=TreeSymbols.ERROR, level=indent_level, is_last=True, status_color=Colors.RED)
    finally:
        plotter.disconnect()
    
    indent_level -= 1
    
    # Clean up temp file if we created one and it's not a user-provided file
    if args.output is None and not args.file:
        print_tree("Cleaning up temporary files", level=indent_level, is_last=True)
        try:
            os.remove(gcode_file)
        except:
            pass
    
    print_tree("Workflow complete", symbol=TreeSymbols.SUCCESS, level=0, is_last=True, status_color=Colors.GREEN)

if __name__ == "__main__":
    main()