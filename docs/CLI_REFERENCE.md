# CLI Reference

Complete command-line interface documentation for s3sync.

## Basic Usage

```bash
s3sync <command> [options]
```

## Global Options

Global options that work with all commands:

```bash
-c, --config <path>  Path to config.yaml (default: config.yaml)
-h, --help           Show help message
```

## Commands

### init

Initialize a new configuration.

```bash
s3sync init
```

**Creates:**
- `config.yaml` — Main configuration file
- `.syncignore` — Exclusion patterns

**Example:**
```bash
$ s3sync init
Created config.yaml in current directory
Created .syncignore in current directory
Edit config.yaml and set your S3 bucket and directories to sync.
```

### start

Start the synchronization daemon.

```bash
s3sync start -c config.yaml [--background]
```

**Options:**
- `--background` — Run daemon in background (returns immediately)
- `-c, --config` — Config file path

**Examples:**

Foreground (blocking):
```bash
s3sync start -c config.yaml
```

Background (returns with PID):
```bash
s3sync start -c config.yaml --background
Started daemon in background (pid 12345)
```

**Output:**
- Foreground: Real-time logs until Ctrl+C
- Background: Returns PID to stdout

### stop

Stop the background daemon.

```bash
s3sync stop -c config.yaml
```

**Example:**
```bash
$ s3sync stop -c config.yaml
Daemon stopped (pid was 12345)
```

### pause

Pause syncing without stopping the daemon.

```bash
s3sync pause -c config.yaml
```

**Effect:**
- Daemon continues running
- File watching pauses
- Full scans pause
- Resume with `s3sync resume`

### resume

Resume syncing after pause.

```bash
s3sync resume -c config.yaml
```

### reload

Reload configuration and `.syncignore` without restarting.

```bash
s3sync reload -c config.yaml
```

**Example:**
```bash
$ s3sync reload -c config.yaml
Configuration reloaded
```

**What reloads:**
- All config.yaml settings (threads, bandwidth, etc.)
- .syncignore patterns
- S3 settings (bucket, region, prefix)

### daemon-status

Show daemon status and state.

```bash
s3sync daemon-status -c config.yaml
```

**Output:**
```json
{
  "running": true,
  "pid": 12345,
  "pid_file": "/path/to/config.yaml.pid",
  "state_file": "/path/to/config.yaml.state.json",
  "state": {
    "status": "running",
    "pid": 12345,
    "config_path": "/path/to/config.yaml",
    "updated_at": "2026-03-18T10:30:42Z"
  }
}
```

**JSON Fields:**
- `running` — Daemon process exists
- `pid` — Process ID
- `state.status` — Current status (running, paused, etc.)

### status

Show synchronization statistics.

```bash
s3sync status -c config.yaml
```

**Output:**
```json
{
  "total_files": 1234,
  "synced": 1200,
  "total_size_bytes": 5368709120
}
```

**Fields:**
- `total_files` — Total files to sync (excluding .syncignore)
- `synced` — Files already synced to S3
- `total_size_bytes` — Total size of all files (in bytes)

**Example:**
```bash
$ s3sync status -c config.yaml
{
  "total_files": 1640,
  "synced": 1639,
  "total_size_bytes": 774206307
}
```

### search

Search local index for files.

```bash
s3sync search <pattern> -c config.yaml
```

**Examples:**
```bash
# Search by name
s3sync search "report" -c config.yaml

# Wildcard patterns
s3sync search "*.pdf" -c config.yaml

# Full-text search
s3sync search "invoice" -c config.yaml
```

**Output:**
```
results/report_2026.pdf
results/report_archive/2025.pdf
documents/annual_report.doc
```

### ls

List files under a path prefix.

```bash
s3sync ls <prefix> -c config.yaml
```

**Examples:**
```bash
# List all files
s3sync ls "" -c config.yaml

# List in directory
s3sync ls "documents/" -c config.yaml

# Nested paths
s3sync ls "backups/2026/" -c config.yaml
```

**Output:**
```
documents/report.pdf
documents/archive/old_report.pdf
documents/notes.txt
```

### pull

Download a single file from S3 to local.

```bash
s3sync pull <s3-key> <local-path> -c config.yaml
```

**Arguments:**
- `s3-key` — Key path in S3
- `local-path` — Local file path to save to

**Examples:**
```bash
# Download to current directory
s3sync pull "backups/archive.zip" ./archive.zip -c config.yaml

# Download to specific location
s3sync pull "documents/report.pdf" ~/Downloads/report.pdf -c config.yaml
```

**Notes:**
- Creates parent directories if needed
- Overwrites existing file without prompt
- Uses configured bandwidth limits

## Exit Codes

- `0` — Success
- `1` — General error
- `2` — Configuration error
- `3` — S3 connection error

## Common Patterns

### Monitor daemon in one terminal

Terminal 1 (start daemon):
```bash
s3sync start -c config.yaml --background
```

Terminal 2 (monitor):
```bash
watch s3sync status -c config.yaml
```

### Backup multiple directories

```yaml
# config.yaml
sync_dirs:
  - ~/Documents
  - ~/Desktop
  - ~/Code
```

### Setup with custom log file

```bash
# config.yaml
logging:
  file: "/var/log/s3sync.log"
  level: "INFO"
```

Then check with:
```bash
tail -f /var/log/s3sync.log
```

### Reload after editing .syncignore

1. Edit `.syncignore` to add/remove patterns
2. Run reload command:
   ```bash
   s3sync reload -c config.yaml
   ```
3. New patterns take effect immediately

## Troubleshooting

### Command not found
```bash
# Try full path
python -m s3sync.cli status -c config.yaml

# Or install in dev mode
pip install -e .
```

### Config file not found
```bash
# Specify full path
s3sync status -c /path/to/config.yaml

# Or cd to directory with config
cd /path/to/config
s3sync status
```

### Permission denied errors
Check AWS credentials and bucket permissions:
```bash
aws s3 ls s3://my-bucket/
```

### Daemon won't start
Check the log file and `.syncignore` patterns:
```bash
cat s3sync.log
```
