# Contributing to s3sync

Thank you for your interest in contributing to s3sync! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites
- Python 3.10 or higher
- pip and virtualenv

### Setup Steps

1. Clone the repository
```bash
git clone https://github.com/mtahle/s3-sync.git.git
cd syncy3
```

2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install in development mode
```bash
pip install -r requirements.txt
pip install -e .
```

## Code Style

- Follow PEP 8
- Use type hints where practical
- Keep functions focused and well-documented
- Add docstrings for public APIs

## Testing

Before submitting a pull request:

1. Test with `s3sync init` to generate a config
2. Configure with test S3 bucket credentials
3. Run through the main commands: `start`, `status`, `stop`, `pause`, `resume`
4. Verify daemon lifecycle works correctly
5. Test `.syncignore` pattern matching

## Submitting Changes

1. Create a feature branch (`git checkout -b feature/your-feature`)
2. Make your changes with clear commit messages
3. Update documentation if needed
4. Push to your fork and submit a pull request

## Reporting Issues

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Relevant error messages or logs
- s3sync version and configuration (with sensitive data removed)

## Pull Request Process

1. Update README.md with any new features or changes
2. Update CHANGELOG.md under `[Unreleased]` section
3. Ensure all tests pass
4. Request review from maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
