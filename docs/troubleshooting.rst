Troubleshooting Guide
====================

This guide helps resolve common issues when using PromptPlot.

Common Issues
-------------

Installation Problems
~~~~~~~~~~~~~~~~~~~~~

**Issue: Package installation fails**

.. code-block:: bash

   ERROR: Could not find a version that satisfies the requirement promptplot

**Solutions:**

1. Update pip and try again:

.. code-block:: bash

   pip install --upgrade pip
   pip install promptplot

2. Use Python 3.8 or higher:

.. code-block:: bash

   python --version  # Should be 3.8+

3. Install in a virtual environment:

.. code-block:: bash

   python -m venv promptplot_env
   source promptplot_env/bin/activate  # Linux/Mac
   # or
   promptplot_env\Scripts\activate     # Windows
   pip install promptplot

**Issue: Missing dependencies**

.. code-block:: bash

   ModuleNotFoundError: No module named 'llama_index'

**Solution:**

Install with all dependencies:

.. code-block:: bash

   pip install promptplot[azure,ollama,dev]

LLM Provider Issues
~~~~~~~~~~~~~~~~~~~

**Issue: Azure OpenAI authentication fails**

.. code-block:: python

   AuthenticationError: Invalid API key

**Solutions:**

1. Check API key and endpoint:

.. code-block:: python

   from promptplot.config import Settings
   
   settings = Settings(
       llm_provider="azure_openai",
       azure_openai_api_key="your-key-here",
       azure_openai_endpoint="https://your-resource.openai.azure.com/"
   )

2. Verify environment variables:

.. code-block:: bash

   export AZURE_OPENAI_API_KEY="your-key"
   export AZURE_OPENAI_ENDPOINT="your-endpoint"

3. Check deployment name:

.. code-block:: python

   settings.azure_openai_deployment_name = "gpt-4"  # Must match Azure deployment

**Issue: Ollama connection fails**

.. code-block:: python

   ConnectionError: Could not connect to Ollama

**Solutions:**

1. Start Ollama service:

.. code-block:: bash

   ollama serve

2. Check if model is available:

.. code-block:: bash

   ollama list
   ollama pull llama3.2:3b  # If model not found

3. Configure correct endpoint:

.. code-block:: python

   settings = Settings(
       llm_provider="ollama",
       ollama_base_url="http://localhost:11434"
   )

Plotter Connection Issues
~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue: Serial plotter not found**

.. code-block:: python

   SerialException: could not open port '/dev/ttyUSB0'

**Solutions:**

1. Check available ports:

.. code-block:: bash

   # Linux/Mac
   ls /dev/tty*
   
   # Windows
   # Check Device Manager for COM ports

2. Check permissions (Linux/Mac):

.. code-block:: bash

   sudo usermod -a -G dialout $USER
   # Log out and back in

3. Try different port:

.. code-block:: python

   from promptplot.plotter import SerialPlotter
   
   # Try different ports
   ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"]
   for port in ports:
       try:
           plotter = SerialPlotter(port=port)
           print(f"Connected to {port}")
           break
       except Exception as e:
           print(f"Failed to connect to {port}: {e}")

**Issue: Plotter not responding**

.. code-block:: python

   TimeoutError: Plotter did not respond

**Solutions:**

1. Check baud rate:

.. code-block:: python

   plotter = SerialPlotter(port="/dev/ttyUSB0", baud_rate=115200)
   # Try: 9600, 19200, 38400, 57600, 115200

2. Increase timeout:

.. code-block:: python

   plotter = SerialPlotter(port="/dev/ttyUSB0", timeout=10)

3. Reset plotter:

.. code-block:: python

   await plotter.send_command("M112")  # Emergency stop
   await plotter.send_command("G28")   # Home axes

G-code Generation Issues
~~~~~~~~~~~~~~~~~~~~~~~~

**Issue: Invalid G-code generated**

.. code-block:: python

   ValidationError: Invalid G-code command

**Solutions:**

1. Enable validation:

.. code-block:: python

   from promptplot.workflows import SimpleBatchWorkflow
   
   workflow = SimpleBatchWorkflow(
       plotter=plotter,
       validation_enabled=True
   )

2. Check prompt clarity:

.. code-block:: python

   # Bad prompt
   result = await workflow.execute("draw something")
   
   # Better prompt
   result = await workflow.execute("draw a 50mm square at coordinates (10, 10)")

3. Use reflection for errors:

.. code-block:: python

   workflow = SimpleBatchWorkflow(
       plotter=plotter,
       max_retries=3,
       reflection_enabled=True
   )

**Issue: G-code coordinates out of bounds**

.. code-block:: python

   ValidationError: Coordinates exceed plotter bounds

**Solutions:**

1. Set plotter bounds:

.. code-block:: python

   from promptplot.config import PlotterBounds
   
   bounds = PlotterBounds(
       x_min=0, x_max=200,
       y_min=0, y_max=200,
       z_min=0, z_max=50
   )
   
   plotter = SerialPlotter(bounds=bounds)

2. Scale down coordinates:

.. code-block:: python

   result = await workflow.execute("draw a 20mm square")  # Instead of 200mm

File Conversion Issues
~~~~~~~~~~~~~~~~~~~~~~

**Issue: SVG file not converting**

.. code-block:: python

   ConversionError: Could not parse SVG file

**Solutions:**

1. Validate SVG file:

.. code-block:: python

   from promptplot.converters import FileValidator
   
   validator = FileValidator()
   result = validator.validate_file("drawing.svg")
   
   if not result.is_valid:
       print("SVG errors:", result.errors)

2. Simplify SVG:

.. code-block:: python

   from promptplot.converters import SVGConverter, SVGSettings
   
   settings = SVGSettings(
       simplify_paths=True,
       ignore_text=True,
       flatten_groups=True
   )
   
   converter = SVGConverter(settings)

3. Check SVG features:

.. code-block:: python

   # Supported: paths, lines, rectangles, circles
   # Not supported: gradients, filters, animations

**Issue: DXF file conversion fails**

.. code-block:: python

   ConversionError: Unsupported DXF entity type

**Solutions:**

1. Check supported entities:

.. code-block:: python

   from promptplot.converters import DXFConverter
   
   converter = DXFConverter()
   supported = converter.get_supported_entities()
   print("Supported entities:", supported)

2. Filter entities:

.. code-block:: python

   from promptplot.converters import DXFSettings
   
   settings = DXFSettings(
       entity_types=["LINE", "POLYLINE", "CIRCLE"],
       ignore_unsupported=True
   )

Performance Issues
~~~~~~~~~~~~~~~~~~

**Issue: Slow G-code generation**

**Solutions:**

1. Use simpler prompts:

.. code-block:: python

   # Slow
   result = await workflow.execute("draw a detailed mandala with intricate patterns")
   
   # Faster
   result = await workflow.execute("draw a simple circle")

2. Reduce complexity:

.. code-block:: python

   workflow = SimpleBatchWorkflow(
       plotter=plotter,
       max_steps=50,  # Reduce from default 100
       complexity_limit="medium"
   )

3. Use appropriate workflow:

.. code-block:: python

   # For simple shapes
   from promptplot.workflows import SimpleBatchWorkflow
   
   # For complex shapes
   from promptplot.workflows import AdvancedSequentialWorkflow

**Issue: Large file conversion is slow**

**Solutions:**

1. Use streaming conversion:

.. code-block:: python

   from promptplot.converters import SVGConverter
   
   converter = SVGConverter()
   
   async for command_batch in converter.convert_stream("large_file.svg"):
       await plotter.send_commands(command_batch)

2. Enable caching:

.. code-block:: python

   from promptplot.converters import ConversionCache
   
   cache = ConversionCache(enabled=True)
   converter = SVGConverter(cache=cache)

Visualization Issues
~~~~~~~~~~~~~~~~~~~~

**Issue: Visualization not showing**

.. code-block:: python

   # No visualization appears

**Solutions:**

1. Enable visualization:

.. code-block:: python

   from promptplot.plotter import SimulatedPlotter
   
   plotter = SimulatedPlotter(visualize=True)

2. Check display backend:

.. code-block:: python

   import matplotlib
   matplotlib.use('TkAgg')  # or 'Qt5Agg'

3. Save instead of showing:

.. code-block:: python

   plotter = SimulatedPlotter(
       visualize=True,
       save_images=True,
       output_dir="results/visualizations"
   )

**Issue: Visualization is slow**

**Solutions:**

1. Reduce update frequency:

.. code-block:: python

   plotter = SimulatedPlotter(
       visualize=True,
       update_interval=0.5  # Update every 0.5 seconds
   )

2. Disable real-time updates:

.. code-block:: python

   plotter = SimulatedPlotter(
       visualize=True,
       real_time=False  # Only show final result
   )

Configuration Issues
~~~~~~~~~~~~~~~~~~~~

**Issue: Configuration not loading**

.. code-block:: python

   ConfigurationError: Could not load configuration file

**Solutions:**

1. Check file path:

.. code-block:: python

   import os
   from promptplot.config import load_config
   
   config_path = "config.yaml"
   if os.path.exists(config_path):
       config = load_config(config_path)
   else:
       print(f"Config file not found: {config_path}")

2. Validate configuration:

.. code-block:: python

   from promptplot.config import validate_config
   
   try:
       config = load_config("config.yaml")
       validate_config(config)
   except ValidationError as e:
       print(f"Configuration error: {e}")

3. Use default configuration:

.. code-block:: python

   from promptplot.config import Settings
   
   # Use defaults
   settings = Settings()

Debugging Tips
--------------

Enable Debug Logging
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   from promptplot.config import Settings
   
   # Enable debug logging
   logging.basicConfig(level=logging.DEBUG)
   
   settings = Settings(logging_level="DEBUG")

Check System Information
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.utils import system_info
   
   info = system_info.get_system_info()
   print(f"Python version: {info.python_version}")
   print(f"Platform: {info.platform}")
   print(f"Available ports: {info.serial_ports}")

Test Components Individually
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Test LLM provider
   from promptplot.llm.providers import AzureOpenAIProvider
   
   provider = AzureOpenAIProvider()
   response = await provider.acomplete("Hello")
   print(f"LLM response: {response}")
   
   # Test plotter connection
   from promptplot.plotter import SerialPlotter
   
   plotter = SerialPlotter(port="/dev/ttyUSB0")
   success = await plotter.connect()
   print(f"Plotter connected: {success}")

Use Simulated Components for Testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Use simulated plotter for testing
   from promptplot.plotter import SimulatedPlotter
   
   plotter = SimulatedPlotter(visualize=True)
   
   # Use mock LLM for testing
   from promptplot.llm.providers import MockLLMProvider
   
   provider = MockLLMProvider()

Getting Help
------------

Check Documentation
~~~~~~~~~~~~~~~~~~~

* Read the full documentation at [documentation URL]
* Check the API reference for detailed information
* Review examples in the `examples/` directory

Community Support
~~~~~~~~~~~~~~~~~

* GitHub Issues: Report bugs and request features
* Discussions: Ask questions and share experiences
* Wiki: Community-contributed guides and tips

Diagnostic Information
~~~~~~~~~~~~~~~~~~~~~~

When reporting issues, include:

.. code-block:: python

   from promptplot.utils import diagnostic_info
   
   info = diagnostic_info.collect()
   print(info.to_string())

This includes:
* PromptPlot version
* Python version and platform
* Installed dependencies
* Configuration summary
* Recent error logs

Error Recovery
--------------

Automatic Recovery
~~~~~~~~~~~~~~~~~~

PromptPlot includes automatic recovery for common issues:

.. code-block:: python

   from promptplot.workflows import AdvancedSequentialWorkflow
   
   workflow = AdvancedSequentialWorkflow(
       plotter=plotter,
       auto_recovery=True,      # Enable automatic recovery
       max_retries=3,           # Retry failed operations
       fallback_strategy=True   # Use fallback strategies
   )

Manual Recovery
~~~~~~~~~~~~~~~

For manual recovery:

.. code-block:: python

   try:
       result = await workflow.execute(prompt)
   except Exception as e:
       # Log error
       logger.error(f"Workflow failed: {e}")
       
       # Try recovery
       recovery_result = await workflow.recover_from_error(e)
       
       if recovery_result.success:
           result = recovery_result.result
       else:
           # Manual intervention required
           print("Manual recovery needed")

Safe Mode
~~~~~~~~~

Use safe mode for testing:

.. code-block:: python

   from promptplot.config import Settings
   
   settings = Settings(
       safe_mode=True,          # Enable safety checks
       dry_run=True,            # Don't execute commands
       validation_strict=True   # Strict validation
   )

This enables:
* Extra validation checks
* Dry-run mode (no actual plotting)
* Conservative settings
* Enhanced error reporting