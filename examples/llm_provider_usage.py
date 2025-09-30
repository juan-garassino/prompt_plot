#!/usr/bin/env python3
"""
Example usage of the LLM Provider Abstraction Layer

This example demonstrates how to use the new LLM provider abstraction
layer and template management system in PromptPlot v2.0.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from promptplot.llm.providers import create_llm_provider, LLMProviderError
from promptplot.llm.templates import get_template_manager, format_template


async def example_azure_openai():
    """Example using Azure OpenAI provider"""
    print("=== Azure OpenAI Provider Example ===")
    
    try:
        # Create Azure OpenAI provider
        # In real usage, these would come from environment variables
        provider = create_llm_provider(
            "azure_openai",
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            api_key=os.environ.get("GPT4_API_KEY", "your_api_key_here"),
            api_version=os.environ.get("GPT4_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.environ.get("GPT4_ENDPOINT", "https://your-resource.openai.azure.com"),
            timeout=30
        )
        
        print(f"✓ Created provider: {provider.provider_name}")
        
        # Use template to create a prompt
        prompt = format_template(
            "gcode_program",
            prompt="draw a simple square with 50mm sides"
        )
        
        print("Generated prompt:")
        print(prompt[:200] + "...")
        
        # Note: Actual LLM calls would require valid API credentials
        print("(Skipping actual LLM call - requires valid API credentials)")
        
        # Example of how you would use it:
        # response = await provider.acomplete(prompt)
        # print(f"LLM Response: {response}")
        
    except LLMProviderError as e:
        print(f"Provider error: {e.message}")
        print(f"Details: {e.details}")
    except Exception as e:
        print(f"Error: {e}")


async def example_ollama():
    """Example using Ollama provider"""
    print("\n=== Ollama Provider Example ===")
    
    try:
        # Create Ollama provider
        provider = create_llm_provider(
            "ollama",
            model="llama3.2:3b",
            request_timeout=30000  # 30 seconds in milliseconds
        )
        
        print(f"✓ Created provider: {provider.provider_name}")
        
        # Use template for sequential command generation
        prompt = format_template(
            "next_command",
            prompt="draw a circle with radius 25mm",
            history="Step 1: G0 X0 Y0 Z5\nStep 2: M5\nStep 3: G0 X25 Y0"
        )
        
        print("Generated prompt:")
        print(prompt[:200] + "...")
        
        # Note: Actual LLM calls would require Ollama to be running
        print("(Skipping actual LLM call - requires Ollama server running)")
        
        # Example of how you would use it:
        # response = await provider.acomplete(prompt)
        # print(f"LLM Response: {response}")
        
    except LLMProviderError as e:
        print(f"Provider error: {e.message}")
        print(f"Details: {e.details}")
    except Exception as e:
        print(f"Error: {e}")


def example_template_management():
    """Example of template management features"""
    print("\n=== Template Management Example ===")
    
    # Get the template manager
    manager = get_template_manager()
    
    # List all available templates
    templates = manager.list_templates()
    print(f"Available templates: {templates}")
    
    # Get information about each template
    for template_name in templates:
        info = manager.get_template_info(template_name)
        print(f"\nTemplate: {template_name}")
        print(f"  Description: {info['description']}")
        print(f"  Required parameters: {info['required_parameters']}")
        print(f"  Optional parameters: {info['optional_parameters']}")
    
    # Example of template validation
    print("\n--- Template Validation Example ---")
    
    # Valid parameters
    validation = manager.validate_template_parameters(
        "next_command",
        {"prompt": "draw a line", "history": "G0 X0 Y0"}
    )
    print(f"Valid parameters: {validation.is_valid}")
    
    # Invalid parameters (missing required)
    validation = manager.validate_template_parameters(
        "next_command",
        {"prompt": "draw a line"}  # Missing 'history'
    )
    print(f"Missing parameters: {validation.is_valid}")
    print(f"Missing: {validation.missing_parameters}")
    
    # Extra parameters
    validation = manager.validate_template_parameters(
        "gcode_program",
        {"prompt": "draw a square", "extra_param": "not needed"}
    )
    print(f"Extra parameters: {validation.is_valid}")
    print(f"Extra: {validation.extra_parameters}")


def example_error_handling():
    """Example of error handling with reflection template"""
    print("\n=== Error Handling Example ===")
    
    # Simulate an error scenario
    wrong_llm_output = '{"command": "INVALID", "x": "not_a_number"}'
    error_message = "Invalid command type and coordinate format"
    
    # Use reflection template to create error correction prompt
    reflection_prompt = format_template(
        "reflection",
        wrong_answer=wrong_llm_output,
        error=error_message
    )
    
    print("Generated reflection prompt:")
    print(reflection_prompt[:300] + "...")
    
    print("\nThis prompt would be sent to the LLM to help it correct its previous error.")


async def example_workflow_integration():
    """Example of how this integrates with workflows"""
    print("\n=== Workflow Integration Example ===")
    
    # This shows how the abstraction layer would be used in a workflow
    
    # 1. Create provider based on configuration
    provider_config = {
        "type": "ollama",  # Could be "azure_openai"
        "model": "llama3.2:3b",
        "request_timeout": 30000
    }
    
    try:
        provider = create_llm_provider(
            provider_config["type"],
            **{k: v for k, v in provider_config.items() if k != "type"}
        )
        
        print(f"✓ Created {provider.provider_name} provider for workflow")
        
        # 2. Use templates for different workflow stages
        
        # Initial G-code generation
        initial_prompt = format_template(
            "gcode_program",
            prompt="draw a house with a door and two windows"
        )
        print("✓ Generated initial G-code prompt")
        
        # Sequential command generation (for advanced workflows)
        next_prompt = format_template(
            "next_command_enhanced",
            prompt="continue drawing the house",
            history="G0 X0 Y0\nM5\nG0 X10 Y10\nM3 S255"
        )
        print("✓ Generated next command prompt")
        
        # Error correction (if validation fails)
        error_prompt = format_template(
            "reflection",
            wrong_answer='{"invalid": "response"}',
            error="JSON parsing failed"
        )
        print("✓ Generated error correction prompt")
        
        print("\nWorkflow would now use these prompts with the provider to generate G-code")
        
    except Exception as e:
        print(f"Workflow integration error: {e}")


async def main():
    """Run all examples"""
    print("PromptPlot v2.0 LLM Provider Abstraction Layer Examples")
    print("=" * 60)
    
    # Run examples
    await example_azure_openai()
    await example_ollama()
    example_template_management()
    example_error_handling()
    await example_workflow_integration()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("\nKey benefits of the LLM Provider Abstraction Layer:")
    print("• Unified interface for different LLM providers")
    print("• Centralized template management with validation")
    print("• Consistent error handling and recovery")
    print("• Easy provider switching and configuration")
    print("• Type-safe parameter validation")


if __name__ == "__main__":
    asyncio.run(main())