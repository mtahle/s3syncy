"""Unit tests for config module."""

import pytest
import yaml

from s3syncy.config import SyncConfig, load_config, _deep_merge, _expand_path


class TestDeepMerge:
    """Test configuration merging logic."""

    def test_merge_simple_dict(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}
        # Ensure original dicts are unchanged
        assert base == {"a": 1, "b": 2}

    def test_merge_nested_dict(self):
        """Test merging nested dictionaries."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_merge_override_replaces_non_dict(self):
        """Test that non-dict values are replaced entirely."""
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = _deep_merge(base, override)
        assert result == {"a": [4, 5]}


class TestExpandPath:
    """Test path expansion logic."""

    def test_expand_tilde(self):
        """Test tilde expansion."""
        result = _expand_path("~/test")
        assert not str(result).startswith("~")
        assert result.is_absolute()

    def test_expand_env_vars(self, monkeypatch, tmp_path):
        """Test environment variable expansion."""
        monkeypatch.setenv("TEST_VAR", str(tmp_path))
        result = _expand_path("$TEST_VAR/file")
        assert result == (tmp_path / "file").resolve()


class TestSyncConfig:
    """Test SyncConfig class."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return {
            "sync_dirs": ["/tmp/test"],
            "s3": {
                "bucket": "test-bucket",
                "region": "us-east-1",
            },
            "threads": 4,
            "scan_interval_seconds": 300,
            "bandwidth": {
                "upload_limit_mbps": 10,
                "download_limit_mbps": 5,
            },
            "conflict": {
                "strategy": "newest_wins",
                "backup_before_overwrite": True,
            },
            "integrity": {
                "enabled": True,
                "algorithm": "md5",
                "on_failure": "warn",
                "max_retries": 3,
            },
            "resources": {
                "max_memory_mb": 512,
                "chunk_size_mb": 8,
            },
            "logging": {
                "level": "INFO",
                "file": "",
                "max_size_mb": 50,
                "backup_count": 3,
            },
            "exclude_file": ".syncignore",
        }

    def test_config_properties(self, sample_config, tmp_path):
        """Test that config properties are accessible."""
        # Create sync directory
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()
        sample_config["sync_dirs"] = [str(sync_dir)]

        cfg = SyncConfig(sample_config, config_dir=tmp_path)

        assert cfg.s3_bucket == "test-bucket"
        assert cfg.s3_region == "us-east-1"
        assert cfg.threads == 4
        assert cfg.scan_interval == 300
        assert cfg.conflict_strategy == "newest_wins"
        assert cfg.integrity_enabled is True
        assert cfg.integrity_algorithm == "md5"

    def test_bandwidth_conversion(self, sample_config, tmp_path):
        """Test bandwidth limit conversion from Mbps to bytes/sec."""
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()
        sample_config["sync_dirs"] = [str(sync_dir)]

        cfg = SyncConfig(sample_config, config_dir=tmp_path)

        # 10 Mbps = 10 * 1_000_000 / 8 = 1_250_000 bytes/sec
        assert cfg.upload_limit_bytes == 1_250_000
        # 5 Mbps = 5 * 1_000_000 / 8 = 625_000 bytes/sec
        assert cfg.download_limit_bytes == 625_000

    def test_validation_missing_bucket(self, sample_config, tmp_path):
        """Test validation fails when bucket is missing."""
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()
        sample_config["sync_dirs"] = [str(sync_dir)]
        sample_config["s3"]["bucket"] = ""

        cfg = SyncConfig(sample_config, config_dir=tmp_path)
        with pytest.raises(ValueError, match="s3.bucket is required"):
            cfg.validate()

    def test_validation_invalid_strategy(self, sample_config, tmp_path):
        """Test validation fails with invalid conflict strategy."""
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()
        sample_config["sync_dirs"] = [str(sync_dir)]
        sample_config["conflict"]["strategy"] = "invalid"

        cfg = SyncConfig(sample_config, config_dir=tmp_path)
        with pytest.raises(ValueError, match="Unknown conflict strategy"):
            cfg.validate()

    def test_validation_nonexistent_dir(self, sample_config, tmp_path):
        """Test validation fails when sync_dir doesn't exist."""
        sample_config["sync_dirs"] = ["/nonexistent/directory"]

        cfg = SyncConfig(sample_config, config_dir=tmp_path)
        with pytest.raises(ValueError, match="sync_dir does not exist"):
            cfg.validate()


class TestLoadConfig:
    """Test config file loading."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config_file = tmp_path / "config.yaml"
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()

        config_data = {
            "sync_dirs": [str(sync_dir)],
            "s3": {
                "bucket": "my-bucket",
            },
        }
        config_file.write_text(yaml.dump(config_data))

        cfg = load_config(config_file)
        assert cfg.s3_bucket == "my-bucket"
        assert len(cfg.sync_dirs) == 1

    def test_load_nonexistent_config(self):
        """Test loading nonexistent config file exits."""
        with pytest.raises(SystemExit):
            load_config("/nonexistent/config.yaml")
