Getting Started
===============

Installation
------------

Basic Installation
~~~~~~~~~~~~~~~~~~

Install PromptPlot using pip:

.. code-block:: bash

   pip install promptplot

Development Installation
~~~~~~~~~~~~~~~~~~~~~~~~

For development, clone the repository and install in editable mode:

.. code-block:: bash

   git clone <repository-url>
   cd promptplot
   pip install -e .

Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~

Install additional dependencies for specific features:

.. code-block:: bash

   # For Azure OpenAI support
   pip install promptplot[azure]
   
   # For Ollama support
   pip install promptplot[ollama]
   
   # For development tools
   pip install promptplot[dev]

Basic Usage
-----------

Simple Drawing
~~~~~~~~~~~~~~

Create your first drawing with PromptPlot:

.. code-block:: python

   import asyncio
   from promptplot.workflows import SimpleBatchWorkflow
   from promptplot.plotter import SimulatedPlotter
   
   async def main():
       # Create a simulated plotter
       plotter = SimulatedPlotter(visualize=True)
       
       # Initialize workflow
       workflow = SimpleBatchWorkflow(plotter=plotter)
       
       # Generate and execute G-code
       result = await workflow.execute("Draw a circle with radius 50mm")
       
       print(f"Generated {len(result.commands)} G-code commands")
   
   # Run the example
   asyncio.run(main())

Using Real Hardware
~~~~~~~~~~~~~~~~~~~

Connect to a real pen plotter:

.. code-block:: python

   from promptplot.plotter import SerialPlotter
   
   # Connect to real plotter via serial
   plotter = SerialPlotter(port="/dev/ttyUSB0", baud_rate=115200)
   
   # Use with any workflow
   workflow = SimpleBatchWorkflow(plotter=plotter)

Configuration
-------------

Basic Configuration
~~~~~~~~~~~~~~~~~~~

Configure PromptPlot using environment variables or configuration files:

.. code-block:: python

   from promptplot.config import Settings
   
   # Load configuration
   settings = Settings()
   
   # Override specific settings
   settings.llm_provider = "azure_openai"
   settings.plotter_port = "/dev/ttyUSB0"

Configuration Profiles
~~~~~~~~~~~~~~~~~~~~~~

Use predefined configuration profiles:

.. code-block:: python

   from promptplot.config import load_profile
   
   # Load a specific profile
   config = load_profile("production")
   
   # Available profiles: development, testing, production

Next Steps
----------

* Explore the :doc:`workflows` documentation for different drawing approaches
* Learn about :doc:`configuration` options for your setup
* Check out :doc:`examples` for more complex use cases
* Read the :doc:`api_reference` for detailed API documentation