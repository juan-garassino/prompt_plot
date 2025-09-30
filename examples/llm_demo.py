#!/usr/bin/env python3
"""
LLM Demo for PromptPlot v2.0

This example demonstrates using a real LLM (Ollama or Azure OpenAI) to generate
G-code from natural language prompts. This is the core functionality of PromptPlot.

Requirements:
- For Ollama: Install Ollama and pull a model (e.g., llama3.2:3b)
- For Azure OpenAI: Set environment variables for API access

Usage:
    python examples/llm_demo.py --provider ollama
    python examples/llm_demo.py --provider azure
    python examples/llm_demo.py --prompt "Draw a heart shape"
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
    from promptplot.llm.providers import OllamaProvider, AzureOpenAIProvider
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
    required_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
    missing = [var for var in required_vars if not os.getenv(var)]
    return len(missing) == 0, missing


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
        
        # Create workflow
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider,
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ This may take 10-30 seconds...")
        
        # Execute the workflow
        result = await workflow.run(prompt)
        
        if result and hasattr(result, 'commands') and result.commands:
            print(f"✅ Success! Generated {len(result.commands)} G-code commands")
            
            # Show first few commands
            print("\n📋 First few G-code commands:")
            for i, cmd in enumerate(result.commands[:8], 1):
                comment = f" ; {cmd.comment}" if hasattr(cmd, 'comment') and cmd.comment else ""
                print(f"   {i:2d}. {cmd.command}{comment}")
            
            if len(result.commands) > 8:
                print(f"   ... and {len(result.commands) - 8} more commands")
            
            # Show drawing bounds if available
            if hasattr(result, 'bounds'):
                print(f"\n📐 Drawing bounds: {result.bounds}")
            
            print("\n🖼️  Check the visualization window to see the drawing!")
            
        else:
            print("❌ No G-code generated. Check the LLM response.")
            return False
            
    except Exception as e:
        print(f"❌ Error with Ollama: {e}")
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
        print("   export AZURE_OPENAI_API_KEY='your-api-key'")
        print("   export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'")
        print("   export AZURE_OPENAI_DEPLOYMENT='your-deployment-name'  # optional")
        return False
    
    print("✅ Azure OpenAI credentials found")
    
    try:
        # Create Azure OpenAI provider
        llm_provider = AzureOpenAIProvider(
            model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            timeout=60
        )
        
        # Set up simulated plotter with visualization
        plotter = SimulatedPlotter(port="AZURE_DEMO", visualize=True)
        
        # Get configuration
        config = get_config()
        
        # Create workflow
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider,
            max_retries=3,
            max_steps=10
        )
        
        print(f"🎨 Generating G-code for: '{prompt}'")
        print("⏳ Calling Azure OpenAI...")
        
        # Execute the workflow
        result = await workflow.run(prompt)
        
        if result and hasattr(result, 'commands') and result.commands:
            print(f"✅ Success! Generated {len(result.commands)} G-code commands")
            
            # Show first few commands
            print("\n📋 Generated G-code commands:")
            for i, cmd in enumerate(result.commands[:8], 1):
                comment = f" ; {cmd.comment}" if hasattr(cmd, 'comment') and cmd.comment else ""
                print(f"   {i:2d}. {cmd.command}{comment}")
            
            if len(result.commands) > 8:
                print(f"   ... and {len(result.commands) - 8} more commands")
            
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
        choices=["ollama", "azure", "auto"], 
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
            # Auto-detect available provider
            ollama_available, _ = check_ollama_available()
            azure_available, _ = check_azure_credentials()
            
            if ollama_available:
                print("🔍 Auto-detected: Ollama is available")
                success = await demo_with_ollama(args.prompt)
            elif azure_available:
                print("🔍 Auto-detected: Azure OpenAI credentials found")
                success = await demo_with_azure(args.prompt)
            else:
                print("❌ No LLM provider available!")
                print("\nOptions:")
                print("1. Install and run Ollama: https://ollama.ai/")
                print("2. Set up Azure OpenAI credentials")
                print("3. Use mock demo: python examples/quick_start.py")
                return False
                
        elif args.provider == "ollama":
            success = await demo_with_ollama(args.prompt)
        elif args.provider == "azure":
            success = await demo_with_azure(args.prompt)
        
        if success:
            print("\n🎉 Demo completed successfully!")
            print("\nNext steps:")
            print("• Try different prompts with --prompt 'your prompt here'")
            print("• Check examples/basic/ for more examples")
            print("• Use the CLI: promptplot workflow simple 'Draw a circle'")
        
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