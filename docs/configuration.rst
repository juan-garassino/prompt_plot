Configuration
=============

PromptPlot provides flexible configuration options to customize behavior for different use cases and hardware setups.

Configuration Methods
---------------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Set configuration through environment variables:

.. code-block:: bash

   export PROMPTPLOT_LLM_PROVIDER=azure_openai
   export PROMPTPLOT_PLOTTER_PORT=/dev/ttyUSB0
   export PROMPTPLOT_PLOTTER_BAUD_RATE=115200

Configuration Files
~~~~~~~~~~~~~~~~~~~

Create configuration files in YAML or JSON format:

.. code-block:: yaml

   # config.yaml
   llm:
     provider: azure_openai
     model: gpt-4
     timeout: 30
   
   plotter:
     type: serial
     port: /dev/ttyUSB0
     baud_rate: 115200
   
   visualization:
     enabled: true
     real_time: true

.. code-block:: python

   from promptplot.config import load_config
   
   config = load_config("config.yaml")

Programmatic Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure directly in code:

.. code-block:: python

   from promptplot.config import Settings
   
   settings = Settings(
       llm_provider="azure_openai",
       plotter_port="/dev/ttyUSB0",
       visualization_enabled=True
   )

Configuration Profiles
----------------------

PromptPlot includes predefined configuration profiles for common scenarios.

Development Profile
~~~~~~~~~~~~~~~~~~~

Optimized for development and testing:

.. code-block:: python

   from promptplot.config import load_profile
   
   config = load_profile("development")

Features:
* Simulated plotter by default
* Enhanced logging
* Visualization enabled
* Shorter timeouts for faster iteration

Testing Profile
~~~~~~~~~~~~~~~

Configured for automated testing:

.. code-block:: python

   config = load_profile("testing")

Features:
* Mock LLM responses
* Simulated plotter
* Minimal logging
* Fast execution

Production Profile
~~~~~~~~~~~~~~~~~~

Optimized for production use:

.. code-block:: python

   config = load_profile("production")

Features:
* Real hardware defaults
* Comprehensive logging
* Error recovery enabled
* Performance monitoring

Configuration Options
---------------------

LLM Configuration
~~~~~~~~~~~~~~~~~

.. code-block:: python

   llm_config = {
       "provider": "azure_openai",  # azure_openai, ollama
       "model": "gpt-4",
       "api_key": "your-api-key",
       "endpoint": "https://your-endpoint.openai.azure.com/",
       "timeout": 30,
       "max_retries": 3,
       "temperature": 0.1
   }

Available Providers:

* **azure_openai**: Azure OpenAI Service
* **ollama**: Local Ollama installation
* **openai**: OpenAI API (coming soon)

Plotter Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   plotter_config = {
       "type": "serial",  # serial, simulated
       "port": "/dev/ttyUSB0",
       "baud_rate": 115200,
       "timeout": 5,
       "auto_reconnect": True,
       "visualization": True
   }

Serial Plotter Options:

* **port**: Serial port path
* **baud_rate**: Communication speed (115200, 9600, etc.)
* **timeout**: Command timeout in seconds
* **auto_reconnect**: Automatic reconnection on failure

Simulated Plotter Options:

* **visualization**: Enable real-time visualization
* **canvas_size**: Drawing area size (width, height)
* **pen_color**: Drawing color
* **background_color**: Canvas background color

Workflow Configuration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   workflow_config = {
       "max_steps": 100,
       "max_retries": 3,
       "validation_enabled": True,
       "reflection_enabled": True,
       "progress_monitoring": True
   }

Strategy Configuration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   strategy_config = {
       "auto_select": True,
       "orthogonal_threshold": 0.8,
       "curve_resolution": 0.1,
       "optimization_level": "high"
   }

Vision Configuration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   vision_config = {
       "enabled": False,
       "camera_device": 0,
       "capture_interval": 1.0,
       "analysis_threshold": 0.1,
       "feedback_enabled": True
   }

Visualization Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   visualization_config = {
       "enabled": True,
       "real_time": True,
       "save_images": True,
       "output_directory": "results/visualizations",
       "image_format": "png",
       "dpi": 300
   }

Runtime Configuration Updates
-----------------------------

Update configuration at runtime for non-critical settings:

.. code-block:: python

   from promptplot.config import RuntimeConfig
   
   runtime = RuntimeConfig()
   
   # Update visualization settings
   runtime.update_visualization(enabled=True, real_time=False)
   
   # Update strategy settings
   runtime.update_strategy(optimization_level="medium")
   
   # Get current configuration
   current_config = runtime.get_current_config()

Configuration Validation
-------------------------

PromptPlot validates configuration and provides helpful error messages:

.. code-block:: python

   from promptplot.config import validate_config
   
   try:
       config = Settings(plotter_port="invalid-port")
   except ValidationError as e:
       print(f"Configuration error: {e}")

Common validation checks:

* Serial port accessibility
* LLM API credentials
* File path permissions
* Hardware compatibility
* Resource availability

Hardware-Specific Configuration
-------------------------------

AxiDraw Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   plotter:
     type: serial
     port: /dev/ttyUSB0
     baud_rate: 115200
     pen_up_position: 50
     pen_down_position: 30
     travel_speed: 3000
     drawing_speed: 1000

Grbl-based Plotters
~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   plotter:
     type: serial
     port: /dev/ttyUSB0
     baud_rate: 115200
     coordinate_system: absolute
     units: mm
     homing_enabled: true

Custom Hardware
~~~~~~~~~~~~~~~

.. code-block:: python

   from promptplot.plotter import CustomPlotter
   
   class MyPlotter(CustomPlotter):
       def __init__(self, **kwargs):
           super().__init__(**kwargs)
           # Custom initialization
   
   config = Settings(plotter_class=MyPlotter)

Configuration Examples
----------------------

Complete Development Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # development.yaml
   llm:
     provider: ollama
     model: llama3.2:3b
     timeout: 60
   
   plotter:
     type: simulated
     visualization: true
     canvas_size: [200, 200]
   
   workflow:
     max_steps: 50
     validation_enabled: true
     progress_monitoring: true
   
   visualization:
     enabled: true
     real_time: true
     save_images: true

Production Setup with Azure OpenAI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # production.yaml
   llm:
     provider: azure_openai
     model: gpt-4
     api_key: ${AZURE_OPENAI_API_KEY}
     endpoint: ${AZURE_OPENAI_ENDPOINT}
     timeout: 30
   
   plotter:
     type: serial
     port: /dev/ttyUSB0
     baud_rate: 115200
     auto_reconnect: true
   
   workflow:
     max_steps: 200
     max_retries: 5
     validation_enabled: true
   
   logging:
     level: INFO
     file: promptplot.log

Testing Setup
~~~~~~~~~~~~~

.. code-block:: python

   # test_config.py
   from promptplot.config import Settings
   
   test_config = Settings(
       llm_provider="mock",
       plotter_type="simulated",
       visualization_enabled=False,
       logging_level="ERROR"
   )

Environment-Specific Configuration
----------------------------------

Use different configurations for different environments:

.. code-block:: bash

   # .env.development
   PROMPTPLOT_PROFILE=development
   PROMPTPLOT_LLM_PROVIDER=ollama
   PROMPTPLOT_PLOTTER_TYPE=simulated

.. code-block:: bash

   # .env.production
   PROMPTPLOT_PROFILE=production
   PROMPTPLOT_LLM_PROVIDER=azure_openai
   PROMPTPLOT_PLOTTER_TYPE=serial
   PROMPTPLOT_PLOTTER_PORT=/dev/ttyUSB0

Configuration Best Practices
-----------------------------

1. **Use Profiles**: Start with predefined profiles and customize as needed
2. **Environment Variables**: Use environment variables for sensitive data
3. **Validation**: Always validate configuration before use
4. **Documentation**: Document custom configuration options
5. **Testing**: Test configuration changes in development first
6. **Backup**: Keep backup configurations for rollback
7. **Security**: Never commit API keys or sensitive data to version control