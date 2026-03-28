"""
Setup configuration for PromptPlot v2.0

Enhanced setup with comprehensive dependency management, performance optimizations,
and deployment preparation features.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install

# Read version from package
def get_version():
    """Get version from package __init__.py"""
    version_file = Path(__file__).parent / "promptplot" / "__init__.py"
    with open(version_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "2.0.0"

# Read long description
def get_long_description():
    """Get long description from README.md"""
    readme_file = Path(__file__).parent / "README.md"
    if readme_file.exists():
        with open(readme_file, "r", encoding="utf-8") as fh:
            return fh.read()
    return "LLM-controlled pen plotter system with computer vision integration"

# Read requirements from requirements.txt
def get_requirements():
    """Get requirements from requirements.txt"""
    req_file = Path(__file__).parent / "requirements.txt"
    if req_file.exists():
        with open(req_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []

# Platform-specific dependencies
def get_platform_dependencies():
    """Get platform-specific dependencies"""
    deps = []
    
    # Windows-specific dependencies
    if sys.platform.startswith("win"):
        deps.extend([
            "pywin32>=227",
            "wmi>=1.5.1",
        ])
    
    # macOS-specific dependencies
    elif sys.platform == "darwin":
        deps.extend([
            "pyobjc-framework-Cocoa>=8.0",
        ])
    
    # Linux-specific dependencies
    elif sys.platform.startswith("linux"):
        deps.extend([
            "python-udev>=0.22.0",
        ])
    
    return deps

# Performance optimization extensions (optional)
def get_extensions():
    """Get optional C extensions for performance"""
    extensions = []
    
    # Only build extensions if explicitly requested
    if os.environ.get("PROMPTPLOT_BUILD_EXTENSIONS", "0") == "1":
        try:
            import numpy
            extensions.append(
                Extension(
                    "promptplot.utils._math_helpers_c",
                    sources=["promptplot/utils/_math_helpers.c"],
                    include_dirs=[numpy.get_include()],
                    extra_compile_args=["-O3", "-ffast-math"] if sys.platform != "win32" else ["/O2"],
                )
            )
        except ImportError:
            pass  # NumPy not available, skip C extensions
    
    return extensions

class CustomInstall(install):
    """Custom install command with post-install optimizations"""
    
    def run(self):
        install.run(self)
        self.post_install()
    
    def post_install(self):
        """Post-installation optimizations"""
        try:
            # Compile Python files for faster loading
            import compileall
            import promptplot
            
            package_path = Path(promptplot.__file__).parent
            compileall.compile_dir(package_path, quiet=1, optimize=2)
            
            print("✓ Python bytecode compilation completed")
            
        except Exception as e:
            print(f"Warning: Post-install optimization failed: {e}")

# Core dependencies
CORE_REQUIREMENTS = [
    # Core framework
    "pydantic>=2.0.0,<3.0.0",
    "typing-extensions>=4.0.0",
    "dataclasses-json>=0.5.7",
    
    # LLM integration
    "llama-index-core>=0.10.0",
    "llama-index-llms-openai>=0.1.0",
    "llama-index-llms-ollama>=0.1.0",
    "openai>=1.0.0",
    
    # Async and networking
    "aiohttp>=3.8.0",
    "aiofiles>=0.8.0",
    "asyncio>=3.4.3",
    
    # Visualization and image processing
    "matplotlib>=3.5.0,<4.0.0",
    "pillow>=9.0.0,<11.0.0",
    "numpy>=1.21.0,<2.0.0",
    
    # Serial communication
    "pyserial>=3.5,<4.0",
    "pyserial-asyncio>=0.6",
    
    # File format support
    "svglib>=1.4.0",
    "ezdxf>=0.17.0",
    "reportlab>=3.6.0",
    
    # Configuration and CLI
    "pyyaml>=6.0",
    "click>=8.0.0",
    "colorama>=0.4.4",
    "rich>=12.0.0",
    
    # Utilities
    "python-dateutil>=2.8.0",
    "packaging>=21.0",
]

# Optional dependencies for different use cases
EXTRAS_REQUIRE = {
    # Development dependencies
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "pytest-mock>=3.10.0",
        "pytest-benchmark>=4.0.0",
        "black>=22.0.0",
        "isort>=5.10.0",
        "flake8>=4.0.0",
        "mypy>=1.0.0",
        "pre-commit>=2.20.0",
        "sphinx>=5.0.0",
        "sphinx-rtd-theme>=1.2.0",
    ],
    
    # Azure OpenAI support
    "azure": [
        "azure-identity>=1.12.0",
        "azure-keyvault-secrets>=4.6.0",
        "azure-storage-blob>=12.14.0",
    ],
    
    # Local LLM support
    "ollama": [
        "ollama>=0.1.0",
        "requests>=2.28.0",
    ],
    
    # Computer vision enhancements
    "vision": [
        "opencv-python>=4.5.0",
        "scikit-image>=0.19.0",
        "imageio>=2.22.0",
    ],
    
    # Performance optimizations
    "performance": [
        "numba>=0.56.0",
        "cython>=0.29.0",
        "psutil>=5.9.0",
        "memory-profiler>=0.60.0",
    ],
    
    # Hardware integration
    "hardware": [
        "RPi.GPIO>=0.7.1; platform_machine=='armv7l'",
        "gpiozero>=1.6.2; platform_machine=='armv7l'",
        "adafruit-circuitpython-motor>=3.4.0; platform_machine=='armv7l'",
    ],
    
    # Web interface (future)
    "web": [
        "fastapi>=0.95.0",
        "uvicorn>=0.20.0",
        "websockets>=10.4",
        "jinja2>=3.1.0",
    ],
    
    # All optional dependencies
    "all": [
        # Include all extras except platform-specific ones
    ],
}

# Populate "all" extra with all other extras
EXTRAS_REQUIRE["all"] = [
    dep for extra_name, deps in EXTRAS_REQUIRE.items() 
    if extra_name not in ["all", "hardware"] 
    for dep in deps
]

setup(
    name="promptplot",
    version=get_version(),
    author="PromptPlot Team",
    author_email="team@promptplot.dev",
    description="Advanced LLM-controlled pen plotter system with computer vision integration",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/promptplot/promptplot",
    project_urls={
        "Bug Reports": "https://github.com/promptplot/promptplot/issues",
        "Source": "https://github.com/promptplot/promptplot",
        "Documentation": "https://promptplot.readthedocs.io/",
    },
    packages=find_packages(exclude=["tests*", "boilerplates*"]),
    include_package_data=True,
    package_data={
        "promptplot": [
            "config/defaults/*.yaml",
            "config/profiles/*.yaml",
            "templates/*.txt",
            "assets/*",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Hardware :: Hardware Drivers",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Artistic Software",
    ],
    keywords="plotter, gcode, llm, ai, computer-vision, automation, cnc, drawing",
    python_requires=">=3.8",
    install_requires=CORE_REQUIREMENTS + get_platform_dependencies(),
    extras_require=EXTRAS_REQUIRE,
    ext_modules=get_extensions(),
    cmdclass={
        "install": CustomInstall,
    },
    entry_points={
        "console_scripts": [
            "promptplot=promptplot.cli:main",
            "promptplot-config=promptplot.config.cli:main",
            "promptplot-convert=promptplot.converters.cli:main",
        ],
    },
    zip_safe=False,  # Required for package data access
    
    # Performance and deployment options
    options={
        "build_ext": {
            "parallel": True,  # Enable parallel compilation
        },
        "bdist_wheel": {
            "universal": False,  # Platform-specific wheels
        },
    },
    
    # Metadata for package managers
    license="MIT",
    platforms=["any"],
    
    # Security and quality metadata
    download_url="https://github.com/promptplot/promptplot/archive/v2.0.0.tar.gz",
)