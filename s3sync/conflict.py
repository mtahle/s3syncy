"""Conflict resolution when local and remote files diverge.

Strategies (set in config):
  local_wins   — always overwrite remote with local
  remote_wins  — always overwrite local with remote
  newest_wins  — compare timestamps, newest copy wins
  skip         — do nothing, log the conflict
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class Action(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SKIP = "skip"


@dataclass
class ConflictInfo:
    rel_path: str
    local_path: Path
    local_mtime: float
    local_hash: str
    remote_mtime: Optional[datetime]
    remote_etag: str


def resolve(info: ConflictInfo, strategy: str, backup: bool = True) -> Action:
    """Decide which copy wins and return the appropriate ``Action``."""
    log.info("Conflict on %s — strategy=%s", info.rel_path, strategy)

    if strategy == "local_wins":
        action = Action.UPLOAD
    elif strategy == "remote_wins":
        action = Action.DOWNLOAD
    elif strategy == "newest_wins":
        action = _newest_wins(info)
    elif strategy == "skip":
        action = Action.SKIP
    else:
        log.error("Unknown conflict strategy %r — skipping", strategy)
        action = Action.SKIP

    if backup and action == Action.DOWNLOAD and info.local_path.exists():
        _backup_local(info.local_path)
    elif backup and action == Action.UPLOAD:
        # Remote backup is handled by S3 versioning if enabled; nothing to do.
        pass

    log.info("Resolved %s → %s", info.rel_path, action.value)
    return action


def _newest_wins(info: ConflictInfo) -> Action:
    if info.remote_mtime is None:
        return Action.UPLOAD
    remote_ts = info.remote_mtime.timestamp()
    if info.local_mtime > remote_ts:
        return Action.UPLOAD
    elif remote_ts > info.local_mtime:
        return Action.DOWNLOAD
    # Same timestamp — compare hashes.  If identical, skip.
    if info.local_hash and info.remote_etag:
        etag = info.remote_etag.strip('"')
        if info.local_hash == etag:
            return Action.SKIP
    return Action.SKIP  # tie-break: do nothing


def _backup_local(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    try:
        shutil.copy2(str(path), str(bak))
        log.info("Backed up %s → %s", path.name, bak.name)
    except OSError as exc:
        log.warning("Failed to back up %s: %s", path, exc)
