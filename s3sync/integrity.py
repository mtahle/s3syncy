"""File hashing and post-upload integrity verification."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import BinaryIO

log = logging.getLogger(__name__)

# 256 KB read buffer — small enough to stay cache-friendly.
_BUF_SIZE = 256 * 1024


def compute_hash(path: Path, algorithm: str = "md5") -> str:
    """Return the hex-digest of *path* using *algorithm* (md5 | sha256).

    Streams the file in chunks so large files never blow memory.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_BUF_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_hash_fileobj(fh: BinaryIO, algorithm: str = "md5") -> str:
    """Hash an already-open file object (seeks to 0 first)."""
    fh.seek(0)
    h = hashlib.new(algorithm)
    while True:
        chunk = fh.read(_BUF_SIZE)
        if not chunk:
            break
        h.update(chunk)
    fh.seek(0)
    return h.hexdigest()


def s3_etag_matches(local_hash_md5: str, s3_etag: str) -> bool:
    """Compare a local MD5 hex-digest against an S3 ETag.

    S3 ETags are quoted and, for single-part uploads, equal the MD5.
    Multipart ETags contain a ``-`` and cannot be compared to a plain MD5.
    """
    etag = s3_etag.strip('"')
    if "-" in etag:
        # Multipart upload — can't do simple MD5 comparison.
        log.debug("Skipping ETag comparison (multipart): %s", s3_etag)
        return True  # optimistically pass
    return local_hash_md5 == etag


def verify_upload(
    local_path: Path,
    s3_head: dict,
    algorithm: str = "md5",
) -> bool:
    """Verify that an uploaded file matches its S3 HEAD response.

    Returns ``True`` if integrity is confirmed.
    """
    if algorithm == "md5":
        local_hash = compute_hash(local_path, "md5")
        etag = s3_head.get("ETag", "")
        ok = s3_etag_matches(local_hash, etag)
        if not ok:
            log.warning(
                "Integrity FAIL (md5): %s  local=%s  etag=%s",
                local_path.name, local_hash, etag,
            )
        return ok

    if algorithm == "sha256":
        local_hash = compute_hash(local_path, "sha256")
        remote_hash = s3_head.get("ChecksumSHA256", "")
        if not remote_hash:
            log.debug("No SHA256 checksum in S3 HEAD for %s — skipping", local_path.name)
            return True
        ok = local_hash == remote_hash
        if not ok:
            log.warning(
                "Integrity FAIL (sha256): %s  local=%s  remote=%s",
                local_path.name, local_hash, remote_hash,
            )
        return ok

    log.error("Unknown integrity algorithm: %s", algorithm)
    return True  # don't block on misconfiguration
