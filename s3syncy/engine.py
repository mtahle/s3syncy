"""Core sync engine — threaded upload / download with integrity checks."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import SyncConfig
from .conflict import Action, ConflictInfo, resolve as resolve_conflict
from .index import SyncIndex
from .integrity import compute_hash, verify_upload
from .patterns import ExclusionFilter
from .throttle import BandwidthLimiter

log = logging.getLogger(__name__)


class _TransferCallback:
    """boto3 transfer callback that feeds the bandwidth limiter."""

    def __init__(self, limiter: BandwidthLimiter, label: str = "") -> None:
        self._limiter = limiter
        self._label = label
        self._seen = 0

    def __call__(self, bytes_amount: int) -> None:
        self._limiter.consume(bytes_amount)
        self._seen += bytes_amount


class SyncEngine:
    """Orchestrates file synchronisation between local dirs and S3."""

    def __init__(
        self,
        cfg: SyncConfig,
        index: SyncIndex,
        exclusion: ExclusionFilter,
    ) -> None:
        self.cfg = cfg
        self.index = index
        self.exclusion = exclusion

        # Bandwidth limiters.
        self._ul = BandwidthLimiter(cfg.upload_limit_bytes)
        self._dl = BandwidthLimiter(cfg.download_limit_bytes)

        # S3 client — one shared client is thread-safe in boto3.
        session_kwargs: dict = {}
        if cfg.s3_profile:
            session_kwargs["profile_name"] = cfg.s3_profile
        session = boto3.Session(**session_kwargs)
        client_kwargs: dict = {"region_name": cfg.s3_region}
        if cfg.s3_endpoint_url:
            client_kwargs["endpoint_url"] = cfg.s3_endpoint_url
        client_kwargs["config"] = BotoConfig(
            max_pool_connections=cfg.threads + 2,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._s3 = session.client("s3", **client_kwargs)

        self._pool = ThreadPoolExecutor(
            max_workers=cfg.threads, thread_name_prefix="s3sync"
        )
        self._active_keys: Set[str] = set()
        self._lock = threading.Lock()
        self._root_scopes = self._build_root_scopes(cfg.sync_dirs)
        if len(self.cfg.sync_dirs) > 1:
            mapping = ", ".join(
                f"{scope}={root}" for root, scope in self._root_scopes.items()
            )
            log.info("Multi-root sync scopes: %s", mapping)

    # ── public API ──────────────────────────────────────────────────────

    def full_scan(self) -> None:
        """Walk every sync_dir, detect changes, upload/download as needed."""
        for sync_dir in self.cfg.sync_dirs:
            self._scan_local(sync_dir)
            self._scan_remote(sync_dir)

    def handle_event(self, path: Path, event_type: str, sync_root: Path) -> None:
        """Handle a single filesystem event (create / modify / delete)."""
        rel = self._rel_path(path, sync_root)
        if rel is None or self.exclusion.is_excluded(rel):
            return
        if event_type == "deleted":
            self._submit(self._delete_remote, rel, sync_root)
        else:
            self._submit(self._upload_one, path, rel, sync_root)

    def pull_file(self, rel_path: str, dest: Path) -> bool:
        """Download a single file from S3 to *dest*."""
        s3_key = self._make_key(rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            cb = _TransferCallback(self._dl, rel_path)
            self._s3.download_file(
                self.cfg.s3_bucket, s3_key, str(dest), Callback=cb,
            )
            log.info("Pulled %s → %s", s3_key, dest)
            return True
        except ClientError as exc:
            log.error("Pull failed %s: %s", s3_key, exc)
            return False

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=True)

    # ── internal: scanning ──────────────────────────────────────────────

    def _scan_local(self, sync_dir: Path) -> None:
        """Walk *sync_dir* and enqueue uploads for new / changed files."""
        futures = []
        for root, dirs, files in os.walk(sync_dir):
            # Prune excluded dirs in-place so os.walk skips them.
            dirs[:] = [
                d for d in dirs
                if not self.exclusion.is_excluded(
                    Path(root, d).relative_to(sync_dir).as_posix() + "/"
                )
            ]
            for fname in files:
                fpath = Path(root, fname)
                rel = fpath.relative_to(sync_dir).as_posix()
                if self.exclusion.is_excluded(rel):
                    continue
                scoped_rel = self._scoped_rel(rel, sync_dir)
                # Quick change-detection: compare mtime + size with index.
                try:
                    stat = fpath.stat()
                except OSError:
                    continue
                rec = self.index.get(scoped_rel)
                if rec and rec.local_mtime == stat.st_mtime and rec.size == stat.st_size:
                    continue  # unchanged
                futures.append(
                    self._submit(self._upload_one, fpath, rel, sync_dir)
                )
        # Wait for this batch (non-blocking to the caller via futures).
        self._wait(futures)

    def _scan_remote(self, sync_dir: Path) -> None:
        """Detect remote-only files and download (or record) them."""
        scope_prefix = self._scope_prefix(sync_dir)
        scoped_key_prefix = f"{scope_prefix}/" if scope_prefix else ""
        prefix = self._make_key(scoped_key_prefix)
        paginator = self._s3.get_paginator("list_objects_v2")
        remote_keys: Dict[str, tuple[str, dict]] = {}
        try:
            for page in paginator.paginate(Bucket=self.cfg.s3_bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    rel = key[len(prefix):] if prefix else key
                    if rel and not self.exclusion.is_excluded(rel):
                        remote_keys[self._scoped_rel(rel, sync_dir)] = (rel, obj)
        except ClientError as exc:
            log.error("Failed to list remote objects: %s", exc)
            return

        futures = []
        for scoped_rel, (local_rel, obj) in remote_keys.items():
            rec = self.index.get(scoped_rel)
            local_path = sync_dir / local_rel
            if local_path.exists():
                # Both exist — potential conflict.
                if rec and rec.status == "synced":
                    continue  # already synced and unchanged
                futures.append(
                    self._submit(
                        self._resolve_and_act,
                        local_path,
                        local_rel,
                        scoped_rel,
                        sync_dir,
                        obj,
                    )
                )
            else:
                # Remote only — download.
                futures.append(
                    self._submit(self._download_one, local_rel, scoped_rel, sync_dir, obj)
                )

        # Self-heal: if remote objects were deleted out-of-band, restore from local.
        for rec in self.index.all_records(sync_root=str(sync_dir)):
            scoped_rel = rec.rel_path
            local_rel = self._local_rel_from_scoped(scoped_rel, sync_dir)
            if local_rel is None:
                continue
            if scoped_rel in remote_keys or self.exclusion.is_excluded(local_rel):
                continue

            local_path = sync_dir / local_rel
            if not local_path.is_file():
                # Drop stale index rows that no longer exist on either side.
                self.index.delete(scoped_rel)
                continue

            log.warning(
                "Remote object missing for %s — restoring from local copy", local_rel
            )
            futures.append(self._submit(self._upload_one, local_path, local_rel, sync_dir))

        self._wait(futures)

    # ── internal: single-file operations ────────────────────────────────

    def _upload_one(self, local_path: Path, rel: str, sync_root: Path) -> None:
        if not local_path.is_file():
            return
        scoped_rel = self._scoped_rel(rel, sync_root)
        s3_key = self._make_key(scoped_rel)

        # Deduplicate concurrent work on the same key.
        with self._lock:
            if s3_key in self._active_keys:
                return
            self._active_keys.add(s3_key)
        try:
            stat = local_path.stat()
            local_hash = compute_hash(local_path, self.cfg.integrity_algorithm)

            # Check if remote is identical (skip upload).
            rec = self.index.get(scoped_rel)
            if rec and rec.local_hash == local_hash and rec.status == "synced":
                log.debug("Skipping (unchanged hash) %s", rel)
                return

            # Check for conflict with remote.
            remote_meta = self._head_object(s3_key)
            if remote_meta and rec and rec.s3_etag != remote_meta.get("ETag", ""):
                action = self._resolve_conflict(local_path, rel, stat, local_hash, remote_meta)
                if action != Action.UPLOAD:
                    if action == Action.DOWNLOAD:
                        self._download_one(rel, scoped_rel, sync_root, remote_meta)
                    return

            # Upload.
            extra = {}
            if self.cfg.integrity_algorithm == "sha256":
                extra["ChecksumAlgorithm"] = "SHA256"
            cb = _TransferCallback(self._ul, rel)
            self._s3.upload_file(
                str(local_path), self.cfg.s3_bucket, s3_key,
                Callback=cb, ExtraArgs=extra,
                Config=boto3.s3.transfer.TransferConfig(
                    multipart_chunksize=self.cfg.chunk_size,
                    max_concurrency=1,  # per-file; pool handles parallelism
                ),
            )
            log.info("Uploaded %s (%s bytes)", rel, stat.st_size)

            # Integrity check.
            if self.cfg.integrity_enabled:
                self._check_integrity(
                    local_path, s3_key, scoped_rel, sync_root, stat, local_hash
                )
            else:
                head = self._head_object(s3_key) or {}
                self.index.upsert(
                    scoped_rel, str(sync_root),
                    size=stat.st_size,
                    local_mtime=stat.st_mtime,
                    local_hash=local_hash,
                    s3_key=s3_key,
                    s3_etag=head.get("ETag", ""),
                    s3_mtime=str(head.get("LastModified", "")),
                    status="synced",
                )
        except Exception as exc:
            log.error("Upload error %s: %s", rel, exc)
            self.index.upsert(scoped_rel, str(sync_root), status="error")
        finally:
            with self._lock:
                self._active_keys.discard(s3_key)

    def _download_one(
        self, rel: str, scoped_rel: str, sync_root: Path, remote_meta: dict
    ) -> None:
        s3_key = self._make_key(scoped_rel)
        local_path = sync_root / rel
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cb = _TransferCallback(self._dl, rel)
            self._s3.download_file(
                self.cfg.s3_bucket, s3_key, str(local_path), Callback=cb,
            )
            stat = local_path.stat()
            local_hash = compute_hash(local_path, self.cfg.integrity_algorithm)
            self.index.upsert(
                scoped_rel, str(sync_root),
                size=stat.st_size,
                local_mtime=stat.st_mtime,
                local_hash=local_hash,
                s3_key=s3_key,
                s3_etag=remote_meta.get("ETag", ""),
                s3_mtime=str(remote_meta.get("LastModified", "")),
                status="synced",
            )
            log.info("Downloaded %s", rel)
        except Exception as exc:
            log.error("Download error %s: %s", rel, exc)

    def _delete_remote(self, rel: str, sync_root: Path) -> None:
        scoped_rel = self._scoped_rel(rel, sync_root)
        s3_key = self._make_key(scoped_rel)
        try:
            self._s3.delete_object(Bucket=self.cfg.s3_bucket, Key=s3_key)
            self.index.delete(scoped_rel)
            log.info("Deleted remote %s", rel)
        except ClientError as exc:
            log.error("Delete error %s: %s", rel, exc)

    # ── integrity ──────────────────────────────────────────────────────

    def _check_integrity(
        self,
        local_path: Path,
        s3_key: str,
        rel: str,
        sync_root: Path,
        stat: os.stat_result,
        local_hash: str,
    ) -> None:
        head = self._head_object(s3_key) or {}
        ok = verify_upload(local_path, head, self.cfg.integrity_algorithm)
        if ok:
            self.index.upsert(
                rel, str(sync_root),
                size=stat.st_size,
                local_mtime=stat.st_mtime,
                local_hash=local_hash,
                s3_key=s3_key,
                s3_etag=head.get("ETag", ""),
                s3_mtime=str(head.get("LastModified", "")),
                status="synced",
            )
            return

        policy = self.cfg.integrity_on_failure
        if policy == "warn":
            log.warning("Integrity check failed for %s — continuing (warn mode)", rel)
            self.index.upsert(
                rel, str(sync_root),
                size=stat.st_size, local_mtime=stat.st_mtime,
                local_hash=local_hash, s3_key=s3_key,
                s3_etag=head.get("ETag", ""),
                status="integrity_warn",
            )
        elif policy == "retry":
            for attempt in range(1, self.cfg.integrity_max_retries + 1):
                log.info("Retrying upload %s (attempt %d)", rel, attempt)
                cb = _TransferCallback(self._ul, rel)
                self._s3.upload_file(
                    str(local_path), self.cfg.s3_bucket, s3_key, Callback=cb,
                )
                head = self._head_object(s3_key) or {}
                if verify_upload(local_path, head, self.cfg.integrity_algorithm):
                    self.index.upsert(
                        rel, str(sync_root),
                        size=stat.st_size, local_mtime=stat.st_mtime,
                        local_hash=local_hash, s3_key=s3_key,
                        s3_etag=head.get("ETag", ""),
                        status="synced",
                    )
                    return
            log.error("Integrity check still failing after %d retries: %s",
                      self.cfg.integrity_max_retries, rel)
            self.index.upsert(rel, str(sync_root), status="integrity_fail")
        elif policy == "delete_remote":
            log.warning("Deleting corrupt remote copy: %s", s3_key)
            self._s3.delete_object(Bucket=self.cfg.s3_bucket, Key=s3_key)
            self.index.upsert(rel, str(sync_root), status="integrity_fail")

    # ── conflict helper ────────────────────────────────────────────────

    def _resolve_conflict(
        self,
        local_path: Path,
        rel: str,
        stat: os.stat_result,
        local_hash: str,
        remote_meta: dict,
    ) -> Action:
        remote_mtime = remote_meta.get("LastModified")
        info = ConflictInfo(
            rel_path=rel,
            local_path=local_path,
            local_mtime=stat.st_mtime,
            local_hash=local_hash,
            remote_mtime=remote_mtime,
            remote_etag=remote_meta.get("ETag", ""),
        )
        return resolve_conflict(
            info, self.cfg.conflict_strategy, self.cfg.backup_before_overwrite,
        )

    def _resolve_and_act(
        self,
        local_path: Path,
        rel: str,
        scoped_rel: str,
        sync_root: Path,
        remote_meta: dict,
    ) -> None:
        """Full conflict resolution path when both local and remote exist."""
        stat = local_path.stat()
        local_hash = compute_hash(local_path, self.cfg.integrity_algorithm)
        action = self._resolve_conflict(local_path, rel, stat, local_hash, remote_meta)
        if action == Action.UPLOAD:
            self._upload_one(local_path, rel, sync_root)
        elif action == Action.DOWNLOAD:
            self._download_one(rel, scoped_rel, sync_root, remote_meta)
        # SKIP → do nothing

    # ── S3 helpers ─────────────────────────────────────────────────────

    def _head_object(self, s3_key: str) -> Optional[dict]:
        try:
            return self._s3.head_object(Bucket=self.cfg.s3_bucket, Key=s3_key)
        except ClientError:
            return None

    def _make_key(self, rel: str) -> str:
        if self.cfg.s3_prefix:
            return f"{self.cfg.s3_prefix}/{rel}" if rel else f"{self.cfg.s3_prefix}/"
        return rel

    def _build_root_scopes(self, roots: list[Path]) -> dict[Path, str]:
        """Create stable, readable scope prefixes for each sync root."""
        if len(roots) <= 1:
            return {roots[0]: ""} if roots else {}
        seen: dict[str, int] = {}
        scopes: dict[Path, str] = {}
        for root in roots:
            base = (root.name or "root").replace("/", "_")
            count = seen.get(base, 0) + 1
            seen[base] = count
            scopes[root] = base if count == 1 else f"{base}-{count}"
        return scopes

    def _scope_prefix(self, sync_root: Path) -> str:
        if len(self.cfg.sync_dirs) <= 1:
            return ""
        return self._root_scopes.get(sync_root, (sync_root.name or "root"))

    def _scoped_rel(self, rel: str, sync_root: Path) -> str:
        scope = self._scope_prefix(sync_root)
        return f"{scope}/{rel}" if scope else rel

    def _local_rel_from_scoped(self, scoped_rel: str, sync_root: Path) -> Optional[str]:
        scope = self._scope_prefix(sync_root)
        if not scope:
            return scoped_rel
        prefix = f"{scope}/"
        if not scoped_rel.startswith(prefix):
            return None
        return scoped_rel[len(prefix):]

    # ── thread helpers ─────────────────────────────────────────────────

    def _submit(self, fn, *args):
        return self._pool.submit(fn, *args)

    @staticmethod
    def _wait(futures: list) -> None:
        for f in as_completed(futures):
            exc = f.exception()
            if exc:
                log.error("Worker error: %s", exc)

    def _rel_path(self, path: Path, sync_root: Path) -> Optional[str]:
        try:
            return path.relative_to(sync_root).as_posix()
        except ValueError:
            return None
