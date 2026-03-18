# Architecture Overview

How s3sync works internally.

## High-Level Components

```
┌─────────────────────────────────────────────┐
│         CLI Interface (cli.py)              │
│  - Command parsing                          │
│  - User interaction                         │
└──────────────┬──────────────────────────────┘
               │
        ┌──────▼───────┐
        │   Config     │
        │   Manager    │
        └──────┬───────┘
               │
     ┌─────────┼─────────┐
     │         │         │
┌────▼────┐ ┌─▼────┐ ┌──▼───────┐
│ Watcher │ │Engine│ │  Index   │
│(watchd) │ │ Core │ │ (SQLite) │
└────┬────┘ └─┬────┘ └──▲───────┘
     │        │         │
     └────┬───┴────┬────┘
          │        │
     ┌────▼────────▼────┐
     │   S3 Interface   │
     │    (boto3)       │
     └──────────────────┘
```

## Core Modules

### cli.py
**Responsibility:** Command-line interface

- Argument parsing (argparse)
- Command routing (start, stop, status, etc.)
- User-facing output formatting
- Exit code handling

**Key Functions:**
- `main()` — Entry point
- `cmd_start()` — Start daemon
- `cmd_stop()` — Stop daemon
- `cmd_status()` — Show statistics

### config.py
**Responsibility:** Configuration management

- Parse YAML config
- Environment variable expansion
- Path resolution (~/, relative, absolute)
- Auto-reload detection
- Validation

**Key Classes:**
- `SyncConfig` — Main config object
- Configuration validation
- Change detection

### engine.py
**Responsibility:** Core sync logic

- File scanning and change detection
- Conflict resolution
- Upload/download orchestration
- Thread pool management
- Rate limiting integration

**Key Classes:**
- `SyncEngine` — Main orchestrator
- Scan logic
- Upload/download workflows

### daemon.py
**Responsibility:** Daemon process management

- Fork/spawn process
- PID file management
- State persistence
- Signal handling (graceful shutdown)
- Background process lifecycle

**Key Classes:**
- `DaemonManager` — Process lifecycle

### watcher.py
**Responsibility:** Real-time file change detection

- Uses `watchdog` library
- Monitors directories for changes
- Debounces rapid changes
- Integrates with engine

**Key Classes:**
- `FileWatcher` — Directory observer

### index.py
**Responsibility:** Local metadata database

- SQLite database of synced files
- File hash caching
- Full-text search
- Prefix-based listing

**Key Classes:**
- `SyncIndex` — Database interface
- FTS (full-text search)

### integrity.py
**Responsibility:** File integrity verification

- Calculate file hashes (MD5, SHA256)
- Verify after upload
- Compare local vs remote
- Handle mismatches

**Key Classes:**
- `IntegrityChecker` — Hash verification

### patterns.py
**Responsibility:** .syncignore pattern matching

- Parse .gitignore-style patterns
- Pattern compilation
- Path matching logic

**Key Classes:**
- `PatternMatcher` — Pattern logic

### throttle.py
**Responsibility:** Bandwidth rate limiting

- Token bucket algorithm
- Upload limit
- Download limit
- Per-thread rate limiting

**Key Classes:**
- `Throttle` — Rate limiter

### conflict.py
**Responsibility:** Conflict resolution

- Compare local vs remote
- Apply strategy (newest_wins, local_wins, etc.)
- Handle backups

**Key Classes:**
- `ConflictResolver` — Resolution logic

## File Sync Workflow

### Upload Flow

```
File Change Detected
    ↓
Check if should sync (not in .syncignore)
    ↓
Calculate hash
    ↓
Check if file exists in S3
    ↓
If exists → Resolve conflict
    ↓
Start upload (with bandwidth throttle)
    ↓
Verify integrity (hash check)
    ↓
Update local index
    ↓
Done
```

### Download Flow

```
New/Updated object in S3 detected
    ↓
Check if should download
    ↓
If local exists → Resolve conflict
    ↓
Start download (with throttle)
    ↓
Verify integrity (hash check)
    ↓
Update local index
    ↓
Done
```

## Daemon Lifecycle

### Startup

1. Parse arguments
2. Load config.yaml
3. Initialize SyncIndex (SQLite)
4. Create FileWatcher
5. Fork to background (if --background)
6. Save PID file
7. Start main event loop

### Main Loop

1. **Every scan_interval** (default 300s):
   - Full directory scan
   - Check S3 for deletions (self-heal)
   - Sync new/changed files

2. **When file changes detected** (real-time):
   - Debounce (coalescence) for 500ms
   - Add to sync queue
   - Process in thread pool

3. **Continuous**:
   - Drive thread pool from sync queue
   - Apply bandwidth limits
   - Handle errors and retries

### Shutdown

1. Signal handler (SIGTERM, SIGINT)
2. Complete in-progress uploads/downloads
3. Flush index to disk
4. Remove PID file
5. Exit cleanly

## Performance Considerations

### Threading

- Configurable thread pool (default 4)
- Each thread handles one file operation
- Allows parallel uploads/downloads
- I/O bound, not CPU bound

### Memory

- Chunked streaming (no full file loading)
- Optional soft memory cap (not implemented yet)
- Index database on disk (not in memory)
- Per-thread I/O buffers

### Network

- Bandwidth throttling (token bucket)
- Retry logic for transient failures
- Connection pooling via boto3
- Multipart upload for large files (via boto3)

### Disk

- Efficient inode watching via watchdog
- Debouncing to reduce redundant scans
- Full scans as safety net only every 5 minutes
- Index updates batched in transactions

## Conflict Resolution Strategies

### local_wins
- Always use local version
- Upload overwrites S3
- Risk: Loses remote changes

### remote_wins
- Always use S3 version
- Download overwrites local
- Risk: Loses local changes

### newest_wins
- Compare modification times
- Use newer version
- Default and recommended

### skip
- Never sync conflicted files
- Requires manual resolution
- Safest for critical data

## State Persistence

### config.yaml.pid
Contains daemon PID:
```
51360
```

### config.yaml.state.json
Contains daemon state:
```json
{
  "status": "running",
  "pid": 51360,
  "config_path": "/path/to/config.yaml",
  "updated_at": "2026-03-18T04:56:42.239678+00:00"
}
```

### .s3sync_index.db
SQLite database with:
- Synced files metadata
- File hashes (MD5/SHA256)
- Full-text search index
- Lake of last state

## Error Handling

### Transient Errors
- Retry up to 3 times
- Exponential backoff (1s, 2s, 4s)
- Log warnings

### Permanent Errors
- Log error and continue
- Mark file as failed
- User can manually retry

### Critical Errors
- Log error
- Exit daemon
- User must investigate

## Security Considerations

1. **AWS Credentials**
   - Never stored locally
   - Use IAM roles when possible
   - Support environment variables

2. **Local Permissions**
   - Respects file permissions
   - Requires read permission to sync
   - Requires write permission to download

3. **S3 Encryption**
   - Server-side (SSE) supported
   - Client-side via boto3
   - Configure via config.yaml

4. **.syncignore Security**
   - Plain text file
   - Should exclude sensitive data
   - Version control with .gitignore
