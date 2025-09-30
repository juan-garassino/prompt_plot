#!/usr/bin/env python3
"""
Simple test script for the PromptPlot CLI
"""

import subprocess
import sys

def test_cli_help():
    """Test that CLI help works"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ CLI help command works")
            return True
        else:
            print(f"✗ CLI help failed with return code {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ CLI help test failed: {str(e)}")
        return False

def test_cli_config_show():
    """Test that config show works"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "promptplot.cli", "config", "show"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ CLI config show command works")
            return True
        else:
            print(f"✗ CLI config show failed with return code {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ CLI config show test failed: {str(e)}")
        return False

def main():
    """Run CLI tests"""
    print("Testing PromptPlot CLI...")
    
    tests = [
        test_cli_help,
        test_cli_config_show,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! ✓")
        return 0
    else:
        print("Some tests failed! ✗")
        return 1

if __name__ == "__main__":
    sys.exit(main())