"""Sample configuration files for testing."""

MINIMAL_CONFIG = """
sync_dirs:
  - /tmp/test

s3:
  bucket: test-bucket
  region: us-east-1
"""

FULL_CONFIG = """
sync_dirs:
  - /tmp/test1
  - /tmp/test2

s3:
  bucket: test-bucket
  prefix: backups
  region: us-west-2
  profile: default
  endpoint_url: ""

exclude_file: .syncignore

threads: 8
scan_interval_seconds: 60

bandwidth:
  upload_limit_mbps: 50
  download_limit_mbps: 100

conflict:
  strategy: newest_wins
  backup_before_overwrite: true

integrity:
  enabled: true
  algorithm: sha256
  on_failure: retry
  max_retries: 5

resources:
  max_memory_mb: 1024
  chunk_size_mb: 16

logging:
  level: DEBUG
  file: /tmp/s3syncy.log
  max_size_mb: 100
  backup_count: 5
"""

SYNCIGNORE_SAMPLE = """
# OS junk
.DS_Store
Thumbs.db
*.tmp

# Version control
.git/
.svn/

# Build outputs
__pycache__/
*.pyc
dist/
build/
"""
