.PHONY: test test-unit test-integration test-coverage test-fast install clean lint format

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests
test:
	python -m pytest tests/ -v

# Run unit tests only
test-unit:
	python -m pytest tests/ -v -m "unit or not integration"

# Run integration tests only  
test-integration:
	python -m pytest tests/test_integration.py -v

# Run tests with coverage
test-coverage:
	python -m pytest tests/ -v --cov=libs --cov=cli --cov-report=html --cov-report=term-missing

# Run fast tests (skip slow ones)
test-fast:
	python -m pytest tests/ -v -m "not slow"

# Run specific test module
test-module:
	@echo "Usage: make test-module MODULE=module_name"
	@echo "Example: make test-module MODULE=epub_utils"
	python -m pytest tests/test_$(MODULE).py -v

# Lint code
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Format code
format:
	black . --line-length 127
	isort . --profile black

# Clean up generated files
clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Show test help
help:
	@echo "Available targets:"
	@echo "  install         - Install dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-coverage  - Run tests with coverage report"
	@echo "  test-fast      - Run tests excluding slow ones"
	@echo "  test-module    - Run tests for specific module (use MODULE=name)"
	@echo "  lint           - Run code linting"
	@echo "  format         - Format code with black and isort"
	@echo "  clean          - Clean up generated files"
	@echo "  help           - Show this help message"
