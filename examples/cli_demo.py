#!/usr/bin/env python3
"""
CLI Demo for PromptPlot v2.0

This example demonstrates the CLI interface and shows all available commands
without requiring complex workflow execution.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a CLI command and show the output."""
    print(f"\n🔧 {description}")
    print("=" * 50)
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False

def main():
    """Run CLI demo."""
    print("🖥️  PromptPlot v2.0 CLI Demo")
    print("=" * 40)
    
    # List of commands to demonstrate
    commands = [
        (["python3", "-m", "promptplot.cli", "--version"], "Show version"),
        (["python3", "-m", "promptplot.cli", "--help"], "Show main help"),
        (["python3", "-m", "promptplot.cli", "config", "show", "--section", "llm"], "Show LLM configuration"),
        (["python3", "-m", "promptplot.cli", "config", "show", "--section", "plotter"], "Show plotter configuration"),
        (["python3", "-m", "promptplot.cli", "config", "show", "--section", "workflow"], "Show workflow configuration"),
        (["python3", "-m", "promptplot.cli", "plotter", "list-ports"], "List available serial ports"),
        (["python3", "-m", "promptplot.cli", "workflow", "--help"], "Show workflow help"),
        (["python3", "-m", "promptplot.cli", "file", "--help"], "Show file commands help"),
    ]
    
    success_count = 0
    total_count = len(commands)
    
    for cmd, description in commands:
        success = run_command(cmd, description)
        if success:
            success_count += 1
            print("✅ Success")
        else:
            print("❌ Failed")
    
    print(f"\n📊 Results: {success_count}/{total_count} commands successful")
    
    if success_count == total_count:
        print("🎉 All CLI commands working perfectly!")
        
        print("\n📚 Available CLI Commands:")
        print("• promptplot --help                    - Show main help")
        print("• promptplot config show               - Show configuration")
        print("• promptplot config set key value     - Set configuration")
        print("• promptplot plotter list-ports       - List serial ports")
        print("• promptplot plotter test --simulate  - Test plotter connection")
        print("• promptplot workflow simple 'prompt' - Simple drawing workflow")
        print("• promptplot file plot file.svg       - Plot a file")
        print("• promptplot interactive              - Interactive mode")
        
        print("\n🚀 Try these examples:")
        print("make example-llm                      - LLM demo with real AI")
        print("make example-streaming                - Streaming demo")
        print("make example-quick                    - Quick start demo")
        
    else:
        print("⚠️  Some CLI commands had issues")
    
    return success_count == total_count

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        sys.exit(1)