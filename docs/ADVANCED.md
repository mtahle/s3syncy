# Advanced Usage

Advanced features and optimization techniques.

## Auto-Start on System Boot

### Linux (systemd)

Create `/etc/systemd/system/s3sync.service`:

```ini
[Unit]
Description=s3sync S3 Synchronization Daemon
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/s3sync start -c /opt/s3sync/config.yaml --background
ExecStop=/usr/local/bin/s3sync stop -c /opt/s3sync/config.yaml
ExecReload=/usr/local/bin/s3sync reload -c /opt/s3sync/config.yaml
Restart=on-failure
RestartSec=10
User=s3sync
Group=s3sync

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable s3sync
sudo systemctl start s3sync
```

Monitor:
```bash
sudo systemctl status s3sync
sudo journalctl -u s3sync -f
```

### macOS (launchd)

Create `~/Library/LaunchAgents/com.s3sync.daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.s3sync.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/s3sync</string>
        <string>start</string>
        <string>-c</string>
        <string>$HOME/.s3sync/config.yaml</string>
        <string>--background</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.s3sync/s3sync.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.s3sync/s3sync.log</string>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.s3sync.daemon.plist
```

### Windows (Task Scheduler)

1. Create batch file `C:\s3sync\start_daemon.bat`:
```batch
@echo off
cd C:\s3sync
python -m s3sync.cli start -c config.yaml --background
```

2. Open Task Scheduler
3. Create Basic Task
   - Name: "s3sync Daemon"
   - Trigger: "At computer startup"
   - Action: Start program: `C:\s3sync\start_daemon.bat`

## Multi-Directory Optimization

### Sync different directories with different settings

Use separate config files and damons:

```bash
# config_docs.yaml
s3sync start -c config_docs.yaml --background

# config_media.yaml (higher bandwidth)
s3sync start -c config_media.yaml --background

# config_archive.yaml (lower priority)
s3sync start -c config_archive.yaml --background
```

Each daemon runs independently with its own:
- Thread pool
- Bandwidth limits
- Conflict strategy
- Scan interval

## Network Optimization

### For Slow Connections

```yaml
threads: 2              # Reduce parallelism
bandwidth:
  upload_limit_mbps: 2
  download_limit_mbps: 5
scan_interval_seconds: 900  # Scan less frequently
```

### For High Bandwidth

```yaml
threads: 16             # More parallelism
bandwidth:
  upload_limit_mbps: 100
  download_limit_mbps: 100
scan_interval_seconds: 60  # More aggressive
```

### Optimized for Large Files

```yaml
threads: 4
conflict:
  strategy: "newest_wins"
integrity:
  algorithm: "md5"  # Faster than SHA256
```

## Monitoring and Alerting

### Check sync health

Script to monitor daemon:

```bash
#!/bin/bash
CONFIG="./config.yaml"

while true; do
    STATUS=$(s3sync daemon-status -c $CONFIG)
    if [ $? -ne 0 ]; then
        echo "ERROR: Daemon not running"
        # Send alert (email, Slack, etc)
        exit 1
    fi
    
    SYNCED=$(s3sync status -c $CONFIG | jq .synced)
    TOTAL=$(s3sync status -c $CONFIG | jq .total_files)
    
    if [ $SYNCED -ne $TOTAL ]; then
        echo "Syncing: $SYNCED/$TOTAL files"
    fi
    
    sleep 60
done
```

### Log monitoring

Parse logs for errors:

```bash
grep "ERROR" s3sync.log | tail -20
```

## S3 Optimization

### Use CloudFront for faster downloads

Configure S3 with CloudFront:

```yaml
# Later s3sync versions may support this
s3:
  bucket: "my-bucket"
  cloudfront_url: "https://d123456.cloudfront.net"
```

### Upload to multiple regions

For redundancy, sync to multiple buckets:

```bash
# Terminal 1: US region
s3sync start -c config_us.yaml --background

# Terminal 2: EU region
s3sync start -c config_eu.yaml --background
```

### S3 Storage Class Transitions

S3 automatically transitions old objects via lifecycle policies:

```json
{
  "Rules": [
    {
      "Id": "Archive old files",
      "Status": "Enabled",
      "Prefix": "backups/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

## Backup Strategies

### Incremental Backups

```yaml
sync_dirs:
  - ~/Documents

conflict:
  strategy: "newest_wins"
  backup_before_overwrite: true
```

### Immutable Backups

```yaml
conflict:
  strategy: "skip"  # Never overwrite
```

Combine with automated timestamp-versioning in S3:

```yaml
s3:
  bucket: "backups"
  prefix: "daily-$(date +%Y%m%d)"  # Not yet supported
```

### Disaster Recovery

Store config and important files in git:

```bash
git add config.yaml CONTRIBUTING.md
git add docs/
git commit -m "Backup s3sync config"
git push origin main
```

## Development Workflow

### Local testing before cloud sync

```bash
# Test locally first
s3sync init
# Edit config.yaml with test S3 bucket
s3sync start -c config.yaml

# Verify locally
s3sync status -c config.yaml
s3sync search "filename" -c config.yaml

# Then run in background
s3sync stop -c config.yaml
s3sync start -c config.yaml --background
```

### A/B testing different strategies

```yaml
# config_strategy_1.yaml
conflict:
  strategy: "newest_wins"

# config_strategy_2.yaml
conflict:
  strategy: "local_wins"
```

Compare results with:
```bash
s3sync status -c config_strategy_1.yaml
s3sync status -c config_strategy_2.yaml
```

## Scripting Examples

### Automated daily backup

```bash
#!/bin/bash
# backup.sh

CONFIG="/etc/s3sync/daily-backup.yaml"
LOG="/var/log/s3sync-backup.log"

echo "=== Daily Backup $(date) ===" >> $LOG

# Start if not running
if ! s3sync daemon-status -c $CONFIG > /dev/null 2>&1; then
    echo "Starting daemon..." >> $LOG
    s3sync start -c $CONFIG --background
    sleep 5
fi

# Force reload to ensure latest config
s3sync reload -c $CONFIG

# Wait for sync to complete
PREV_SYNCED=0
STABLE_COUNT=0

while [ $STABLE_COUNT -lt 3 ]; do
    CURRENT=$(s3sync status -c $CONFIG | jq .synced)
    
    if [ $CURRENT -eq $PREV_SYNCED ]; then
        ((STABLE_COUNT++))
    else
        STABLE_COUNT=0
    fi
    
    echo "Synced: $CURRENT" >> $LOG
    PREV_SYNCED=$CURRENT
    sleep 10
done

echo "Backup complete" >> $LOG
```

Run daily with cron:
```bash
0 2 * * * /path/to/backup.sh
```

### Emergency restore

```bash
#!/bin/bash
# restore.sh <s3-key> <local-path>

S3_KEY="$1"
LOCAL_PATH="$2"
CONFIG="./config.yaml"

if [ -z "$S3_KEY" ] || [ -z "$LOCAL_PATH" ]; then
    echo "Usage: restore.sh <s3-key> <local-path>"
    exit 1
fi

echo "Restoring $S3_KEY to $LOCAL_PATH..."
s3sync pull "$S3_KEY" "$LOCAL_PATH" -c $CONFIG

if [ $? -eq 0 ]; then
    echo "Restore complete"
else
    echo "Restore failed"
    exit 1
fi
```

Usage:
```bash
./restore.sh "documents/important.pdf" ./important.pdf
```
