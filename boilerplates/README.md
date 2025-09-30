# Boilerplate Files

This directory contains the original monolithic implementation files from PromptPlot v1.0.
These files serve as reference material during the refactoring process to PromptPlot v2.0's
modular architecture.

## Original Files

- `generate_llm_simple.py` - Simple batch G-code generation workflow
- `generate_llm_advanced.py` - Advanced sequential G-code generation workflow  
- `generate_llm_advanced_first_code.py` - First iteration of advanced workflow
- `llm_stream_simple.py` - Simple streaming G-code generation workflow
- `llm_stream_advanced.py` - Advanced streaming G-code generation workflow
- `test_llm_stream.py` - Tests for streaming functionality
- `test.py` - General test file

## Usage

These files contain the original implementation patterns and logic that will be
extracted and refactored into the new modular structure. They should be referenced
during the refactoring process but not used directly in the new system.

## Migration Status

- [ ] Simple batch workflow → `promptplot/workflows/simple_batch.py`
- [ ] Advanced sequential workflow → `promptplot/workflows/advanced_sequential.py`
- [ ] Simple streaming workflow → `promptplot/workflows/simple_streaming.py`
- [ ] Advanced streaming workflow → `promptplot/workflows/advanced_streaming.py`
- [ ] Common models extracted → `promptplot/core/models.py`
- [ ] Base workflow extracted → `promptplot/core/base_workflow.py`
- [ ] Exception handling extracted → `promptplot/core/exceptions.py`