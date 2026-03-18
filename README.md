# s3sync

[![Tests](https://github.com/mtahle/s3-sync.git/workflows/Tests/badge.svg)](https://github.com/mtahle/s3-sync.git/actions)
[![PyPI version](https://badge.fury.io/py/s3sync.svg)](https://badge.fury.io/py/s3sync)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Cross-platform, multithreaded S3 file synchronisation daemon.

## Features

- **Continuous sync** — watches directories for changes in real-time (via `watchdog`) and runs periodic full scans as a safety net.
- **Daemon controls** — start in background and control with `stop`, `pause`, `resume`, `reload`, `daemon-status`.
- **Multithreaded** — configurable thread pool for parallel uploads/downloads.
- **Bandwidth throttling** — token-bucket rate limiter (upload & download independently).
- **Resource-friendly** — chunked streaming (no full-file buffering), optional soft memory cap, bounded thread pool.
- **Configurable** — single `config.yaml` controls everything (S3 target, threads, bandwidth, conflict strategy, integrity, logging).
- **Gitignore-style exclusions** — `.syncignore` file uses the same pattern syntax as `.gitignore`.
- **Auto-reload** — config and exclusion files are reloaded automatically on change.
- **Searchable local index** — SQLite metadata database with full-text search on file paths and folder-prefix listing.
- **Conflict resolution** — `local_wins`, `remote_wins`, `newest_wins`, or `skip` — with optional `.bak` backup before overwriting.
- **Remote delete self-heal** — if an object is deleted directly from S3 but still exists locally, daemon restores it on the next scan.
- **Integrity checks** — post-upload hash verification (MD5 via S3 ETag, or SHA256). Configurable reaction: `warn`, `retry`, or `delete_remote`.
- **Cross-platform** — macOS, Linux, Windows (Python 3.10+).

## Quick Start

```bash
# Install from PyPI
pip install s3sync

# Initialize configuration
s3sync init

# Edit config.yaml with your S3 bucket and sync directories
# Then run:
s3sync start -c config.yaml --background

# Check status
s3sync status -c config.yaml
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `s3sync start -c config.yaml` | Start the sync daemon |
| `s3sync start -c config.yaml --background` | Start daemon in background |
| `s3sync stop -c config.yaml` | Stop background daemon |
| `s3sync pause -c config.yaml` | Pause syncing (daemon stays alive) |
| `s3sync resume -c config.yaml` | Resume syncing after pause |
| `s3sync reload -c config.yaml` | Reload config + exclusions immediately |
| `s3sync daemon-status -c config.yaml` | Show daemon PID/running/state info |
| `s3sync search "report" -c config.yaml` | Search the index for files matching "report" |
| `s3sync ls "photos/2024" -c config.yaml` | List synced files under a path prefix |
| `s3sync pull "docs/file.pdf" ./local.pdf -c config.yaml` | Download a single file from S3 |
| `s3sync status -c config.yaml` | Show index statistics (total files, synced count, total size) |
| `s3sync init` | Create starter `config.yaml` and `.syncignore` |

## Configuration

See `config.yaml` for full documentation. Key settings:

```yaml
sync_dirs:
  - ~/Documents/sync
  - ~/Desktop/uploads

s3:
  bucket: "my-bucket"
  prefix: "backups"
  region: "us-east-1"

threads: 4
scan_interval_seconds: 300

bandwidth:
  upload_limit_mbps: 10    # 0 = unlimited
  download_limit_mbps: 0

conflict:
  strategy: "newest_wins"  # local_wins | remote_wins | newest_wins | skip
  backup_before_overwrite: true

integrity:
  enabled: true
  algorithm: "md5"         # md5 | sha256
  on_failure: "warn"       # warn | retry | delete_remote
```

When multiple `sync_dirs` are configured, one daemon handles all of them.  
S3 keys are namespaced per root (for example `Documents/file.txt`, `uploads-2/file.txt`) to avoid collisions.

## .syncignore

Works exactly like `.gitignore`:

```gitignore
# OS junk
.DS_Store
Thumbs.db

# Build artefacts
node_modules/
__pycache__/
*.pyc

# Secrets
.env
*.pem
```

## Signals (Unix)

- `SIGINT` / `SIGTERM` — graceful shutdown (finish in-flight transfers, close index).
- `SIGHUP` — reload config and exclusions.
- `SIGUSR1` — pause syncing.
- `SIGUSR2` — resume syncing.

## Architecture

```
┌─────────────┐     events      ┌─────────────┐    ThreadPool    ┌──────────┐
│  watchdog   │ ──────────────▸ │   watcher   │ ──────────────▸ │  engine  │
│  (OS-level) │   debounced     │  (handler)  │   submit tasks   │ (upload/ │
└─────────────┘                 └──────┬──────┘                  │ download)│
                                       │                         └────┬─────┘
                          periodic     │                              │
                          full scan    ▼                              ▼
                                ┌─────────────┐              ┌──────────────┐
                                │   daemon    │              │   S3 (boto3) │
                                │ (main loop) │              │  + throttle  │
                                └─────────────┘              │  + integrity │
                                       │                     └──────────────┘
                                       ▼
                                ┌─────────────┐
                                │   SQLite    │
                                │   index     │
                                └─────────────┘
```

## License

MIT
