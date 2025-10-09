# Release Process

This project uses **single-source versioning** - you only need to update the version in one place.

## Version Management

The version is defined **only** in `src/izumi/__init__.py`:

```python
__version__ = "0.1.1"
```

The `pyproject.toml` dynamically reads this version using hatchling's version plugin:
```toml
[project]
dynamic = ["version"]

[tool.hatch.version]
path = "src/izumi/__init__.py"
```

## Release Steps

### 1. Update Version

Edit `src/izumi/__init__.py` and change the version:

```python
__version__ = "0.1.2"  # or whatever the new version is
```

### 2. Commit and Tag

```bash
git add src/izumi/__init__.py
git commit -m "Bump version to 0.1.2"
git tag v0.1.2
git push origin main --tags
```

### 3. Build and Publish

```bash
# Clean previous builds
rm -rf dist/

# Build package (version is read automatically from __init__.py)
uv build

# Check the build
ls -lh dist/
twine check dist/*

# Upload to PyPI (test first)
twine upload --repository testpypi dist/*

# Upload to production PyPI
twine upload dist/*
```

## Notes

- **No need to edit `pyproject.toml`** for version changes
- Git tag should match the version (e.g., `v0.1.2` for version `0.1.2`)
- The build system automatically extracts `__version__` from `__init__.py`
- This ensures version consistency across package metadata and Python imports
