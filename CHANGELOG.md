# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4](https://github.com/mtahle/s3syncy/compare/0.1.3...0.1.4) (2026-08-08)


### Bug Fixes

* make daemon shutdown responsive to stop signals ([4401a8c](https://github.com/mtahle/s3syncy/commit/4401a8c823d4dc284e91670fddd98c44ea79a8cc))
* make publish workflow run on main merges and repair integration tests yaml ([2c2eb4f](https://github.com/mtahle/s3syncy/commit/2c2eb4fcd309d958231572cd8271b17b9a3bb900))
* pass server /data to minio service container ([def7124](https://github.com/mtahle/s3syncy/commit/def712484c1f098666d042f45f35422d07f9b354))
* repair publish workflow yaml indentation ([#44](https://github.com/mtahle/s3syncy/issues/44)) ([f79e10c](https://github.com/mtahle/s3syncy/commit/f79e10c393fb25203ab9b1381d586b7659f123ef))
* responsive graceful shutdown + version 1.2.0 ([d8a0838](https://github.com/mtahle/s3syncy/commit/d8a0838f244b769625f2f325c10a67f60b5c0028))
* skip existing files on PyPI Test publish ([c399320](https://github.com/mtahle/s3syncy/commit/c3993200cd888d7f10bbf73258a4a1e46e508a00))

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
