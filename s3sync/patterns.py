"""Gitignore-style pattern matching backed by *pathspec*."""

from __future__ import annotations

import logging
from pathlib import Path

import pathspec

log = logging.getLogger(__name__)


class ExclusionFilter:
    """Load a .syncignore (or .gitignore-format) file and test paths."""

    def __init__(self, exclude_file: Path) -> None:
        self._spec: pathspec.PathSpec | None = None
        self._path = exclude_file
        self.reload()

    # ── public API ──────────────────────────────────────────────────────

    def reload(self) -> None:
        """(Re-)read the exclusion file from disk."""
        if not self._path.is_file():
            log.warning("Exclusion file not found: %s — no patterns loaded", self._path)
            self._spec = pathspec.PathSpec.from_lines("gitwildmatch", [])
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        self._spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        count = sum(1 for p in self._spec.patterns if p.regex)
        log.info("Loaded %d exclusion patterns from %s", count, self._path)

    def is_excluded(self, rel_path: str | Path) -> bool:
        """Return ``True`` if *rel_path* (relative to sync root) is excluded."""
        if self._spec is None:
            return False
        return self._spec.match_file(str(rel_path))
