.PHONY: help install test test-unit test-integration test-cov clean lint format

help:
	@echo "PDF Report Renderer - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install dependencies"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-cov         Run tests with coverage report"
	@echo "  lint             Run code linters"
	@echo "  format           Format code with black"
	@echo "  clean            Clean generated files"
	@echo "  run-example      Run example usage"

install:
	pip install -r requirements.txt

test:
	pytest -v

test-unit:
	pytest -v -m "not integration"

test-integration:
	pytest -v -m integration

test-cov:
	pytest --cov=render --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	@echo "Running linters..."
	-pylint render/
	-mypy render/

format:
	@echo "Formatting code..."
	black render/ tests/
	isort render/ tests/

clean:
	@echo "Cleaning generated files..."
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run-example:
	python -m render.main

.DEFAULT_GOAL := help
