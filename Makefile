# Makefile for PromptPlot v2.0 - Enhanced Development Workflow
# Supports both traditional pip and modern uv package management

# Configuration
PYTHON := python3
UV := uv
PIP := pip
PROJECT_NAME := promptplot
VERSION := $(shell $(PYTHON) -c "import promptplot; print(promptplot.__version__)" 2>/dev/null || echo "2.0.0")
PACKAGE_DIR := promptplot
TEST_DIR := tests
DOCS_DIR := docs
BUILD_DIR := build
DIST_DIR := dist

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
PURPLE := \033[0;35m
CYAN := \033[0;36m
WHITE := \033[0;37m
RESET := \033[0m

# Check if uv is available
UV_AVAILABLE := $(shell command -v uv 2> /dev/null)

.PHONY: help install install-dev install-uv test test-unit test-integration test-coverage test-benchmark clean lint format build publish docs docker

# Default target
help:
	@echo "$(CYAN)PromptPlot v$(VERSION) Development Commands$(RESET)"
	@echo "$(CYAN)===========================================$(RESET)"
	@echo ""
	@echo "$(GREEN)Package Management:$(RESET)"
	@echo "  install           Install package (pip or uv)"
	@echo "  install-dev       Install with development dependencies"
	@echo "  install-uv        Install using uv (recommended)"
	@echo "  install-pip       Install using pip (traditional)"
	@echo "  sync              Sync dependencies with lock file"
	@echo "  lock              Generate/update lock file"
	@echo "  upgrade           Upgrade all dependencies"
	@echo ""
	@echo "$(GREEN)Testing:$(RESET)"
	@echo "  test              Run all tests"
	@echo "  test-unit         Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-coverage     Run tests with coverage report"
	@echo "  test-benchmark    Run performance benchmarks"
	@echo "  test-fast         Run tests in parallel"
	@echo "  test-watch        Watch files and run tests on changes"
	@echo "  test-report       Generate comprehensive test report"
	@echo ""
	@echo "$(GREEN)Code Quality:$(RESET)"
	@echo "  lint              Run all linting tools"
	@echo "  lint-check        Check code quality without fixing"
	@echo "  format            Format code with black and isort"
	@echo "  format-check      Check code formatting"
	@echo "  type-check        Run type checking with mypy"
	@echo "  security-check    Run security analysis"
	@echo "  pre-commit        Run pre-commit hooks"
	@echo ""
	@echo "$(GREEN)Build & Release:$(RESET)"
	@echo "  build             Build package distributions"
	@echo "  build-wheel       Build wheel distribution only"
	@echo "  build-sdist       Build source distribution only"
	@echo "  publish           Publish to PyPI"
	@echo "  publish-test      Publish to TestPyPI"
	@echo "  version-bump      Bump version (patch/minor/major)"
	@echo ""
	@echo "$(GREEN)Documentation:$(RESET)"
	@echo "  docs              Build documentation"
	@echo "  docs-serve        Serve documentation locally"
	@echo "  docs-clean        Clean documentation build"
	@echo "  docs-deploy       Deploy documentation"
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@echo "  docker-build      Build Docker image"
	@echo "  docker-run        Run Docker container"
	@echo "  docker-push       Push Docker image"
	@echo "  docker-compose    Run with docker-compose"
	@echo ""
	@echo "$(GREEN)Examples & Demos:$(RESET)"
	@echo "  example-quick     Run quick start demo (mock LLM)"
	@echo "  example-llm       Run LLM demo with auto-detection"
	@echo "  example-streaming Run streaming demo"
	@echo "  example-cli       Test CLI commands"
	@echo "  example-all       Run all examples"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  dev-setup         Complete development environment setup"
	@echo "  dev-reset         Reset development environment"
	@echo "  clean             Clean up generated files"
	@echo "  clean-all         Deep clean (including caches)"
	@echo "  check-deps        Check for dependency issues"
	@echo "  profile           Profile application performance"
	@echo ""
	@echo "$(GREEN)Examples:$(RESET)"
	@echo "  make test-unit ARGS='-v -k test_gcode'"
	@echo "  make test-coverage"
	@echo "  make build"
	@echo "  make docker-build TAG=latest"

# Package Management
install:
ifdef UV_AVAILABLE
	@echo "$(GREEN)Installing with uv...$(RESET)"
	$(UV) pip install -e .
else
	@echo "$(GREEN)Installing with pip...$(RESET)"
	$(PIP) install -e .
endif

install-dev:
ifdef UV_AVAILABLE
	@echo "$(GREEN)Installing development dependencies with uv...$(RESET)"
	$(UV) pip install -e .[dev,all]
else
	@echo "$(GREEN)Installing development dependencies with pip...$(RESET)"
	$(PIP) install -e .[dev,all]
endif

install-uv:
	@echo "$(GREEN)Installing with uv (forced)...$(RESET)"
	$(UV) pip install -e .[all]

install-pip:
	@echo "$(GREEN)Installing with pip (forced)...$(RESET)"
	$(PIP) install -e .[all]

sync:
ifdef UV_AVAILABLE
	@echo "$(GREEN)Syncing dependencies with uv...$(RESET)"
	$(UV) pip sync requirements.lock
else
	@echo "$(YELLOW)uv not available, using pip install$(RESET)"
	$(PIP) install -r requirements.txt
endif

lock:
ifdef UV_AVAILABLE
	@echo "$(GREEN)Generating lock file with uv...$(RESET)"
	$(UV) pip compile pyproject.toml -o requirements.lock
else
	@echo "$(YELLOW)uv not available, using pip-tools$(RESET)"
	pip-compile pyproject.toml
endif

upgrade:
ifdef UV_AVAILABLE
	@echo "$(GREEN)Upgrading dependencies with uv...$(RESET)"
	$(UV) pip install --upgrade -e .[all]
else
	@echo "$(GREEN)Upgrading dependencies with pip...$(RESET)"
	$(PIP) install --upgrade -e .[all]
endif

# Testing
test:
	@echo "$(GREEN)Running all tests...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/ -v $(ARGS)

test-unit:
	@echo "$(GREEN)Running unit tests...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/unit/ -v $(ARGS)

test-integration:
	@echo "$(GREEN)Running integration tests...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/integration/ -v $(ARGS)

test-coverage:
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/ --cov=$(PACKAGE_DIR) --cov-report=html --cov-report=term --cov-report=xml -v

test-benchmark:
	@echo "$(GREEN)Running performance benchmarks...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/ --benchmark-only -v

test-fast:
	@echo "$(GREEN)Running tests in parallel...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/ -n auto -v

test-watch:
	@echo "$(GREEN)Watching files for test changes...$(RESET)"
	ptw $(TEST_DIR)/ $(PACKAGE_DIR)/

test-report:
	@echo "$(GREEN)Generating comprehensive test report...$(RESET)"
	$(PYTHON) -m pytest $(TEST_DIR)/ --html=test-results/report.html --self-contained-html --cov=$(PACKAGE_DIR) --cov-report=html

# Code Quality
lint:
	@echo "$(GREEN)Running all linting tools...$(RESET)"
	$(PYTHON) -m flake8 $(PACKAGE_DIR)/ $(TEST_DIR)/
	$(PYTHON) -m pylint $(PACKAGE_DIR)/ $(TEST_DIR)/ || true

lint-check:
	@echo "$(GREEN)Checking code quality...$(RESET)"
	$(PYTHON) -m flake8 $(PACKAGE_DIR)/ $(TEST_DIR)/ --count --select=E9,F63,F7,F82 --show-source --statistics
	$(PYTHON) -m pylint $(PACKAGE_DIR)/ --errors-only

format:
	@echo "$(GREEN)Formatting code...$(RESET)"
	$(PYTHON) -m black $(PACKAGE_DIR)/ $(TEST_DIR)/
	$(PYTHON) -m isort $(PACKAGE_DIR)/ $(TEST_DIR)/

format-check:
	@echo "$(GREEN)Checking code formatting...$(RESET)"
	$(PYTHON) -m black --check $(PACKAGE_DIR)/ $(TEST_DIR)/
	$(PYTHON) -m isort --check-only $(PACKAGE_DIR)/ $(TEST_DIR)/

type-check:
	@echo "$(GREEN)Running type checking...$(RESET)"
	$(PYTHON) -m mypy $(PACKAGE_DIR)/ --ignore-missing-imports

security-check:
	@echo "$(GREEN)Running security analysis...$(RESET)"
	$(PYTHON) -m bandit -r $(PACKAGE_DIR)/ -f json -o security-report.json || true
	$(PYTHON) -m safety check

pre-commit:
	@echo "$(GREEN)Running pre-commit hooks...$(RESET)"
	pre-commit run --all-files

# Build & Release
build: clean
	@echo "$(GREEN)Building package distributions...$(RESET)"
	$(PYTHON) -m build

build-wheel:
	@echo "$(GREEN)Building wheel distribution...$(RESET)"
	$(PYTHON) -m build --wheel

build-sdist:
	@echo "$(GREEN)Building source distribution...$(RESET)"
	$(PYTHON) -m build --sdist

publish: build
	@echo "$(GREEN)Publishing to PyPI...$(RESET)"
	$(PYTHON) -m twine upload $(DIST_DIR)/*

publish-test: build
	@echo "$(GREEN)Publishing to TestPyPI...$(RESET)"
	$(PYTHON) -m twine upload --repository testpypi $(DIST_DIR)/*

version-bump:
	@echo "$(GREEN)Current version: $(VERSION)$(RESET)"
	@echo "Use: bump2version patch|minor|major"

# Documentation
docs:
	@echo "$(GREEN)Building documentation...$(RESET)"
	cd $(DOCS_DIR) && make html

docs-serve:
	@echo "$(GREEN)Serving documentation locally...$(RESET)"
	cd $(DOCS_DIR)/_build/html && $(PYTHON) -m http.server 8000

docs-clean:
	@echo "$(GREEN)Cleaning documentation build...$(RESET)"
	cd $(DOCS_DIR) && make clean

docs-deploy:
	@echo "$(GREEN)Deploying documentation...$(RESET)"
	cd $(DOCS_DIR) && make html && rsync -av _build/html/ docs-server:/var/www/promptplot-docs/

# Docker
docker-build:
	@echo "$(GREEN)Building Docker image...$(RESET)"
	docker build -t $(PROJECT_NAME):$(VERSION) .
	docker tag $(PROJECT_NAME):$(VERSION) $(PROJECT_NAME):latest

docker-run:
	@echo "$(GREEN)Running Docker container...$(RESET)"
	docker run -it --rm -p 8000:8000 $(PROJECT_NAME):latest

docker-push:
	@echo "$(GREEN)Pushing Docker image...$(RESET)"
	docker push $(PROJECT_NAME):$(VERSION)
	docker push $(PROJECT_NAME):latest

docker-compose:
	@echo "$(GREEN)Running with docker-compose...$(RESET)"
	docker-compose up -d

# Examples and Demos
example-quick:
	@echo "$(GREEN)Running quick start example...$(RESET)"
	$(PYTHON) examples/quick_start.py

example-simple:
	@echo "$(GREEN)Running simple demo...$(RESET)"
	$(PYTHON) examples/simple_demo.py

example-llm:
	@echo "$(GREEN)Running LLM demo with auto-detection...$(RESET)"
	$(PYTHON) examples/llm_demo.py --provider auto

example-llm-ollama:
	@echo "$(GREEN)Running LLM demo with Ollama...$(RESET)"
	$(PYTHON) examples/llm_demo.py --provider ollama

example-llm-azure:
	@echo "$(GREEN)Running LLM demo with Azure OpenAI...$(RESET)"
	$(PYTHON) examples/llm_demo.py --provider azure

example-streaming:
	@echo "$(GREEN)Running streaming demo...$(RESET)"
	$(PYTHON) examples/streaming_demo.py --provider mock

example-streaming-ollama:
	@echo "$(GREEN)Running streaming demo with Ollama...$(RESET)"
	$(PYTHON) examples/streaming_demo.py --provider ollama

example-streaming-interactive:
	@echo "$(GREEN)Running interactive streaming demo...$(RESET)"
	$(PYTHON) examples/streaming_demo.py --provider mock --interactive

example-cli:
	@echo "$(GREEN)Testing CLI commands...$(RESET)"
	$(PYTHON) examples/cli_demo.py

example-basic:
	@echo "$(GREEN)Running basic examples...$(RESET)"
	$(PYTHON) examples/basic/simple_drawing.py

example-all: example-simple example-quick example-cli
	@echo "$(GREEN)All basic examples completed!$(RESET)"
	@echo ""
	@echo "$(CYAN)Available Examples:$(RESET)"
	@echo "• make example-simple     - Core components demo (no LLM needed)"
	@echo "• make example-quick      - Quick start with mock LLM"
	@echo "• make example-cli        - CLI interface demo"
	@echo "• make example-llm        - Real LLM demo (requires Ollama/Azure)"
	@echo "• make example-streaming  - Streaming workflow demo"

# Development
dev-setup: install-dev
	@echo "$(GREEN)Setting up development environment...$(RESET)"
	pre-commit install || echo "pre-commit not available"
	@echo "$(GREEN)Development environment ready!$(RESET)"

dev-reset: clean-all
	@echo "$(GREEN)Resetting development environment...$(RESET)"
	rm -rf venv/ .venv/
ifdef UV_AVAILABLE
	$(UV) venv
	$(UV) pip install -e .[dev,all]
else
	$(PYTHON) -m venv venv
	./venv/bin/pip install -e .[dev,all]
endif

clean:
	@echo "$(GREEN)Cleaning up generated files...$(RESET)"
	rm -rf $(BUILD_DIR)/
	rm -rf $(DIST_DIR)/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf test-results/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-all: clean
	@echo "$(GREEN)Deep cleaning (including caches)...$(RESET)"
	rm -rf .mypy_cache/
	rm -rf .tox/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf node_modules/
	rm -rf .cache/

check-deps:
	@echo "$(GREEN)Checking for dependency issues...$(RESET)"
	$(PYTHON) -m pip check
ifdef UV_AVAILABLE
	$(UV) pip list --outdated
endif

profile:
	@echo "$(GREEN)Profiling application performance...$(RESET)"
	$(PYTHON) -m cProfile -o profile.stats examples/quick_start.py
	$(PYTHON) -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Utility targets
check-uv:
ifdef UV_AVAILABLE
	@echo "$(GREEN)✓ uv is available$(RESET)"
else
	@echo "$(YELLOW)⚠ uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh$(RESET)"
endif

check-system:
	@echo "$(CYAN)System Information:$(RESET)"
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Pip: $(shell $(PIP) --version)"
ifdef UV_AVAILABLE
	@echo "UV: $(shell $(UV) --version)"
endif
	@echo "Platform: $(shell uname -s)"
	@echo "Architecture: $(shell uname -m)"

info:
	@echo "$(CYAN)Project Information:$(RESET)"
	@echo "Name: $(PROJECT_NAME)"
	@echo "Version: $(VERSION)"
	@echo "Package Directory: $(PACKAGE_DIR)"
	@echo "Test Directory: $(TEST_DIR)"
	@echo "Documentation: $(DOCS_DIR)"

# Default target when no arguments provided
.DEFAULT_GOAL := help