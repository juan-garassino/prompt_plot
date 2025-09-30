#!/usr/bin/env python3
"""
Basic test runner to check if our core tests work without API dependencies.
"""
import subprocess
import sys


def run_basic_tests():
    """Run basic tests that don't require API keys."""
    
    print("🧪 Running Basic PromptPlot Tests (No API Keys Required)")
    print("=" * 60)
    
    # Test core models
    print("\n1. Testing Core Models...")
    result = subprocess.run([
        "python", "-m", "pytest", 
        "tests/unit/test_core_models.py::TestGCodeCommand::test_create_basic_command",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Core models test passed")
    else:
        print("❌ Core models test failed")
        print(result.stdout)
        print(result.stderr)
    
    # Test mock LLM provider
    print("\n2. Testing Mock LLM Provider...")
    result = subprocess.run([
        "python", "-m", "pytest", 
        "tests/unit/test_llm_providers.py::TestLLMProviderBase::test_mock_provider_implementation",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Mock LLM provider test passed")
    else:
        print("❌ Mock LLM provider test failed")
        print(result.stdout)
        print(result.stderr)
    
    # Test strategy selector
    print("\n3. Testing Strategy Selector...")
    result = subprocess.run([
        "python", "-m", "pytest", 
        "tests/unit/test_strategies.py::TestStrategySelector::test_analyze_simple_prompts",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Strategy selector test passed")
    else:
        print("❌ Strategy selector test failed")
        print(result.stdout)
        print(result.stderr)
    
    # Test mock plotter
    print("\n4. Testing Mock Plotter...")
    result = subprocess.run([
        "python", "-m", "pytest", 
        "tests/unit/test_plotter_interfaces.py::TestBasePlotter::test_mock_plotter_basic_operations",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Mock plotter test passed")
    else:
        print("❌ Mock plotter test failed")
        print(result.stdout)
        print(result.stderr)
    
    print("\n" + "=" * 60)
    print("🎯 Basic test run complete!")
    print("\nNote: These tests use mock objects and don't require API keys.")
    print("For full testing with real LLM providers, you'll need to set up:")
    print("- GPT4_API_KEY, GPT4_API_VERSION, GPT4_ENDPOINT for Azure OpenAI")
    print("- Or run a local Ollama instance for Ollama provider")


if __name__ == "__main__":
    run_basic_tests()