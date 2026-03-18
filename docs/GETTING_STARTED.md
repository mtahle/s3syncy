# Getting Started with s3sync

A quick guide to get up and running with s3sync in 5 minutes.

## Step 1: Install s3sync

```bash
pip install s3sync
```

## Step 2: Initialize Configuration

```bash
s3sync init
```

This creates two files in your current directory:

- **config.yaml** — Main configuration file
- **.syncignore** — Files and patterns to exclude from sync

## Step 3: Configure Your S3 Bucket

Edit `config.yaml`:

```yaml
sync_dirs:
  - ~/Documents/important-files
  - ~/Desktop/backups

s3:
  bucket: "my-company-backups"
  prefix: "user-data"
  region: "us-east-1"

threads: 4
scan_interval_seconds: 300
```

### Minimal Configuration

```yaml
sync_dirs:
  - ~/Documents

s3:
  bucket: "my-bucket"
```

## Step 4: Test the Configuration

Preview what will be synced without starting the daemon:

```bash
s3sync status -c config.yaml
```

This shows:
- Total files that would be synced
- Synced count
- Total size

## Step 5: Start Syncing

### Option A: Run in foreground (for testing)

```bash
s3sync start -c config.yaml
```

Press `Ctrl+C` to stop.

### Option B: Run in background (production)

```bash
s3sync start -c config.yaml --background
```

### Check Status

```bash
s3sync daemon-status -c config.yaml
```

Output:
```json
{
  "running": true,
  "pid": 12345,
  "state": {
    "status": "running",
    "synced_count": 1234,
    "last_scan": "2026-03-18T10:30:00Z"
  }
}
```

## Common Tasks

### Pause Synchronization

```bash
s3sync pause -c config.yaml
```

The daemon continues running but won't sync changes.

### Resume Synchronization

```bash
s3sync resume -c config.yaml
```

### Reload Configuration

```bash
s3sync reload -c config.yaml
```

This reloads both `config.yaml` and `.syncignore` without restarting the daemon.

### Stop the Daemon

```bash
s3sync stop -c config.yaml
```

### Search Files

Find synced files by name:

```bash
s3sync search "document" -c config.yaml
s3sync search "*.pdf" -c config.yaml
```

### List Directory

List files under a specific S3 path:

```bash
s3sync ls "backups/2026" -c config.yaml
```

### Download a File

```bash
s3sync pull "backups/important.zip" ./local.zip -c config.yaml
```

## Understanding .syncignore

The `.syncignore` file works like `.gitignore`:

```gitignore
# System files
.DS_Store
Thumbs.db
.clusterlog

# Build artifacts
/node_modules/
/__pycache__/
/dist/
/build/

# Temporary files
*.tmp
*.log

# Private files
.env
.secrets
```

Changes to `.syncignore` are automatically detected and reloaded (usually within 5 seconds).

## Next Steps

- Read the [Configuration Guide](./CONFIGURATION.md) for advanced settings
- See the [CLI Reference](./CLI_REFERENCE.md) for all available commands
- Check [Troubleshooting](./TROUBLESHOOTING.md) if something goes wrong
- Explore [Advanced Usage](./ADVANCED.md) for optimization tips

## Example Setups

### Simple Daily Backup

```yaml
sync_dirs:
  - ~/Documents

s3:
  bucket: "my-backups"
  prefix: "daily"

conflict:
  strategy: "newest_wins"
```

### Multi-Directory with Throttling

```yaml
sync_dirs:
  - ~/Documents
  - ~/Downloads
  - ~/Desktop

s3:
  bucket: "backups"
  region: "us-west-2"

threads: 8
bandwidth:
  upload_limit_mbps: 5
  download_limit_mbps: 10
```

### Strict Backup with Integrity

```yaml
sync_dirs:
  - ~/financial-data

s3:
  bucket: "secure-backups"
  prefix: "financial"

conflict:
  strategy: "skip"  # Don't overwrite anything
  backup_before_overwrite: true

integrity:
  enabled: true
  algorithm: "sha256"
  on_failure: "retry"  # Retry 3 times on checksum mismatch
```
