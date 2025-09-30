#!/usr/bin/env python3
"""
Hardware Connection Example

This example demonstrates how to connect to real plotter hardware:
- Detecting available serial ports
- Connecting to a plotter
- Testing the connection
- Executing simple commands

WARNING: This example requires actual hardware. Make sure your plotter
is properly connected and configured before running.
"""

import asyncio
import sys
import os
import serial.tools.list_ports

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from promptplot.workflows import SimpleBatchWorkflow
from promptplot.plotter import SerialPlotter
from promptplot.core.exceptions import PlotterException


def list_serial_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    return [(port.device, port.description) for port in ports]


async def test_plotter_connection(port, baud_rate=115200):
    """Test connection to a plotter."""
    print(f"Testing connection to {port} at {baud_rate} baud...")
    
    try:
        plotter = SerialPlotter(
            port=port,
            baud_rate=baud_rate,
            timeout=5
        )
        
        # Try to connect
        success = await plotter.connect()
        
        if success:
            print("   ✓ Connection successful")
            
            # Send a simple test command (usually a status query)
            response = await plotter.send_command("M114")  # Get current position
            print(f"   ✓ Test command response: {response}")
            
            await plotter.disconnect()
            return True
        else:
            print("   ✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"   ✗ Connection error: {e}")
        return False


async def main():
    """Main example function."""
    print("PromptPlot Hardware Connection Example")
    print("=" * 45)
    
    # Step 1: List available serial ports
    print("1. Scanning for serial ports...")
    ports = list_serial_ports()
    
    if not ports:
        print("   No serial ports found!")
        print("   Make sure your plotter is connected via USB.")
        return
    
    print(f"   Found {len(ports)} serial port(s):")
    for i, (port, description) in enumerate(ports):
        print(f"   {i+1}. {port} - {description}")
    
    # Step 2: Select port
    if len(ports) == 1:
        selected_port = ports[0][0]
        print(f"\n2. Auto-selecting only available port: {selected_port}")
    else:
        print("\n2. Select a port:")
        try:
            choice = int(input(f"   Enter port number (1-{len(ports)}): ")) - 1
            if 0 <= choice < len(ports):
                selected_port = ports[choice][0]
            else:
                print("   Invalid selection!")
                return
        except ValueError:
            print("   Invalid input!")
            return
    
    # Step 3: Test connection
    print(f"\n3. Testing connection to {selected_port}...")
    
    # Try common baud rates
    baud_rates = [115200, 9600, 19200, 38400, 57600]
    connected = False
    working_baud = None
    
    for baud_rate in baud_rates:
        if await test_plotter_connection(selected_port, baud_rate):
            connected = True
            working_baud = baud_rate
            break
    
    if not connected:
        print("\n   ✗ Could not establish connection with any baud rate")
        print("   Check your plotter configuration and try again.")
        return
    
    print(f"\n   ✓ Successfully connected at {working_baud} baud")
    
    # Step 4: Create workflow and test drawing
    print("\n4. Setting up workflow...")
    
    plotter = SerialPlotter(
        port=selected_port,
        baud_rate=working_baud,
        timeout=10
    )
    
    workflow = SimpleBatchWorkflow(plotter=plotter)
    
    # Step 5: Execute a simple test drawing
    print("\n5. Executing test drawing...")
    print("   WARNING: The plotter will now move!")
    
    confirm = input("   Continue with test drawing? (y/N): ")
    if confirm.lower() != 'y':
        print("   Test drawing cancelled.")
        return
    
    try:
        # Simple test drawing - small square
        result = await workflow.execute("Draw a small 10mm square at origin")
        
        if result.success:
            print(f"   ✓ Test drawing completed!")
            print(f"     Commands executed: {len(result.commands)}")
            print(f"     Execution time: {result.execution_time:.2f} seconds")
        else:
            print(f"   ✗ Test drawing failed: {result.error_message}")
            
    except Exception as e:
        print(f"   ✗ Drawing error: {e}")
    
    print("\n6. Hardware connection example completed!")
    print("   Your plotter is ready for use with PromptPlot.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nExample failed: {e}")
        sys.exit(1)