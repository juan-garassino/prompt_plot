Examples
========

This section provides comprehensive examples for using PromptPlot in various scenarios.

Basic Examples
--------------

Simple Drawing
~~~~~~~~~~~~~~

Create a basic drawing with the simplest workflow:

.. code-block:: python

   import asyncio
   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SimulatedPlotter
   
   async def simple_drawing():
       """Create a simple square drawing."""
       # Set up simulated plotter with visualization
       plotter = SimulatedPlotter(visualize=True)
       
       # Initialize workflow
       workflow = SimpleBatchWorkflow(plotter=plotter)
       
       # Generate and execute G-code
       result = await workflow.execute("Draw a 50mm square centered at origin")
       
       print(f"Generated {len(result.commands)} G-code commands")
       print(f"Execution time: {result.execution_time:.2f} seconds")
       
       return result
   
   # Run the example
   if __name__ == "__main__":
       asyncio.run(simple_drawing())

Real Hardware Connection
~~~~~~~~~~~~~~~~~~~~~~~~

Connect to actual plotter hardware:

.. code-block:: python

   import asyncio
   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SerialPlotter
   
   async def hardware_drawing():
       """Draw using real hardware."""
       # Connect to real plotter
       plotter = SerialPlotter(
           port="/dev/ttyUSB0",  # Adjust for your system
           baud_rate=115200,
           timeout=5
       )
       
       try:
           # Test connection
           await plotter.connect()
           print("Connected to plotter successfully")
           
           # Initialize workflow
           workflow = SimpleBatchWorkflow(plotter=plotter)
           
           # Draw something simple first
           result = await workflow.execute("Draw a small circle with 10mm radius")
           
           print(f"Drawing completed: {result.success}")
           
       except Exception as e:
           print(f"Error: {e}")
       finally:
           await plotter.disconnect()
   
   if __name__ == "__main__":
       asyncio.run(hardware_drawing())

Advanced Examples
-----------------

Complex Drawing with Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use advanced workflow with validation and error recovery:

.. code-block:: python

   import asyncio
   from promptplot.workflows import AdvancedSequentialWorkflow
   from promptplot.plotter import SimulatedPlotter
   from promptplot.config import Settings
   
   async def complex_drawing():
       """Create a complex drawing with validation."""
       # Configure settings
       settings = Settings(
           max_retries=3,
           validation_enabled=True,
           reflection_enabled=True
       )
       
       # Set up plotter with visualization
       plotter = SimulatedPlotter(
           visualize=True,
           canvas_size=(200, 200),
           save_images=True
       )
       
       # Initialize advanced workflow
       workflow = AdvancedSequentialWorkflow(
           plotter=plotter,
           settings=settings,
           max_steps=100
       )
       
       # Create complex drawing
       prompt = """
       Draw a mandala pattern with the following elements:
       1. A central circle with 20mm radius
       2. 8 petals around the circle, each 15mm long
       3. Decorative dots at the tips of each petal
       4. An outer ring with radius 50mm
       """
       
       result = await workflow.execute(prompt)
       
       print(f"Complex drawing completed:")
       print(f"  Commands generated: {len(result.commands)}")
       print(f"  Validation passes: {result.validation_passes}")
       print(f"  Retries needed: {result.retry_count}")
       
       return result
   
   if __name__ == "__main__":
       asyncio.run(complex_drawing())

File Conversion Examples
------------------------

SVG to G-code Conversion
~~~~~~~~~~~~~~~~~~~~~~~~

Convert and plot SVG files:

.. code-block:: python

   import asyncio
   from promptplot.workflows import FilePlottingWorkflow
   from promptplot.plotter import SimulatedPlotter
   from promptplot.converters import SVGConverter, SVGSettings
   
   async def svg_conversion_example():
       """Convert and plot SVG files."""
       plotter = SimulatedPlotter(visualize=True)
       workflow = FilePlottingWorkflow(plotter=plotter)
       
       # Basic SVG plotting
       result = await workflow.plot_file("examples/logo.svg")
       print(f"SVG plotted: {result.success}")
       
       # Advanced SVG conversion with custom settings
       settings = SVGSettings(
           resolution=0.1,
           scale_factor=2.0,
           optimize_order=True,
           pen_up_height=5,
           travel_speed=3000,
           draw_speed=1000
       )
       
       converter = SVGConverter(settings)
       gcode_program = converter.convert("examples/complex_drawing.svg")
       
       # Plot converted G-code
       result = await workflow.plot_gcode_program(gcode_program)
       
       print(f"Advanced SVG conversion completed:")
       print(f"  Original paths: {converter.stats.original_paths}")
       print(f"  Optimized commands: {len(gcode_program.commands)}")
       
       return result
   
   if __name__ == "__main__":
       asyncio.run(svg_conversion_example())

Configuration Examples
----------------------

Custom Configuration
~~~~~~~~~~~~~~~~~~~~

Set up custom configuration for specific use cases:

.. code-block:: python

   import asyncio
   from promptplot.config import Settings, ProfileManager
   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SerialPlotter
   
   async def custom_configuration_example():
       """Use custom configuration."""
       # Create custom settings
       settings = Settings(
           # LLM configuration
           llm_provider="azure_openai",
           azure_openai_model="gpt-4",
           azure_openai_timeout=60,
           
           # Plotter configuration
           plotter_type="serial",
           plotter_port="/dev/ttyUSB0",
           plotter_baud_rate=115200,
           
           # Workflow configuration
           max_retries=5,
           validation_enabled=True,
           
           # Visualization configuration
           visualization_enabled=True,
           save_visualizations=True,
           output_directory="results/custom_output"
       )
       
       # Apply settings
       plotter = SerialPlotter.from_settings(settings)
       workflow = SimpleBatchWorkflow.from_settings(settings, plotter=plotter)
       
       result = await workflow.execute("Draw a custom design with these settings")
       
       print(f"Custom configuration example completed: {result.success}")
       
       return result
   
   if __name__ == "__main__":
       asyncio.run(custom_configuration_example())