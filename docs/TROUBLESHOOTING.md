# Troubleshooting Guide

Solutions to common s3sync issues.

## Daemon Won't Start

### Error: "daemon already running"

```bash
$ s3sync start -c config.yaml
Error: daemon already running (pid 12345)
```

**Solutions:**

1. Check if process actually exists:
```bash
s3sync daemon-status -c config.yaml
ps aux | grep "[s]3sync"
```

2. If not running, remove stale PID file:
```bash
rm config.yaml.pid
s3sync start -c config.yaml
```

3. If running, stop it properly:
```bash
s3sync stop -c config.yaml
```

### Error: "KeyboardInterrupt"

The daemon appears to start but immediately exits with a traceback.

**Solution:** This is fixed in v0.1.0+. Upgrade:
```bash
pip install --upgrade s3sync
```

Or run foreground mode to see actual errors:
```bash
s3sync start -c config.yaml
# Exit with Ctrl+C
```

## Sync Isn't Working

### Files aren't uploading

1. **Check daemon is running:**
```bash
s3sync daemon-status -c config.yaml
```

2. **Check file isn't excluded:**
```bash
# Check .syncignore
cat .syncignore

# Test pattern matching
s3sync search "filename" -c config.yaml
```

3. **Check config is valid:**
```bash
# Verify S3 connection
aws s3 ls s3://my-bucket/

# Check permissions
aws s3api head-bucket --bucket my-bucket
```

4. **Check logs:**
```bash
tail -f s3sync.log
```

### Files are stuck "syncing"

1. Check if S3 is slow:
```bash
time aws s3 cp /tmp/test.txt s3://my-bucket/test.txt
```

2. Check bandwidth throttle isn't too low:
```bash
# config.yaml
bandwidth:
  upload_limit_mbps: 10  # Increase this
```

3. Reload config:
```bash
s3sync reload -c config.yaml
```

### Conflict files keep accumulating

Files exist in both local and S3 but never sync.

**Cause:** Probably using `skip` strategy.

**Solution:**

1. Change strategy in config.yaml:
```yaml
conflict:
  strategy: "newest_wins"  # Instead of "skip"
```

2. Reload:
```bash
s3sync reload -c config.yaml
```

3. Daemon will resolve on next scan

## Performance Issues

### Daemon using high CPU

**Causes:**
- Config has too low `scan_interval_seconds`
- Pattern matching is complex (many rules in .syncignore)
- Thread pool set too high

**Solutions:**

1. Increase scan interval:
```yaml
scan_interval_seconds: 600  # 10 minutes instead of 5
```

2. Simplify .syncignore patterns:
```gitignore
# Good (simple patterns)
*.tmp
*.log
# Avoid (complex patterns)
^(?!backups).*        # Regex not supported
```

3. Reduce thread count if maxed out CPU:
```yaml
threads: 2  # Reduce from default 4
```

### Sync is slow

**Causes:**
- Bandwidth throttle set too low
- Slow S3 connection
- Too many files to sync

**Solutions:**

1. Check bandwidth limit:
```yaml
bandwidth:
  upload_limit_mbps: 50    # Increase
  download_limit_mbps: 50  # Increase
```

2. Increase thread count:
```yaml
threads: 8  # More parallel uploads
```

3. Test S3 speed:
```bash
# Should be 10+ Mbps for good connection
aws s3 cp ./largefile.bin s3://my-bucket/test.bin
```

## Configuration Issues

### Error: "config file not found"

```bash
$ s3sync status -c config.yaml
Error: config.yaml not found
```

**Solution:**

1. Create new config:
```bash
s3sync init
```

2. Or specify full path:
```bash
s3sync status -c /full/path/to/config.yaml
```

### Error: "bucket does not exist"

```bash
ERROR: s3 bucket 'wrong-name' does not exist
```

**Solution:**

1. Check bucket name in AWS:
```bash
aws s3 ls
```

2. Update config.yaml:
```yaml
s3:
  bucket: "correct-bucket-name"
```

### Error: "access denied" or "permission denied"

```bash
ERROR: Access Denied (403)
```

**Solutions:**

1. Verify AWS credentials:
```bash
aws sts get-caller-identity
```

2. Check bucket exists in right region:
```bash
aws s3api head-bucket --bucket my-bucket --region us-east-1
```

3. Verify IAM policy allows S3 access:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::my-bucket/*",
    "arn:aws:s3:::my-bucket"
  ]
}
```

## Port/Process Issues

### Error: "daemon already running" but it's not

```bash
rm config.yaml.pid
s3sync start -c config.yaml
```

### Different config files conflict

Ensure each config has unique state file:

```bash
# Good: separate config files
s3sync start -c config1.yaml
s3sync start -c config2.yaml
# Each has its own .pid file

# Bad: would conflict
s3sync start
s3sync start -c ./config.yaml
```

## AWS Credential Issues

### Error: "Unable to locate credentials"

```bash
ERROR: Unable to locate credentials. You can configure credentials by...
```

**Solutions:**

1. Set environment variables:
```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

2. Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

3. Create `~/.aws/config`:
```ini
[default]
region = us-east-1
```

4. On EC2, use IAM role (automatic)

### Credentials work locally but not in cron/systemd

**Cause:** Environment variables or home directory different

**Solution:** Specify credentials explicitly:
```bash
AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy s3sync start -c /path/to/config.yaml
```

Or use IAM role if on AWS infrastructure.

## Getting Help

### Enable debug logging

```yaml
# config.yaml
logging:
  level: "DEBUG"
  file: "s3sync_debug.log"
```

Then check detailed logs:
```bash
tail -f s3sync_debug.log
```

### Collect diagnostic info

```bash
# Config validation
s3sync init

# Check AWS connection
aws s3 ls s3://my-bucket/

# Daemon status
s3sync daemon-status -c config.yaml

# Sync status
s3sync status -c config.yaml

# Recent logs
tail -50 s3sync.log
```

### Report an issue

Include in bug report:
- Python version: `python --version`
- OS: `uname -a`
- s3sync version: `s3sync --version` (if available)
- Relevant config (without credentials)
- Last 50 lines of log file
- Steps to reproduce
