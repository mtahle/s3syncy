# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-18

### Added
- Initial release of s3sync
- Cross-platform multithreaded S3 file synchronization daemon
- Real-time file watching with watchdog
- Periodic full scans as safety net
- Daemon lifecycle controls (start, stop, pause, resume, reload)
- Configurable thread pool for parallel uploads/downloads
- Bandwidth throttling with token-bucket rate limiter
- Resource-friendly chunked streaming (no full-file buffering)
- Single YAML configuration file
- `.syncignore` file support with gitignore-style patterns
- Auto-reload on config and exclusion file changes
- SQLite-based local index with full-text search
- Multiple conflict resolution strategies (local_wins, remote_wins, newest_wins, skip)
- Remote delete self-heal capability
- Integrity verification (MD5 and SHA256)
- Cross-platform support (macOS, Linux, Windows)
- Fixed KeyboardInterrupt handling in CLI

### Features
- Continuous sync with real-time change detection
- Bandwidth throttling (upload & download independently)
- Configurable integrity checks with multiple hash algorithms
- Searchable local index with path prefix listing
- Conflict resolution with optional backup before overwrite
- Remote delete recovery
