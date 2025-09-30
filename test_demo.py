#!/usr/bin/env python3
"""
Demo script to showcase the PromptPlot v2.0 testing infrastructure.
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            if result.stdout:
                print("Output:")
                print(result.stdout[:500])  # Limit output
        else:
            print(f"❌ {description} - FAILED")
            if result.stderr:
                print("Error:")
                print(result.stderr[:500])
                
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False


def main():
    """Run testing infrastructure demo."""
    print("🚀 PromptPlot v2.0 Testing Infrastructure Demo")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("tests").exists():
        print("❌ Tests directory not found. Please run from project root.")
        return 1
        
    # Test infrastructure validation
    tests = [
        ("python -m pytest --version", "Check pytest installation"),
        ("python -c 'import tests.conftest; print(\"✅ Test fixtures loaded\")'", "Validate test fixtures"),
        ("python -c 'from tests.utils.mocks import MockLLMProvider; print(\"✅ Mock objects available\")'", "Check mock objects"),
        ("python -c 'from tests.utils.gcode_utils import GCodeTestValidator; print(\"✅ G-code utilities available\")'", "Validate G-code utilities"),
    ]
    
    print("\n📋 Testing Infrastructure Validation")
    print("-" * 40)
    
    all_passed = True
    for cmd, desc in tests:
        success = run_command(cmd, desc)
        all_passed = all_passed and success
        
    if not all_passed:
        print("\n❌ Infrastructure validation failed. Please check dependencies.")
        return 1
        
    # Run sample tests
    sample_tests = [
        ("python -m pytest tests/unit/test_core_models.py::TestGCodeCommand::test_create_basic_command -v", 
         "Run sample unit test"),
        ("python -m pytest tests/unit/test_llm_providers.py::TestLLMProviderBase::test_mock_provider_implementation -v", 
         "Test LLM provider mocks"),
        ("python -m pytest tests/unit/test_strategies.py::TestStrategySelector::test_analyze_simple_prompts -v", 
         "Test strategy selection"),
    ]
    
    print("\n🧪 Sample Test Execution")
    print("-" * 40)
    
    for cmd, desc in sample_tests:
        run_command(cmd, desc)
        
    # Show test structure
    print("\n📁 Test Structure Overview")
    print("-" * 40)
    
    def show_tree(path, prefix="", max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return
            
        items = sorted(path.iterdir())
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{item.name}")
            
            if item.is_dir() and not item.name.startswith('.') and current_depth < max_depth - 1:
                next_prefix = prefix + ("    " if is_last else "│   ")
                show_tree(item, next_prefix, max_depth, current_depth + 1)
                
    show_tree(Path("tests"))
    
    # Show available test commands
    print("\n🛠️  Available Test Commands")
    print("-" * 40)
    
    commands = [
        ("make test", "Run all tests"),
        ("make test-unit", "Run unit tests only"),
        ("make test-integration", "Run integration tests only"),
        ("make test-coverage", "Run tests with coverage report"),
        ("make test-benchmark", "Run performance benchmarks"),
        ("python run_tests.py --unit", "Run unit tests with custom runner"),
        ("python run_tests.py --coverage", "Generate coverage report"),
    ]
    
    for cmd, desc in commands:
        print(f"  {cmd:<30} - {desc}")
        
    print("\n📊 Test Categories")
    print("-" * 40)
    
    categories = [
        ("Unit Tests", "Individual component testing", "tests/unit/"),
        ("Integration Tests", "End-to-end workflow testing", "tests/integration/"),
        ("Performance Tests", "Benchmarking and scalability", "@pytest.mark.benchmark"),
        ("Mock Objects", "Test doubles and stubs", "tests/utils/mocks.py"),
        ("Test Fixtures", "Sample data and files", "tests/fixtures/"),
        ("G-code Utilities", "Validation and analysis tools", "tests/utils/gcode_utils.py"),
    ]
    
    for name, desc, location in categories:
        print(f"  {name:<20} - {desc:<35} ({location})")
        
    print("\n🎯 Test Coverage Areas")
    print("-" * 40)
    
    coverage_areas = [
        "✅ Core Models (GCodeCommand, GCodeProgram)",
        "✅ LLM Provider Abstraction (Azure OpenAI, Ollama)",
        "✅ Strategy Selection (Orthogonal, Non-orthogonal)",
        "✅ Plotter Interfaces (Serial, Simulated)",
        "✅ File Conversion (SVG, DXF, G-code, JSON)",
        "✅ Workflow Execution (Simple, Advanced, File plotting)",
        "✅ Error Handling and Recovery",
        "✅ Performance and Scalability",
        "✅ Concurrent Operations",
        "✅ Memory Management",
    ]
    
    for area in coverage_areas:
        print(f"  {area}")
        
    print("\n🚀 Quick Start Testing")
    print("-" * 40)
    print("1. Install test dependencies:")
    print("   pip install -r requirements-test.txt")
    print()
    print("2. Run basic tests:")
    print("   make test-unit")
    print()
    print("3. Run with coverage:")
    print("   make test-coverage")
    print()
    print("4. Run performance benchmarks:")
    print("   make test-benchmark")
    print()
    print("5. View coverage report:")
    print("   open htmlcov/index.html")
    
    print(f"\n✨ Testing infrastructure setup complete!")
    print(f"📁 {len(list(Path('tests').rglob('test_*.py')))} test files created")
    print(f"🧪 Ready for comprehensive testing of PromptPlot v2.0")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())