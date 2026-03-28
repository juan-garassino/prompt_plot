# Makefile for PromptPlot v3.0

PYTHON := python3
PACKAGE := promptplot
TESTS := tests

.PHONY: help install dev test lint format clean

help:
	@echo "PromptPlot v3.0"
	@echo ""
	@echo "  install    Install package"
	@echo "  dev        Install with dev dependencies"
	@echo "  test       Run tests"
	@echo "  lint       Run ruff linter"
	@echo "  format     Format code with black"
	@echo "  clean      Remove build artifacts"

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev,viz]"

test:
	$(PYTHON) -m pytest $(TESTS)/ -v

lint:
	$(PYTHON) -m ruff check $(PACKAGE)/

format:
	$(PYTHON) -m black $(PACKAGE)/ $(TESTS)/
	$(PYTHON) -m isort $(PACKAGE)/ $(TESTS)/

clean:
	rm -rf build/ dist/ .pytest_cache/ htmlcov/ .coverage coverage.xml test-results/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
