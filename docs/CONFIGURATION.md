# Configuration Reference

Complete reference for all options in `config.yaml`.

## Top-Level Configuration

```yaml
sync_dirs:
  - ~/Documents/important
  - ~/Desktop/backups

s3:
  bucket: "my-bucket"
  prefix: "optional-prefix"
  region: "us-east-1"

threads: 4
scan_interval_seconds: 300

bandwidth:
  upload_limit_mbps: 0
  download_limit_mbps: 0

conflict:
  strategy: "newest_wins"
  backup_before_overwrite: false

integrity:
  enabled: true
  algorithm: "md5"
  on_failure: "warn"

logging:
  level: "INFO"
  file: "s3sync.log"
```

## sync_dirs (Required)

List of local directories to synchronize with S3.

```yaml
sync_dirs:
  - ~/Documents
  - ~/Mobile
  - /mnt/external/backups
```

**Notes:**
- Paths are expanded (~ → home directory, environment variables)
- Relative paths are resolved from config file location
- Each directory gets its own S3 namespace
- Supports absolute and relative paths

## s3 (Required)

### bucket
**Type:** string  
**Required:** Yes  
**Description:** The S3 bucket name (without s3:// prefix)

```yaml
s3:
  bucket: "my-company-backups"
```

### prefix
**Type:** string  
**Default:** "" (root of bucket)  
**Description:** Optional S3 key prefix (path-like prefix for all keys)

```yaml
s3:
  prefix: "backups/recent"
```

### region
**Type:** string  
**Default:** "us-east-1"  
**Description:** AWS region where the bucket exists

```yaml
s3:
  region: "eu-west-1"
```

## threads

**Type:** integer  
**Default:** 4  
**Description:** Number of worker threads for parallel uploads/downloads  

```yaml
threads: 8  # For faster sync on good connections
```

**Considerations:**
- Higher values = faster sync but more CPU/memory
- Typical: 4-8
- Max recommended: 16
- Min: 1

## scan_interval_seconds

**Type:** integer  
**Default:** 300 (5 minutes)  
**Description:** Interval between full directory scans (safety net)

```yaml
scan_interval_seconds: 120  # Scan every 2 minutes
```

**Notes:**
- Real-time changes via watchdog happen instantly
- Full scans catch external S3 deletions (remote delete self-heal)
- Lower values = more CPU usage but catches deletions faster

## bandwidth

Control upload and download speeds independently.

### upload_limit_mbps
**Type:** float  
**Default:** 0 (unlimited)  
**Description:** Upload speed limit in Mbps

```yaml
bandwidth:
  upload_limit_mbps: 10  # 10 Mbps = ~1.25 MB/s
```

### download_limit_mbps
**Type:** float  
**Default:** 0 (unlimited)  
**Description:** Download speed limit in Mbps

```yaml
bandwidth:
  download_limit_mbps: 25  # 25 Mbps
```

## conflict

Handles conflicts when files differ between local and S3.

### strategy
**Type:** string  
**Options:** `local_wins`, `remote_wins`, `newest_wins`, `skip`  
**Default:** `newest_wins`

- **local_wins**: Always use local version, overwrite S3
- **remote_wins**: Always use S3 version, overwrite local
- **newest_wins**: Use newer file (by modification time)
- **skip**: Don't sync conflicted files

```yaml
conflict:
  strategy: "newest_wins"
```

### backup_before_overwrite
**Type:** boolean  
**Default:** false  
**Description:** Create `.bak` backup before overwriting

```yaml
conflict:
  backup_before_overwrite: true
```

When enabled, before overwriting a file, s3sync first renames it:
- Local file → `filename.bak`
- Remote file → backed up separately

## integrity

Verify file integrity after upload.

### enabled
**Type:** boolean  
**Default:** true  
**Description:** Enable integrity checking

### algorithm
**Type:** string  
**Options:** `md5`, `sha256`  
**Default:** `md5`

```yaml
integrity:
  algorithm: "md5"   # Faster, uses S3 ETag
```

- **md5**: Uses S3 ETag (faster)
- **sha256**: More thorough hash

### on_failure
**Type:** string  
**Options:** `warn`, `retry`, `delete_remote`  
**Default:** `warn`

```yaml
integrity:
  on_failure: "retry"
```

- **warn**: Log warning but continue
- **retry**: Retry upload up to 3 times
- **delete_remote**: Delete from S3 and re-upload

## logging

### level
**Type:** string  
**Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`  
**Default:** `INFO`

```yaml
logging:
  level: "DEBUG"  # More verbose
```

### file
**Type:** string  
**Default:** `s3sync.log` (in config directory)  
**Description:** Log file path

```yaml
logging:
  file: "/var/log/s3sync.log"
```

## Environment Variable Expansion

Config values can use environment variables:

```yaml
sync_dirs:
  - $HOME/Documents
  - /data/$USER/backups

s3:
  bucket: $S3_BUCKET
  region: $AWS_REGION
```

Access with `${VAR}` or `$VAR` (both work).

## .syncignore Patterns

Works exactly like `.gitignore`:

```gitignore
# Exclude specific file
.env

# Exclude all in directory
/node_modules/
__pycache__/

# Exclude by extension
*.tmp
*.log
*.pid

# Exclude everywhere
.DS_Store
Thumbs.db

# Negate (include this file even if parent excluded)
!important.log
```

## Complete Example

```yaml
# Backup multiple directories
sync_dirs:
  - ~/Documents
  - ~/Desktop
  - ~/Code/projects

# S3 configuration
s3:
  bucket: "my-company-backups"
  prefix: "user-data/john"
  region: "eu-west-1"

# Performance tuning
threads: 6
scan_interval_seconds: 180

# Network throttling
bandwidth:
  upload_limit_mbps: 8
  download_limit_mbps: 20

# Conflict resolution
conflict:
  strategy: "newest_wins"
  backup_before_overwrite: true

# Ensure file integrity
integrity:
  enabled: true
  algorithm: "sha256"
  on_failure: "retry"

# Logging
logging:
  level: "INFO"
  file: "./logs/s3sync.log"
```

## Configuration Inheritance

Changes to `config.yaml` are automatically reloaded when you run:

```bash
s3sync reload -c config.yaml
```

Or the daemon auto-reloads when it detects changes (within 5 seconds).
