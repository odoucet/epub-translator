#!/usr/bin/env python3
"""
Test runner script for epub-translator project.
This script provides convenient commands for running different types of tests.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ {description} failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False
    else:
        print(f"✅ {description} passed!")
        if result.stdout.strip():
            print("Output:", result.stdout.strip())
        return True


def main():
    parser = argparse.ArgumentParser(description="Run tests for epub-translator")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage report')
    parser.add_argument('--fast', action='store_true', help='Skip slow tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--module', help='Run tests for specific module')
    
    args = parser.parse_args()
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    if args.fast:
        pytest_cmd.extend(["-m", "not slow"])
    
    if args.coverage:
        pytest_cmd.extend(["--cov=libs", "--cov=cli", "--cov-report=term-missing"])
    
    # Test selection
    if args.unit:
        pytest_cmd.extend(["-m", "unit"])
    elif args.integration:
        pytest_cmd.extend(["-m", "integration"])
    elif args.module:
        pytest_cmd.append(f"tests/test_{args.module}.py")
    else:
        # Run all tests
        pytest_cmd.append("tests/")
    
    success = run_command(pytest_cmd, "pytest tests")
    
    if not success:
        sys.exit(1)
    
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    main()
