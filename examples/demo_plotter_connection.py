#!/usr/bin/env python3
"""
Pen Plotter Connection Test

This script tests the connection and basic functionality of pen plotters,
including both simulated and real hardware connections.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from promptplot.plotter import SerialPlotter, SimulatedPlotter, PlotterVisualizer
    from promptplot.core import GCodeCommand, GCodeProgram
    from promptplot.core.exceptions import PlotterConnectionException, PlotterCommandException
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


class PlotterConnectionTester:
    """Comprehensive plotter connection testing utility"""
    
    def __init__(self):
        self.test_results: List[Dict[str, Any]] = []
        self.current_plotter: Optional[Any] = None
    
    def log_result(self, test_name: str, success: bool, message: str = "", details: Dict = None):
        """Log a test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    async def test_simulated_plotter(self) -> bool:
        """Test the simulated plotter functionality"""
        print("\n" + "="*60)
        print("🤖 Testing Simulated Plotter")
        print("="*60)
        
        try:
            # Create simulated plotter
            plotter = SimulatedPlotter("SIMULATED")
            self.current_plotter = plotter
            
            # Test connection
            success = await plotter.connect()
            self.log_result(
                "Simulated Plotter Connection", 
                success,
                "Connected successfully" if success else "Connection failed"
            )
            
            if not success:
                return False
            
            # Test basic commands
            await self._test_basic_commands(plotter, "Simulated")
            
            # Test G-code program execution
            await self._test_gcode_program(plotter, "Simulated")
            
            # Test status monitoring
            await self._test_status_monitoring(plotter, "Simulated")
            
            # Disconnect
            await plotter.disconnect()
            self.log_result(
                "Simulated Plotter Disconnect",
                not plotter.is_connected,
                "Disconnected successfully"
            )
            
            return True
            
        except Exception as e:
            self.log_result(
                "Simulated Plotter Test",
                False,
                f"Unexpected error: {str(e)}"
            )
            return False
    
    async def test_serial_plotter(self, port: str) -> bool:
        """Test serial plotter connection"""
        print("\n" + "="*60)
        print(f"🔌 Testing Serial Plotter on {port}")
        print("="*60)
        
        try:
            # Create serial plotter
            plotter = SerialPlotter(port, timeout=10.0, max_retries=2)
            self.current_plotter = plotter
            
            # Test connection with retry
            try:
                success = await plotter.connect_with_retry()
                self.log_result(
                    "Serial Plotter Connection",
                    success,
                    f"Connected to {port}" if success else f"Failed to connect to {port}",
                    {"port": port, "baud_rate": plotter.baud_rate}
                )
                
                if not success:
                    return False
                
            except PlotterConnectionException as e:
                self.log_result(
                    "Serial Plotter Connection",
                    False,
                    f"Connection failed: {str(e)}",
                    {"port": port, "error_type": "PlotterConnectionException"}
                )
                return False
            
            # Test basic commands
            await self._test_basic_commands(plotter, "Serial")
            
            # Test G-code program execution
            await self._test_gcode_program(plotter, "Serial")
            
            # Test status monitoring
            await self._test_status_monitoring(plotter, "Serial")
            
            # Test heartbeat (if enabled)
            if hasattr(plotter, 'enable_heartbeat') and plotter.enable_heartbeat:
                await self._test_heartbeat(plotter)
            
            # Disconnect
            await plotter.disconnect()
            self.log_result(
                "Serial Plotter Disconnect",
                not plotter.is_connected,
                "Disconnected successfully"
            )
            
            return True
            
        except Exception as e:
            self.log_result(
                "Serial Plotter Test",
                False,
                f"Unexpected error: {str(e)}"
            )
            return False
    
    async def _test_basic_commands(self, plotter, plotter_type: str):
        """Test basic G-code commands"""
        print(f"\n📝 Testing Basic Commands ({plotter_type})")
        
        # Use configurable pen commands for GRBL compatibility
        # Most GRBL plotters need servo value: M3 S1000 (down) / M3 S0 or M5 (up)
        # Or use Z-axis: G1 Z0 (down) / G1 Z5 (up)
        pen_up = "M3 S0"      # Servo at 0 position (pen up)
        pen_down = "M3 S1000" # Servo at max position (pen down)
        
        # For GRBL with servo, we need to include S value with movement commands
        # to keep the servo engaged (laser mode behavior)
        basic_commands = [
            ("G28", "Home command", 0.5),
            (pen_down, "Pen down (test)", 1.0),
            (pen_up, "Pen up (test)", 1.0),
            (pen_down, "Pen down (before drawing)", 1.0),
            ("G1 X10 Y10 S1000 F1000", "Move to start (pen down)", 0.1),
            ("G1 X20 Y20 S1000 F1000", "Draw line 1", 0.1),
            ("G1 X30 Y30 S1000 F1000", "Draw line 2", 0.1),
            ("G1 X10 Y10 S1000 F1000", "Return to start", 0.1),
            (pen_up, "Pen up (after drawing)", 1.0)
        ]
        
        for command, description, delay in basic_commands:
            try:
                success = await plotter.send_command_safe(command)
                self.log_result(
                    f"{plotter_type} Command: {command}",
                    success,
                    description,
                    {"response": plotter.status.last_response}
                )
                
                # Delay after command (longer for pen movements)
                await asyncio.sleep(delay)
                
            except Exception as e:
                self.log_result(
                    f"{plotter_type} Command: {command}",
                    False,
                    f"Command failed: {str(e)}"
                )
    
    async def _test_gcode_program(self, plotter, plotter_type: str):
        """Test executing a complete G-code program"""
        print(f"\n📋 Testing G-code Program Execution ({plotter_type})")
        
        try:
            # Create a simple square drawing program
            # Using servo commands with S value on each move (GRBL laser mode)
            # Pen up = S0, Pen down = S1000 on each G1 command
            commands = [
                GCodeCommand(command="G28"),                        # Home
                GCodeCommand(command="M3 S0"),                      # Pen up (servo)
                GCodeCommand(command="G1", x=0, y=0, s=0, f=1000),  # Move to origin (pen up)
                GCodeCommand(command="M3 S1000"),                   # Pen down (servo)
                GCodeCommand(command="G1", x=30, y=0, s=1000, f=1000),   # Draw bottom
                GCodeCommand(command="G1", x=30, y=30, s=1000, f=1000),  # Draw right
                GCodeCommand(command="G1", x=0, y=30, s=1000, f=1000),   # Draw top
                GCodeCommand(command="G1", x=0, y=0, s=1000, f=1000),    # Draw left
                GCodeCommand(command="M3 S0"),                      # Pen up (servo)
            ]
            
            program = GCodeProgram(commands=commands)
            
            # Execute the program
            success_count = 0
            for i, cmd in enumerate(program.commands):
                try:
                    gcode = cmd.to_gcode()
                    success = await plotter.send_command_safe(gcode)
                    if success:
                        success_count += 1
                    # Wait 1 second after pen commands (M3) to let servo settle
                    if gcode.startswith("M3"):
                        await asyncio.sleep(1.0)
                    else:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"   Command {i+1} failed: {str(e)}")
            
            program_success = success_count == len(program.commands)
            self.log_result(
                f"{plotter_type} G-code Program",
                program_success,
                f"Executed {success_count}/{len(program.commands)} commands",
                {
                    "total_commands": len(program.commands),
                    "successful_commands": success_count,
                    "program_bounds": program.get_bounds()
                }
            )
            
        except Exception as e:
            self.log_result(
                f"{plotter_type} G-code Program",
                False,
                f"Program execution failed: {str(e)}"
            )
    
    async def _test_status_monitoring(self, plotter, plotter_type: str):
        """Test plotter status monitoring"""
        print(f"\n📊 Testing Status Monitoring ({plotter_type})")
        
        try:
            # Get status information
            if hasattr(plotter, 'get_plotter_status'):
                status = await plotter.get_plotter_status()
            else:
                status = {
                    "connected": plotter.is_connected,
                    "busy": plotter.is_busy,
                    "port": plotter.port
                }
            
            # Check command history
            history = plotter.get_command_history(limit=5)
            
            self.log_result(
                f"{plotter_type} Status Monitoring",
                True,
                "Status retrieved successfully",
                {
                    "status": status,
                    "recent_commands": len(history),
                    "last_commands": history[-3:] if history else []
                }
            )
            
        except Exception as e:
            self.log_result(
                f"{plotter_type} Status Monitoring",
                False,
                f"Status monitoring failed: {str(e)}"
            )
    
    async def _test_heartbeat(self, plotter):
        """Test heartbeat functionality for serial plotter"""
        print(f"\n💓 Testing Heartbeat Monitoring")
        
        try:
            # Wait a bit to let heartbeat run
            await asyncio.sleep(2.0)
            
            # Check if ping information is available
            has_ping_info = (
                hasattr(plotter.status, 'last_ping_time') and
                plotter.status.last_ping_time is not None
            )
            
            self.log_result(
                "Serial Plotter Heartbeat",
                has_ping_info,
                "Heartbeat monitoring active" if has_ping_info else "No heartbeat data",
                {
                    "last_ping_time": getattr(plotter.status, 'last_ping_time', None),
                    "ping_response_time": getattr(plotter.status, 'ping_response_time', None),
                    "heartbeat_enabled": getattr(plotter, 'enable_heartbeat', False)
                }
            )
            
        except Exception as e:
            self.log_result(
                "Serial Plotter Heartbeat",
                False,
                f"Heartbeat test failed: {str(e)}"
            )
    
    def detect_serial_ports(self) -> List[str]:
        """Detect available serial ports"""
        ports = []
        
        try:
            import serial.tools.list_ports
            
            available_ports = serial.tools.list_ports.comports()
            for port in available_ports:
                ports.append(port.device)
                print(f"   Found port: {port.device} - {port.description}")
                
        except ImportError:
            print("   pyserial not available for port detection")
            # Add common port names for manual testing
            import platform
            system = platform.system()
            if system == "Linux":
                ports.extend(["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"])
            elif system == "Darwin":  # macOS
                ports.extend(["/dev/tty.usbserial", "/dev/tty.usbmodem"])
            elif system == "Windows":
                ports.extend(["COM1", "COM2", "COM3", "COM4"])
        
        return ports
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "No tests run")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print(f"\n🎯 Recommendations:")
        if passed_tests == total_tests:
            print("   ✅ All tests passed! Your plotter setup is working correctly.")
        else:
            print("   🔧 Some tests failed. Check the error messages above.")
            print("   📖 Refer to the troubleshooting guide for common issues.")


async def main():
    """Main test function"""
    print("🖊️  PromptPlot Pen Plotter Connection Test")
    print("="*60)
    print("This script tests pen plotter connections and basic functionality.")
    print("It will test both simulated and real hardware connections.")
    
    tester = PlotterConnectionTester()
    
    # Test simulated plotter first (always available)
    print("\n🚀 Starting plotter connection tests...")
    await tester.test_simulated_plotter()
    
    # Check if a specific port was provided
    if len(sys.argv) > 1:
        # Test only the manually specified port
        manual_port = sys.argv[1]
        print(f"\n🎯 Testing manually specified port: {manual_port}")
        try:
            await tester.test_serial_plotter(manual_port)
        except Exception as e:
            print(f"   Error testing manual port {manual_port}: {str(e)}")
    else:
        # Detect and test serial ports
        print("\n🔍 Detecting serial ports...")
        ports = tester.detect_serial_ports()
        
        if not ports:
            print("   No serial ports detected.")
            print("   Connect your pen plotter and try again, or specify a port manually.")
        else:
            print(f"   Found {len(ports)} potential serial port(s)")
            
            # Test each detected port
            for port in ports[:3]:  # Limit to first 3 ports to avoid long waits
                print(f"\n🔌 Testing port: {port}")
                try:
                    await tester.test_serial_plotter(port)
                except KeyboardInterrupt:
                    print(f"\n⏹️  Test interrupted by user")
                    break
                except Exception as e:
                    print(f"   Unexpected error testing {port}: {str(e)}")
    
    # Print summary
    tester.print_summary()
    
    # Usage instructions
    print(f"\n📖 Usage Instructions:")
    print(f"   python {sys.argv[0]}                    # Test detected ports")
    print(f"   python {sys.argv[0]} /dev/ttyUSB0       # Test specific port")
    print(f"   python {sys.argv[0]} COM3               # Test Windows port")
    
    print(f"\n🔧 Troubleshooting:")
    print(f"   - Make sure your pen plotter is connected and powered on")
    print(f"   - Check that you have the correct drivers installed")
    print(f"   - Verify the baud rate matches your plotter (default: 115200)")
    print(f"   - Try different USB ports or cables")
    print(f"   - Check device permissions on Linux/macOS")
    
    return 0 if all(r["success"] for r in tester.test_results) else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)