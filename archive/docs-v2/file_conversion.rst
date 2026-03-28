File Conversion and Plotting
============================

PromptPlot supports direct conversion and plotting of various file formats, allowing you to plot existing designs without writing prompts.

Supported File Formats
-----------------------

SVG Files
~~~~~~~~~

Scalable Vector Graphics files are fully supported with path extraction and optimization.

.. code-block:: python

   from promptplot.workflows import FilePlottingWorkflow
   from promptplot.converters import SVGConverter
   
   # Direct plotting
   workflow = FilePlottingWorkflow(plotter=plotter)
   result = await workflow.plot_file("drawing.svg")
   
   # Manual conversion
   converter = SVGConverter()
   gcode_program = converter.convert("drawing.svg")

**Supported SVG Features:**
* Paths (lines, curves, arcs)
* Basic shapes (rectangles, circles, ellipses)
* Groups and layers
* Transformations (scale, rotate, translate)
* Stroke properties

**SVG Conversion Options:**
* Resolution control
* Path simplification
* Pen-up/pen-down optimization
* Coordinate system mapping

G-code Files
~~~~~~~~~~~~

Direct G-code files can be loaded, validated, and executed.

.. code-block:: python

   from promptplot.converters import GCodeLoader
   
   # Load and validate G-code
   loader = GCodeLoader()
   program = loader.load("commands.gcode")
   
   # Plot directly
   result = await workflow.plot_file("commands.gcode")

**G-code Features:**
* Syntax validation
* Command optimization
* Coordinate transformation
* Safety checks
* Multiple G-code dialects

DXF Files
~~~~~~~~~

AutoCAD DXF files for CAD integration.

.. code-block:: python

   from promptplot.converters import DXFConverter
   
   converter = DXFConverter()
   gcode_program = converter.convert("cad_drawing.dxf")

**Supported DXF Entities:**
* Lines
* Polylines
* Circles and arcs
* Splines
* Blocks and inserts
* Layers

HPGL Files
~~~~~~~~~~

Legacy HP Graphics Language files.

.. code-block:: python

   from promptplot.converters import HPGLConverter
   
   converter = HPGLConverter()
   gcode_program = converter.convert("legacy_plot.hpgl")

**HPGL Commands:**
* Pen up/down (PU/PD)
* Plot absolute/relative (PA/PR)
* Circle and arc commands
* Text plotting

JSON Files
~~~~~~~~~~

Programmatic G-code generation from JSON data.

.. code-block:: python

   from promptplot.converters import JSONConverter
   
   # JSON format
   json_data = {
       "commands": [
           {"command": "G0", "x": 0, "y": 0},
           {"command": "G1", "x": 50, "y": 50, "f": 1000}
       ],
       "metadata": {
           "title": "Simple Line",
           "units": "mm"
       }
   }
   
   converter = JSONConverter()
   gcode_program = converter.convert_from_dict(json_data)

Image Files
~~~~~~~~~~~

Basic bitmap image conversion for simple line art.

.. code-block:: python

   from promptplot.converters import ImageConverter
   
   converter = ImageConverter()
   gcode_program = converter.convert("line_art.png", 
                                   edge_detection=True,
                                   threshold=128)

**Image Processing:**
* Edge detection
* Contour extraction
* Path tracing
* Threshold adjustment

File Detection and Auto-Conversion
----------------------------------

Automatic Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~

PromptPlot automatically detects file formats:

.. code-block:: python

   from promptplot.converters import FileDetector
   
   detector = FileDetector()
   file_type = detector.detect_format("unknown_file.ext")
   
   # Auto-select converter
   converter = detector.get_converter(file_type)
   gcode_program = converter.convert("unknown_file.ext")

Batch Processing
~~~~~~~~~~~~~~~~

Process multiple files at once:

.. code-block:: python

   from promptplot.workflows import FilePlottingWorkflow
   
   workflow = FilePlottingWorkflow(plotter=plotter)
   
   files = ["drawing1.svg", "drawing2.dxf", "drawing3.gcode"]
   results = await workflow.plot_files_batch(files)
   
   for file, result in zip(files, results):
       print(f"{file}: {result.status}")

Conversion Options and Settings
-------------------------------

SVG Conversion Settings
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import SVGConverter, SVGSettings
   
   settings = SVGSettings(
       resolution=0.1,           # Path resolution in mm
       simplify_paths=True,      # Simplify complex paths
       optimize_order=True,      # Optimize drawing order
       pen_up_height=5,         # Pen up Z position
       pen_down_height=0,       # Pen down Z position
       travel_speed=3000,       # Travel speed (mm/min)
       draw_speed=1000,         # Drawing speed (mm/min)
       scale_factor=1.0,        # Scale multiplier
       offset_x=0,              # X offset
       offset_y=0               # Y offset
   )
   
   converter = SVGConverter(settings)
   gcode_program = converter.convert("drawing.svg")

DXF Conversion Settings
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import DXFConverter, DXFSettings
   
   settings = DXFSettings(
       layers=["0", "PLOT"],     # Layers to include
       units="mm",               # Drawing units
       arc_resolution=0.1,      # Arc approximation resolution
       text_to_paths=True,      # Convert text to paths
       ignore_blocks=False,     # Include block references
       line_weight_mapping={    # Line weight to speed mapping
           0.1: 1500,
           0.2: 1200,
           0.5: 800
       }
   )
   
   converter = DXFConverter(settings)

Image Conversion Settings
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import ImageConverter, ImageSettings
   
   settings = ImageSettings(
       edge_detection="canny",   # Edge detection algorithm
       threshold=128,            # Binary threshold
       min_contour_length=10,   # Minimum contour length
       smoothing=True,          # Path smoothing
       invert=False,            # Invert colors
       dpi=300                  # Image resolution
   )
   
   converter = ImageConverter(settings)

File Plotting Workflow
----------------------

Basic File Plotting
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.workflows import FilePlottingWorkflow
   from promptplot.plotter import SerialPlotter
   
   async def plot_file_example():
       plotter = SerialPlotter(port="/dev/ttyUSB0")
       workflow = FilePlottingWorkflow(plotter=plotter)
       
       # Plot with default settings
       result = await workflow.plot_file("drawing.svg")
       
       print(f"Plotted {len(result.commands)} commands")
       print(f"Execution time: {result.execution_time:.2f}s")

Advanced File Plotting
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def advanced_plot_example():
       workflow = FilePlottingWorkflow(
           plotter=plotter,
           preview_enabled=True,      # Show preview before plotting
           validation_enabled=True,   # Validate G-code
           optimization_enabled=True  # Optimize paths
       )
       
       # Plot with custom settings
       result = await workflow.plot_file(
           "complex_drawing.dxf",
           scale=2.0,                # Scale 2x
           offset=(10, 10),          # Offset position
           rotation=45,              # Rotate 45 degrees
           preview=True              # Show preview
       )

File Plotting with Preview
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def plot_with_preview():
       workflow = FilePlottingWorkflow(plotter=plotter)
       
       # Generate preview
       preview = await workflow.generate_preview("drawing.svg")
       
       # Show preview (matplotlib visualization)
       preview.show()
       
       # Confirm and plot
       if input("Plot this drawing? (y/n): ").lower() == 'y':
           result = await workflow.plot_file("drawing.svg")

Batch File Processing
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def batch_plot_example():
       workflow = FilePlottingWorkflow(plotter=plotter)
       
       # Define batch job
       batch_job = {
           "files": [
               {"path": "logo.svg", "scale": 0.5},
               {"path": "border.dxf", "offset": (0, 100)},
               {"path": "text.hpgl", "rotation": 90}
           ],
           "settings": {
               "pause_between": 2.0,    # Pause between files
               "validate_all": True,    # Validate before starting
               "continue_on_error": False
           }
       }
       
       results = await workflow.plot_batch(batch_job)

File Conversion Examples
------------------------

SVG to G-code Conversion
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import SVGConverter
   
   # Basic conversion
   converter = SVGConverter()
   gcode_program = converter.convert("logo.svg")
   
   # Save G-code
   with open("logo.gcode", "w") as f:
       for command in gcode_program.commands:
           f.write(f"{command.to_gcode()}\n")

DXF Processing
~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import DXFConverter
   
   converter = DXFConverter()
   
   # Convert specific layers only
   gcode_program = converter.convert(
       "technical_drawing.dxf",
       layers=["OUTLINE", "DETAILS"],
       scale=2.0
   )

Image Tracing
~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import ImageConverter
   
   converter = ImageConverter()
   
   # Convert photo to line art
   gcode_program = converter.convert(
       "photo.jpg",
       edge_detection="canny",
       threshold=100,
       smoothing=True
   )

Performance Optimization
------------------------

Path Optimization
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import PathOptimizer
   
   optimizer = PathOptimizer()
   
   # Optimize drawing order
   optimized_program = optimizer.optimize_travel_distance(gcode_program)
   
   # Reduce pen lifts
   optimized_program = optimizer.minimize_pen_lifts(gcode_program)

Memory Management
~~~~~~~~~~~~~~~~~

For large files, use streaming conversion:

.. code-block:: python

   from promptplot.converters import SVGConverter
   
   converter = SVGConverter()
   
   # Stream large files
   async for command_batch in converter.convert_stream("large_file.svg"):
       await plotter.send_commands(command_batch)

Caching
~~~~~~~

Cache converted files for faster replotting:

.. code-block:: python

   from promptplot.converters import ConversionCache
   
   cache = ConversionCache()
   
   # Check cache first
   if cache.has_cached("drawing.svg"):
       gcode_program = cache.get_cached("drawing.svg")
   else:
       gcode_program = converter.convert("drawing.svg")
       cache.store("drawing.svg", gcode_program)

Error Handling and Validation
------------------------------

File Validation
~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.converters import FileValidator
   
   validator = FileValidator()
   
   # Validate before conversion
   validation_result = validator.validate_file("drawing.svg")
   
   if validation_result.is_valid:
       gcode_program = converter.convert("drawing.svg")
   else:
       print(f"Validation errors: {validation_result.errors}")

Conversion Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.core.exceptions import ConversionError
   
   try:
       gcode_program = converter.convert("problematic_file.dxf")
   except ConversionError as e:
       print(f"Conversion failed: {e}")
       print(f"Suggestions: {e.suggestions}")

G-code Validation
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.core.models import GCodeValidator
   
   validator = GCodeValidator()
   
   # Validate generated G-code
   validation_result = validator.validate_program(gcode_program)
   
   if not validation_result.is_valid:
       print("G-code validation errors:")
       for error in validation_result.errors:
           print(f"  Line {error.line}: {error.message}")

Best Practices
--------------

1. **File Preparation**: Clean up source files before conversion
2. **Preview First**: Always preview complex files before plotting
3. **Validate Input**: Check file format and content validity
4. **Optimize Paths**: Use path optimization for better performance
5. **Test Settings**: Test conversion settings on small samples first
6. **Backup Originals**: Keep original files safe
7. **Monitor Progress**: Use progress monitoring for large files
8. **Error Recovery**: Implement proper error handling and recovery