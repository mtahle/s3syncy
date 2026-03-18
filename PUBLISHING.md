# Publishing Guide

This document describes how to publish s3sync to PyPI.

## Prerequisites

1. **PyPI Account**: Create one at https://pypi.org/

2. **Setup API Token**: 
   - Go to https://pypi.org/manage/account/
   - Create an API token with scope "Entire account"
   - Save it securely

3. **Build tools**:
   ```bash
   pip install build twine
   ```

## Step 1: Update Version

Edit both `setup.py` and `pyproject.toml`:

```python
# setup.py
version="0.2.0"

# pyproject.toml
version = "0.2.0"
```

## Step 2: Update Changelog

Add entry to `CHANGELOG.md`:

```markdown
## [0.2.0] - 2026-03-18

### Added
- New features...

### Fixed
- Bug fixes...
```

## Step 3: Tag Release in Git

```bash
git add setup.py pyproject.toml CHANGELOG.md
git commit -m "Bump version to 0.2.0"
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

## Step 4: Build Distribution

```bash
python -m build
```

This creates:
- `dist/s3sync-0.2.0-py3-none-any.whl` (wheel)
- `dist/s3sync-0.2.0.tar.gz` (source distribution)

## Step 5: Test Locally

```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate

# Install from local wheel
pip install dist/s3sync-0.2.0-py3-none-any.whl

# Test commands
s3sync --help
s3sync init
s3sync --version
```

## Step 6: Upload to PyPI

Using API token:

```bash
python -m twine upload dist/* --username __token__ --password pypi-xxx
```

Or configure `.pypirc` for convenience:

```ini
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...
```

Then simply:
```bash
twine upload dist/*
```

## Step 7: Verify on PyPI

1. Visit https://pypi.org/project/s3sync/
2. Verify package appears
3. Test installation:
   ```bash
   pip install s3sync
   s3sync --version
   ```

## Uploading to Test PyPI (Optional)

Before publishing to production, test on TestPyPI:

```bash
python -m twine upload --repository testpypi dist/*
```

Then test installation:
```bash
pip install --index-url https://test.pypi.org/simple/ s3sync
```

## Troubleshooting

### Upload fails with "403 Forbidden"

- Check PyPI token is valid
- Verify token username is `__token__`
- Token may be expired

### Package metadata invalid

```bash
twine check dist/*
```

Fix any issues and rebuild.

### Installation fails

```bash
pip install --upgrade pip setuptools wheel
python -m build
```

## Maintenance

### Yanking a Release

If a release has critical issues:

```bash
twine yank dist/s3sync-0.1.5-py3-none-any.whl
```

### Updating Existing Release

PyPI doesn't allow replacing files. Create a new patch version:

1. Fix the issue
2. Bump version (0.1.1 → 0.1.2)
3. Tag and build
4. Upload new version
5. Yank old version if needed

## Resources

- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Python Packaging Guide](https://packaging.python.org/)
