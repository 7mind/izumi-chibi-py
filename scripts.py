#!/usr/bin/env python3
"""
Development scripts for distage-py project.

These scripts integrate with uv to run various checks and tests.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n🔄 {description}...")
    print(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False


def run_tests() -> int:
    """Run the test suite."""
    print("🧪 Running test suite")
    success = run_command(["uv", "run", "pytest", "-v"], "Tests")
    return 0 if success else 1


def run_lint() -> int:
    """Run linting checks."""
    print("🔍 Running linting checks")

    checks = [
        (["uv", "run", "ruff", "check", "."], "Ruff linting"),
        (["uv", "run", "ruff", "format", "--check", "."], "Ruff formatting"),
    ]

    all_passed = True
    for cmd, desc in checks:
        if not run_command(cmd, desc):
            all_passed = False

    if not all_passed:
        print("\n💡 To auto-fix formatting issues, run: uv run ruff format .")
        print("💡 To auto-fix some linting issues, run: uv run ruff check --fix .")

    return 0 if all_passed else 1


def run_typecheck() -> int:
    """Run type checking with both mypy and pyright."""
    print("🔬 Running type checking")

    checks = [
        (["uv", "run", "mypy", "src/izumi/distage/"], "MyPy type checking"),
        (["uv", "run", "pyright", "src/izumi/distage/"], "Pyright type checking"),
    ]

    all_passed = True
    for cmd, desc in checks:
        if not run_command(cmd, desc):
            all_passed = False

    return 0 if all_passed else 1


def run_demos() -> int:
    """Run all demo scripts to ensure they work correctly."""
    print("🎭 Running demo scripts")

    demo_dir = Path("demo")
    if not demo_dir.exists():
        print("❌ Demo directory not found")
        return 1

    # Find all Python files in demo directory
    demo_files = list(demo_dir.glob("*.py"))

    if not demo_files:
        print("⚠️  No demo files found in demo directory")
        return 0

    all_passed = True
    for demo_file in sorted(demo_files):
        # Skip files that are not meant to be executed directly
        if demo_file.name.startswith("_"):
            continue

        cmd = ["uv", "run", "python", str(demo_file)]
        description = f"Demo: {demo_file.name}"

        if not run_command(cmd, description):
            all_passed = False

    return 0 if all_passed else 1


def run_readme_validation() -> int:
    """Validate that code examples in README.md are working."""
    print("📖 Validating README code examples")

    readme_path = Path("README.md")
    if not readme_path.exists():
        print("❌ README.md not found")
        return 1

    # Generate test file from README using phmdoctest
    test_file_path = Path("test_readme.py")

    # Clean up any existing test file
    if test_file_path.exists():
        test_file_path.unlink()

    # Generate test file
    gen_cmd = ["uv", "run", "phmdoctest", str(readme_path), "--outfile", str(test_file_path)]
    if not run_command(gen_cmd, "Generating README tests"):
        return 1

    # Run the generated tests
    test_cmd = ["uv", "run", "pytest", str(test_file_path), "-v"]
    success = run_command(test_cmd, "README code examples")

    # Clean up test file
    if test_file_path.exists():
        test_file_path.unlink()

    return 0 if success else 1


def check_all() -> int:
    """Run all checks: tests, linting, type checking, demos, and README validation."""
    print("🚀 Running all checks for distage-py")
    print("=" * 50)

    checks = [
        ("Tests", run_tests),
        ("Linting", run_lint),
        ("Type Checking", run_typecheck),
        ("Demos", run_demos),
        ("README", run_readme_validation),
    ]

    results = {}
    for name, func in checks:
        print(f"\n{'=' * 20} {name} {'=' * 20}")
        results[name] = func() == 0

    # Summary
    print(f"\n{'=' * 20} SUMMARY {'=' * 20}")
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:<15} {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All checks passed!")
        return 0
    else:
        print("\n💥 Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    # Allow running directly for development
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test":
            sys.exit(run_tests())
        elif command == "lint":
            sys.exit(run_lint())
        elif command == "typecheck":
            sys.exit(run_typecheck())
        elif command == "demos":
            sys.exit(run_demos())
        elif command == "readme":
            sys.exit(run_readme_validation())
        elif command == "check":
            sys.exit(check_all())
        else:
            print(f"Unknown command: {command}")
            print("Available commands: test, lint, typecheck, demos, readme, check")
            sys.exit(1)
    else:
        print("Available commands: test, lint, typecheck, demos, readme, check")
        print("Usage: python scripts.py <command>")
