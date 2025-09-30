Workflows
=========

PromptPlot provides several workflow types to handle different drawing scenarios and complexity levels.

Overview
--------

Workflows are the main entry points for generating and executing G-code from prompts. Each workflow type is optimized for specific use cases:

* **Simple Batch**: Basic prompt-to-G-code generation
* **Advanced Sequential**: Step-by-step generation with validation
* **Simple Streaming**: Real-time streaming to plotter
* **Advanced Streaming**: Enhanced streaming with visualization
* **Plot Enhanced**: Computer vision integration
* **File Plotting**: Direct file conversion and plotting

Simple Batch Workflow
----------------------

The simplest workflow for basic G-code generation.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SimulatedPlotter
   
   async def simple_example():
       plotter = SimulatedPlotter()
       workflow = SimpleBatchWorkflow(plotter=plotter)
       
       result = await workflow.execute("Draw a square")
       return result

Features
~~~~~~~~

* Basic prompt processing
* G-code validation
* Simple error handling
* Batch command generation

Best For
~~~~~~~~

* Simple geometric shapes
* Quick prototyping
* Learning and testing

Advanced Sequential Workflow
----------------------------

Step-by-step generation with enhanced validation and error recovery.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import AdvancedSequentialWorkflow
   
   async def advanced_example():
       workflow = AdvancedSequentialWorkflow(
           plotter=plotter,
           max_steps=100,
           validation_enabled=True
       )
       
       result = await workflow.execute("Draw a complex mandala pattern")
       return result

Features
~~~~~~~~

* Multi-step generation
* Enhanced validation
* Automatic error recovery
* Progress tracking
* Reflection-based improvements

Best For
~~~~~~~~

* Complex drawings
* High-precision requirements
* Production use

Simple Streaming Workflow
--------------------------

Real-time streaming of G-code commands to the plotter.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import SimpleStreamingWorkflow
   
   async def streaming_example():
       workflow = SimpleStreamingWorkflow(
           plotter=plotter,
           stream_delay=0.1  # seconds between commands
       )
       
       async for command in workflow.stream("Draw a spiral"):
           print(f"Executing: {command}")

Features
~~~~~~~~

* Real-time command streaming
* Live progress monitoring
* Immediate feedback
* Cancellation support

Best For
~~~~~~~~

* Interactive drawing sessions
* Real-time visualization
* Live demonstrations

Advanced Streaming Workflow
----------------------------

Enhanced streaming with visualization and monitoring.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import AdvancedStreamingWorkflow
   
   async def advanced_streaming():
       workflow = AdvancedStreamingWorkflow(
           plotter=plotter,
           enable_visualization=True,
           monitor_progress=True
       )
       
       async for status in workflow.stream_with_monitoring("Draw a landscape"):
           print(f"Progress: {status.progress}%")

Features
~~~~~~~~

* Enhanced visualization
* Progress monitoring
* Performance metrics
* Error recovery
* Quality assessment

Best For
~~~~~~~~

* Complex real-time drawings
* Performance monitoring
* Quality control

Plot Enhanced Workflow
----------------------

Computer vision integration for intelligent drawing decisions.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import PlotEnhancedWorkflow
   from promptplot.vision import PlotAnalyzer
   
   async def vision_example():
       analyzer = PlotAnalyzer()
       workflow = PlotEnhancedWorkflow(
           plotter=plotter,
           plot_analyzer=analyzer,
           feedback_enabled=True
       )
       
       result = await workflow.execute_with_vision(
           "Draw a portrait",
           reference_image="portrait.jpg"
       )

Features
~~~~~~~~

* Computer vision integration
* Visual feedback loops
* Adaptive drawing strategies
* Image analysis
* Progress comparison

Best For
~~~~~~~~

* Artistic drawings
* Image reproduction
* Adaptive corrections
* Quality improvement

File Plotting Workflow
----------------------

Direct conversion and plotting of various file formats.

Usage
~~~~~

.. code-block:: python

   from promptplot.workflows import FilePlottingWorkflow
   
   async def file_example():
       workflow = FilePlottingWorkflow(plotter=plotter)
       
       # Plot SVG file
       result = await workflow.plot_file("drawing.svg")
       
       # Plot G-code file
       result = await workflow.plot_file("commands.gcode")
       
       # Plot DXF file
       result = await workflow.plot_file("cad_drawing.dxf")

Supported Formats
~~~~~~~~~~~~~~~~~

* **SVG**: Vector graphics files
* **G-code**: Direct G-code files
* **DXF**: CAD drawing files
* **HPGL**: Legacy plotter files
* **JSON**: Programmatic G-code data
* **Images**: Basic bitmap conversion

Features
~~~~~~~~

* Automatic format detection
* File validation
* Conversion optimization
* Batch processing
* Preview generation

Best For
~~~~~~~~

* Existing file conversion
* CAD integration
* Batch processing
* Legacy file support

Workflow Selection Guide
------------------------

Choose the right workflow based on your needs:

.. list-table::
   :header-rows: 1
   :widths: 20 20 20 20 20

   * - Use Case
     - Complexity
     - Real-time
     - Vision
     - Recommended Workflow
   * - Simple shapes
     - Low
     - No
     - No
     - Simple Batch
   * - Complex drawings
     - High
     - No
     - No
     - Advanced Sequential
   * - Live drawing
     - Low-Medium
     - Yes
     - No
     - Simple Streaming
   * - Interactive demo
     - Medium-High
     - Yes
     - Optional
     - Advanced Streaming
   * - Artistic work
     - High
     - Optional
     - Yes
     - Plot Enhanced
   * - File conversion
     - Variable
     - No
     - No
     - File Plotting

Configuration
-------------

All workflows support configuration through:

* Constructor parameters
* Configuration files
* Environment variables
* Runtime updates

Example configuration:

.. code-block:: python

   from promptplot.config import WorkflowConfig
   
   config = WorkflowConfig(
       max_retries=3,
       timeout=30,
       validation_enabled=True,
       visualization_enabled=True
   )
   
   workflow = AdvancedSequentialWorkflow(config=config)