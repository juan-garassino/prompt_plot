#!/usr/bin/env python3
"""
LLM Demo for PromptPlot v2.0

This example demonstrates using real LLMs to generate G-code from natural language prompts.

Supported providers:
- OpenAI (GPT-4o-mini, GPT-4o, etc.) - Set OPENAI_API_KEY
- Gemini (gemini-1.5-flash, gemini-1.5-pro) - Set GOOGLE_API_KEY
- Azure OpenAI - Set GPT4_API_KEY, GPT4_ENDPOINT, GPT4_API_VERSION
- Ollama (local models) - Install and run Ollama

Usage:
    python examples/demo_llm_generation.py --provider openai
    python examples/demo_llm_generation.py --provider gemini
    python examples/demo_llm_generation.py --provider azure
    python examples/demo_llm_generation.py --provider ollama
    python examples/demo_llm_generation.py --prompt "Draw a heart shape"
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add the parent directory to the path so we can import promptplot
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from promptplot import SimpleGCodeWorkflow, get_config
    from promptplot.plotter.simulated import SimulatedPlotter
    from promptplot.llm.providers import (
        OllamaProvider, 
        AzureOpenAIProvider,
        OpenAIProvider,
        GeminiProvider
    )
    from promptplot.strategies import StrategySelector
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure PromptPlot is installed: pip install -e .")
    sys.exit(1)


def check_ollama_available():
    """Check if Ollama is running and has models available."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return len(models) > 0, [model["name"] for model in models]
        return False, []
    except Exception:
        return False, []


def check_azure_credentials():
    """Check if Azure OpenAI credentials are available."""
    required_vars = ["GPT4_API_KEY", "GPT4_ENDPOINT", "GPT4_API_VERSION"]
    missing = [var for var in required_vars if not os.getenv(var)]
    return len(missing) == 0, missing


def check_openai_credentials():
    """Check if OpenAI API key is available."""
    api_key = os.getenv("OPENAI_API_KEY")
    return api_key is not None, [] if api_key else ["OPENAI_API_KEY"]


def check_gemini_credentials():
    """Check if Google API key is available."""
    api_key = os.getenv("GOOGLE_API_KEY")
    return api_key is not None, [] if api_key else ["GOOGLE_API_KEY"]


async def demo_with_ollama(prompt: str):
    """Demo using Ollama local LLM."""
    print("🦙 Using Ollama Local LLM")
    print("-" * 30)
    
    # Check if Ollama is available
    available, models = check_ollama_available()
    if not available:
        print("❌ Ollama not available. Please:")
        print("   1. Install Ollama: https://ollama.ai/")
        print("   2. Start Ollama: ollama serve")
        print("   3. Pull a model: ollama pull llama3.2:3b")
        return False
    
    print(f"✅ Ollama available with models: {', '.join(models[:3])}")
    
    # Use the first available model or default
    model = models[0] if models else "llama3.2:3b"
    print(f"📝 Using model: {model}")
    
    try:
        # Create Ollama provider
        llm_provider = OllamaProvider(
            model=model,
            request_timeout=30000  # 30 seconds
        )
        
        # Set up simulated plotter with visualization
        plotter = SimulatedPlotter(port="OLLAMA_DEMO", visualize=True)
        
        # Get configuration
        config = get_config()
        
        # Create workflow - pass the underlying llama-index LLM instance
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider.llm,  # Use .llm to get the raw llama-index instance
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ This may take 10-30 seconds...")
        
        # Execute the workflow
        result = await workflow.run(prompt=prompt)
        
        if result and result.get('commands_count', 0) > 0:
            print(f"✅ Success! Generated {result['commands_count']} G-code commands")
            
            # Show G-code preview
            print("\n📋 Generated G-code:")
            gcode_lines = result.get('gcode', '').split('\n')[:8]
            for i, line in enumerate(gcode_lines, 1):
                print(f"   {i:2d}. {line}")
            
            if len(result.get('gcode', '').split('\n')) > 8:
                print(f"   ... and more commands")
            
            print("\n🖼️  Check the visualization window to see the drawing!")
            
        else:
            print("❌ No G-code generated. Check the LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Error with Ollama: {e}")
        return False
    
    return True


async def demo_with_openai(prompt: str):
    """Demo using OpenAI."""
    print("🤖 Using OpenAI")
    print("-" * 25)
    
    # Check credentials
    available, missing = check_openai_credentials()
    if not available:
        print(f"❌ Missing OpenAI API key")
        print("Please set environment variable:")
        print("   export OPENAI_API_KEY='your-api-key'")
        return False
    
    print("✅ OpenAI API key found")
    
    try:
        # Create OpenAI provider
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        print(f"📝 Using model: {model}")
        
        llm_provider = OpenAIProvider(
            model=model,
            timeout=120
        )
        
        # Set up simulated plotter with visualization
        plotter = SimulatedPlotter(port="OPENAI_DEMO", visualize=True)
        
        # Get configuration
        config = get_config()
        
        # Create workflow - pass the underlying llama-index LLM instance
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider.llm,  # Use .llm to get the raw llama-index instance
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ Calling OpenAI...")
        
        # Execute the workflow
        result = await workflow.run(prompt=prompt)
        
        if result and result.get('commands_count', 0) > 0:
            print(f"✅ Success! Generated {result['commands_count']} G-code commands")
            
            # Show G-code preview
            print("\n📋 Generated G-code:")
            gcode_lines = result.get('gcode', '').split('\n')[:8]
            for i, line in enumerate(gcode_lines, 1):
                print(f"   {i:2d}. {line}")
            
            if len(result.get('gcode', '').split('\n')) > 8:
                print(f"   ... and more commands")
            
            print("\n🖼️  Check the visualization window to see the drawing!")
            
        else:
            print("❌ No G-code generated. Check the LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Error with OpenAI: {e}")
        return False
    
    return True


async def demo_with_gemini(prompt: str):
    """Demo using Google Gemini."""
    print("💎 Using Google Gemini")
    print("-" * 25)
    
    # Check credentials
    available, missing = check_gemini_credentials()
    if not available:
        print(f"❌ Missing Google API key")
        print("Please set environment variable:")
        print("   export GOOGLE_API_KEY='your-api-key'")
        return False
    
    print("✅ Google API key found")
    
    try:
        # Create Gemini provider
        model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")
        print(f"📝 Using model: {model}")
        
        llm_provider = GeminiProvider(
            model=model,
            timeout=120
        )
        
        # Set up simulated plotter with visualization
        plotter = SimulatedPlotter(port="GEMINI_DEMO", visualize=True)
        
        # Get configuration
        config = get_config()
        
        # Create workflow - pass the underlying llama-index LLM instance
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider.llm,  # Use .llm to get the raw llama-index instance
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ Calling Gemini...")
        
        # Execute the workflow
        result = await workflow.run(prompt=prompt)
        
        if result and result.get('commands_count', 0) > 0:
            print(f"✅ Success! Generated {result['commands_count']} G-code commands")
            
            # Show G-code preview
            print("\n📋 Generated G-code:")
            gcode_lines = result.get('gcode', '').split('\n')[:8]
            for i, line in enumerate(gcode_lines, 1):
                print(f"   {i:2d}. {line}")
            
            if len(result.get('gcode', '').split('\n')) > 8:
                print(f"   ... and more commands")
            
            print("\n🖼️  Check the visualization window to see the drawing!")
            
        else:
            print("❌ No G-code generated. Check the LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Error with Gemini: {e}")
        return False
    
    return True


async def demo_with_azure(prompt: str):
    """Demo using Azure OpenAI."""
    print("☁️  Using Azure OpenAI")
    print("-" * 25)
    
    # Check credentials
    available, missing = check_azure_credentials()
    if not available:
        print(f"❌ Missing Azure credentials: {', '.join(missing)}")
        print("Please set environment variables:")
        print("   export GPT4_API_KEY='your-api-key'")
        print("   export GPT4_ENDPOINT='https://your-resource.openai.azure.com/'")
        print("   export GPT4_API_VERSION='2024-02-15-preview'")
        return False
    
    print("✅ Azure OpenAI credentials found")
    
    try:
        # Create Azure OpenAI provider
        llm_provider = AzureOpenAIProvider(
            model=os.getenv("GPT4_MODEL", "gpt-4o"),
            deployment_name=os.getenv("GPT4_DEPLOYMENT", "gpt-4o-gs"),
            timeout=60
        )
        
        # Set up simulated plotter with visualization
        plotter = SimulatedPlotter(port="AZURE_DEMO", visualize=True)
        
        # Get configuration
        config = get_config()
        
        # Create workflow - pass the underlying llama-index LLM instance
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider.llm,  # Use .llm to get the raw llama-index instance
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ Calling Azure OpenAI...")
        
        # Execute the workflow
        result = await workflow.run(prompt=prompt)
        
        if result and result.get('commands_count', 0) > 0:
            print(f"✅ Success! Generated {result['commands_count']} G-code commands")
            
            # Show G-code preview
            print("\n📋 Generated G-code:")
            gcode_lines = result.get('gcode', '').split('\n')[:8]
            for i, line in enumerate(gcode_lines, 1):
                print(f"   {i:2d}. {line}")
            
            if len(result.get('gcode', '').split('\n')) > 8:
                print(f"   ... and more commands")
            
            print("\n🖼️  Check the visualization window to see the drawing!")
            
        else:
            print("❌ No G-code generated. Check the LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Error with Azure OpenAI: {e}")
        return False
    
    return True


async def demo_strategy_selection(prompt: str):
    """Demonstrate automatic strategy selection."""
    print(f"\n🧠 Strategy Selection for: '{prompt}'")
    print("-" * 40)
    
    try:
        selector = StrategySelector()
        strategy = selector.select_strategy(prompt)
        
        print(f"📊 Selected strategy: {strategy.__class__.__name__}")
        
        # Analyze the prompt
        analysis = selector.analyze_prompt_complexity(prompt)
        print(f"📈 Complexity analysis:")
        print(f"   • Requires curves: {analysis.requires_curves}")
        print(f"   • Estimated commands: {analysis.estimated_commands}")
        print(f"   • Complexity level: {analysis.complexity_level.value}")
        print(f"   • Confidence score: {analysis.confidence_score:.2f}")
        
    except Exception as e:
        print(f"❌ Strategy selection error: {e}")


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="PromptPlot LLM Demo")
    parser.add_argument(
        "--provider", 
        choices=["openai", "gemini", "azure", "ollama", "auto"], 
        default="auto",
        help="LLM provider to use (default: auto-detect)"
    )
    parser.add_argument(
        "--prompt", 
        default="Draw a simple house with a door and two windows",
        help="Drawing prompt to send to the LLM"
    )
    parser.add_argument(
        "--no-strategy", 
        action="store_true",
        help="Skip strategy selection demo"
    )
    
    args = parser.parse_args()
    
    print("🎨 PromptPlot v2.0 LLM Demo")
    print("=" * 35)
    print(f"Prompt: '{args.prompt}'")
    print()
    
    async def run_demo():
        success = False
        
        # Show strategy selection first
        if not args.no_strategy:
            await demo_strategy_selection(args.prompt)
        
        if args.provider == "auto":
            # Auto-detect available provider (priority: OpenAI > Gemini > Azure > Ollama)
            openai_available, _ = check_openai_credentials()
            gemini_available, _ = check_gemini_credentials()
            azure_available, _ = check_azure_credentials()
            ollama_available, _ = check_ollama_available()
            
            if openai_available:
                print("🔍 Auto-detected: OpenAI API key found")
                success = await demo_with_openai(args.prompt)
            elif gemini_available:
                print("🔍 Auto-detected: Google API key found")
                success = await demo_with_gemini(args.prompt)
            elif azure_available:
                print("🔍 Auto-detected: Azure OpenAI credentials found")
                success = await demo_with_azure(args.prompt)
            elif ollama_available:
                print("🔍 Auto-detected: Ollama is available")
                success = await demo_with_ollama(args.prompt)
            else:
                print("❌ No LLM provider available!")
                print("\nOptions:")
                print("1. Set OPENAI_API_KEY for OpenAI")
                print("2. Set GOOGLE_API_KEY for Gemini")
                print("3. Set GPT4_API_KEY, GPT4_ENDPOINT for Azure OpenAI")
                print("4. Install and run Ollama: https://ollama.ai/")
                return False
        
        elif args.provider == "openai":
            success = await demo_with_openai(args.prompt)
        elif args.provider == "gemini":
            success = await demo_with_gemini(args.prompt)
        elif args.provider == "azure":
            success = await demo_with_azure(args.prompt)
        elif args.provider == "ollama":
            success = await demo_with_ollama(args.prompt)
        
        if success:
            print("\n🎉 Demo completed successfully!")
            print("\nNext steps:")
            print("• Try different prompts with --prompt 'your prompt here'")
            print("• Try different providers with --provider openai/gemini/azure/ollama")
            print("• Check examples/basic/ for more examples")
        
        return success
    
    try:
        success = asyncio.run(run_demo())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()