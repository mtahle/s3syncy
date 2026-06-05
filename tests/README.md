# Test Suite

This directory contains the test suite for s3syncy.

## Structure

```
tests/
├── unit/                # Unit tests for individual components
│   ├── test_config.py   # Configuration loading and validation
│   ├── test_integrity.py # File hashing and verification
│   ├── test_throttle.py # Bandwidth throttling
│   └── ...
├── integration/         # Integration tests for workflows
│   └── ...
└── fixtures/            # Shared test fixtures and utilities
    ├── sample_configs.py # Sample configuration files
    └── ...
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run with coverage:
```bash
pytest --cov=s3syncy --cov-report=html
```

### Run only unit tests:
```bash
pytest tests/unit -m unit
```

### Run only integration tests:
```bash
pytest tests/integration -m integration
```

### Run a specific test file:
```bash
pytest tests/unit/test_config.py
```

### Run a specific test:
```bash
pytest tests/unit/test_config.py::TestSyncConfig::test_config_properties
```

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast, no external dependencies)
- `@pytest.mark.integration` - Integration tests (may use mocked S3)
- `@pytest.mark.slow` - Tests that take longer to run

## Writing Tests

### Unit Tests
Unit tests should:
- Test a single component in isolation
- Use mocks for external dependencies
- Be fast (< 1 second each)
- Not require network access or real S3

### Integration Tests
Integration tests should:
- Test multiple components working together
- Use moto for S3 mocking when needed
- Test realistic workflows
- Can take longer to run

### Example Test Structure

```python
import pytest
from s3syncy.module import MyClass

class TestMyClass:
    """Test MyClass functionality."""

    @pytest.fixture
    def sample_instance(self):
        """Create a sample instance for testing."""
        return MyClass(param="value")

    def test_basic_functionality(self, sample_instance):
        """Test basic functionality."""
        result = sample_instance.method()
        assert result == expected_value

    def test_error_handling(self, sample_instance):
        """Test error handling."""
        with pytest.raises(ValueError):
            sample_instance.method(invalid_param)
```

## Test Coverage Goals

- **Overall coverage**: > 80%
- **Critical modules** (engine, daemon, index): > 90%
- **Utility modules** (config, patterns, integrity): > 85%

## CI/CD

Tests are automatically run on:
- Every pull request
- Every commit to main branch
- Nightly builds

See `.github/workflows/tests.yml` for details.
