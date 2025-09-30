# PromptPlot v2.0

A modular, extensible pen plotter control system that transforms natural language prompts into G-code instructions through intelligent LLM processing and computer vision feedback.

## Features

- **Modular Architecture**: Clean separation of concerns with distinct modules for core functionality, LLM processing, computer vision, and plotter communication
- **Dual Drawing Strategies**: Optimized handling for both orthogonal (straight-line) and non-orthogonal (curved) drawing patterns
- **Computer Vision Integration**: Real-time visual feedback for intelligent drawing decisions
- **Multiple LLM Providers**: Support for Azure OpenAI, Ollama, and other LLM services
- **Flexible Plotter Interface**: Unified interface supporting both real hardware and simulated plotters
- **Enhanced Visualization**: Real-time drawing preview and comprehensive progress monitoring

## Project Structure

```
promptplot/                 # Main package
├── core/                   # Core components (models, base classes, exceptions)
├── workflows/              # Different workflow implementations
├── llm/                    # LLM provider abstractions and integrations
├── plotter/                # Plotter interfaces and communication
├── strategies/             # Drawing strategy implementations
├── vision/                 # Computer vision components
└── utils/                  # Utilities (config, logging)

boilerplates/               # Original v1.0 files for reference
results/                    # Generated outputs and results
├── gcode/                  # Generated G-code files
├── images/                 # Captured images and visual outputs
├── visualizations/         # Generated visualization files
├── reports/                # Drawing session reports
└── logs/                   # Execution logs

lib/                        # External libraries and dependencies
.kiro/                      # Kiro IDE configuration and specs
```

## Installation

```bash
# Install in development mode
pip install -e .

# Or install from requirements
pip install -r requirements.txt
```

## Quick Start

```python
from promptplot import BasePromptPlotWorkflow
from promptplot.workflows import SimpleBatchWorkflow
from promptplot.plotter import SimulatedPlotter

# Create a simulated plotter for testing
plotter = SimulatedPlotter(visualize=True)

# Initialize workflow
workflow = SimpleBatchWorkflow(plotter=plotter)

# Generate and execute G-code from prompt
result = await workflow.execute("Draw a simple square")
```

## Development

This project follows the spec-driven development methodology. See `.kiro/specs/pen-plotter-v2/` for detailed requirements, design, and implementation tasks.

### Migration from v1.0

The original monolithic files have been moved to `boilerplates/` for reference during refactoring:
- `generate_llm_simple.py` → `promptplot/workflows/simple_batch.py`
- `generate_llm_advanced.py` → `promptplot/workflows/advanced_sequential.py`
- `llm_stream_simple.py` → `promptplot/workflows/simple_streaming.py`
- `llm_stream_advanced.py` → `promptplot/workflows/advanced_streaming.py`

## License

MIT License - see LICENSE file for details.