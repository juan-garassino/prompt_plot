PromptPlot v2.0 Documentation
=============================

Welcome to PromptPlot v2.0, a modular, extensible pen plotter control system that transforms natural language prompts into G-code instructions through intelligent LLM processing and computer vision feedback.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   api_reference
   workflows
   configuration
   file_conversion
   troubleshooting
   examples

Quick Start
-----------

.. code-block:: python

   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SimulatedPlotter
   
   # Create a simulated plotter for testing
   plotter = SimulatedPlotter(visualize=True)
   
   # Initialize workflow
   workflow = SimpleBatchWorkflow(plotter=plotter)
   
   # Generate and execute G-code from prompt
   result = await workflow.execute("Draw a simple square")

Features
--------

* **Modular Architecture**: Clean separation of concerns with distinct modules
* **Dual Drawing Strategies**: Optimized for both orthogonal and non-orthogonal patterns
* **Computer Vision Integration**: Real-time visual feedback for intelligent decisions
* **Multiple LLM Providers**: Support for Azure OpenAI, Ollama, and other services
* **Flexible Plotter Interface**: Unified interface for real hardware and simulation
* **Enhanced Visualization**: Real-time drawing preview and progress monitoring

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`