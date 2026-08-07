# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3](https://github.com/mtahle/s3syncy/compare/0.1.2...0.1.3) (2026-08-07)


### Bug Fixes

* correct publish workflow indentation ([f0ebe1e](https://github.com/mtahle/s3syncy/commit/f0ebe1e96c41719306f37ad75836d1b49e8fc37f))

## [0.1.2](https://github.com/mtahle/s3syncy/compare/0.1.1...0.1.2) (2026-08-07)


### Bug Fixes

* correct publish workflow indentation ([f0ebe1e](https://github.com/mtahle/s3syncy/commit/f0ebe1e96c41719306f37ad75836d1b49e8fc37f))
* make publish workflow validate tags correctly ([4dda4c1](https://github.com/mtahle/s3syncy/commit/4dda4c1ca3fb10fc5ddf24dfb4ff76b9290031b6))
* use PyPI API tokens for publish workflow ([1fc1d50](https://github.com/mtahle/s3syncy/commit/1fc1d503efe9c3ffd660d7b87b8d3eed3827a780))

## [Unreleased]

### Added
- Initial test infrastructure and developer workflow documentation
- Local integration test support for S3-compatible storage via MinIO

### Changed
- Standardized runtime naming to `s3syncy` across CLI, daemon logging, thread names, and index DB files
- Made daemon PID file writes atomic for safer startup/shutdown handling

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
