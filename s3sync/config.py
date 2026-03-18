"""Load, validate and expose the YAML configuration."""

from __future__ import annotations

import logging
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml

log = logging.getLogger(__name__)

# ── defaults ────────────────────────────────────────────────────────────────

DEFAULTS: Dict[str, Any] = {
    "sync_dirs": [],
    "s3": {
        "bucket": "",
        "prefix": "",
        "region": "us-east-1",
        "profile": "",
        "endpoint_url": "",
    },
    "exclude_file": ".syncignore",
    "threads": 4,
    "scan_interval_seconds": 300,
    "bandwidth": {
        "upload_limit_mbps": 0,
        "download_limit_mbps": 0,
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
}


# ── helpers ─────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (non-destructive)."""
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _expand_path(p: str) -> Path:
    """Expand ``~`` and environment variables, then resolve."""
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


# ── public API ──────────────────────────────────────────────────────────────

class SyncConfig:
    """Immutable-ish wrapper around the parsed YAML config."""

    def __init__(self, raw: Dict[str, Any], config_dir: Path) -> None:
        self._raw = raw
        self._config_dir = config_dir

    # -- shortcuts --------------------------------------------------------

    @property
    def sync_dirs(self) -> list[Path]:
        return [_expand_path(d) for d in self._raw["sync_dirs"]]

    @property
    def s3_bucket(self) -> str:
        return self._raw["s3"]["bucket"]

    @property
    def s3_prefix(self) -> str:
        return self._raw["s3"].get("prefix", "").strip("/")

    @property
    def s3_region(self) -> str:
        return self._raw["s3"]["region"]

    @property
    def s3_profile(self) -> str:
        return self._raw["s3"].get("profile", "")

    @property
    def s3_endpoint_url(self) -> str:
        return self._raw["s3"].get("endpoint_url", "")

    @property
    def exclude_file(self) -> Path:
        p = Path(self._raw["exclude_file"])
        if not p.is_absolute():
            p = self._config_dir / p
        return p.resolve()

    @property
    def threads(self) -> int:
        return max(1, int(self._raw["threads"]))

    @property
    def scan_interval(self) -> int:
        return max(10, int(self._raw["scan_interval_seconds"]))

    @property
    def upload_limit_bytes(self) -> int:
        """Bytes per second (0 = unlimited)."""
        mbps = float(self._raw["bandwidth"]["upload_limit_mbps"])
        return int(mbps * 1_000_000 / 8) if mbps > 0 else 0

    @property
    def download_limit_bytes(self) -> int:
        mbps = float(self._raw["bandwidth"]["download_limit_mbps"])
        return int(mbps * 1_000_000 / 8) if mbps > 0 else 0

    @property
    def conflict_strategy(self) -> str:
        return self._raw["conflict"]["strategy"]

    @property
    def backup_before_overwrite(self) -> bool:
        return bool(self._raw["conflict"]["backup_before_overwrite"])

    @property
    def integrity_enabled(self) -> bool:
        return bool(self._raw["integrity"]["enabled"])

    @property
    def integrity_algorithm(self) -> str:
        return self._raw["integrity"]["algorithm"]

    @property
    def integrity_on_failure(self) -> str:
        return self._raw["integrity"]["on_failure"]

    @property
    def integrity_max_retries(self) -> int:
        return int(self._raw["integrity"]["max_retries"])

    @property
    def chunk_size(self) -> int:
        """Chunk size in bytes."""
        return max(5, int(self._raw["resources"]["chunk_size_mb"])) * 1024 * 1024

    @property
    def max_memory_mb(self) -> int:
        return int(self._raw["resources"]["max_memory_mb"])

    @property
    def log_level(self) -> str:
        return self._raw["logging"]["level"].upper()

    @property
    def log_file(self) -> str:
        return self._raw["logging"].get("file", "")

    @property
    def log_max_size(self) -> int:
        return int(self._raw["logging"]["max_size_mb"]) * 1024 * 1024

    @property
    def log_backup_count(self) -> int:
        return int(self._raw["logging"]["backup_count"])

    # -- validation -------------------------------------------------------

    def validate(self) -> None:
        errors: list[str] = []
        if not self._raw["s3"]["bucket"]:
            errors.append("s3.bucket is required")
        if not self._raw["sync_dirs"]:
            errors.append("sync_dirs must contain at least one path")
        if self.conflict_strategy not in ("local_wins", "remote_wins", "newest_wins", "skip"):
            errors.append(f"Unknown conflict strategy: {self.conflict_strategy}")
        if self.integrity_algorithm not in ("md5", "sha256"):
            errors.append(f"Unknown integrity algorithm: {self.integrity_algorithm}")
        if self.integrity_on_failure not in ("warn", "retry", "delete_remote"):
            errors.append(f"Unknown integrity on_failure: {self.integrity_on_failure}")
        for d in self.sync_dirs:
            if not d.is_dir():
                errors.append(f"sync_dir does not exist: {d}")
        if errors:
            raise ValueError("Config errors:\n  • " + "\n  • ".join(errors))


def load_config(path: str | Path) -> SyncConfig:
    """Read *path*, merge with defaults, return ``SyncConfig``."""
    path = Path(path).resolve()
    if not path.is_file():
        print(f"Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as fh:
        user = yaml.safe_load(fh) or {}
    merged = _deep_merge(DEFAULTS, user)
    cfg = SyncConfig(merged, config_dir=path.parent)
    cfg.validate()
    return cfg
