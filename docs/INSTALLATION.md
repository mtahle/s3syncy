# Installation Guide

## System Requirements

- **Python**: 3.10 or later
- **OS**: Windows, macOS, or Linux
- **AWS Credentials**: Valid AWS credentials with S3 access

## Installation Steps

### 1. Install from PyPI (Recommended)

```bash
pip install s3syncy
```

### 2. Verify Installation

```bash
s3syncy --help
```

You should see the help message listing available commands.

### 3. AWS Credentials Setup

s3sync uses boto3, which looks for credentials in this order:

1. **Environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **AWS credentials file** (`~/.aws/credentials`):
   ```ini
   [default]
   aws_access_key_id = your_key
   aws_secret_access_key = your_secret
   ```

3. **IAM Role** (if running on EC2 or other AWS services)

4. **AWS config file** (`~/.aws/config`):
   ```ini
   [default]
   region = us-east-1
   ```

### 4. Verify AWS Credentials

```bash
# This will work if credentials are set up correctly
s3syncy init
```

## Development Installation

To contribute or run from source:

```bash
# Clone the repository
git clone https://github.com/yourusername/s3sync.git
cd s3sync

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -r requirements.txt
pip install -e .
```

## Upgrading

```bash
pip install --upgrade s3syncy
```

## Uninstalling

```bash
pip uninstall s3syncy
```

Note: This removes the s3sync package but leaves any config files and databases intact.

## Troubleshooting Installation

### Command not found

If `s3sync` command is not found after installation:

- Ensure the pip installation directory is in your PATH
- Try using `python -m s3sync.cli` instead
- On macOS/Linux, you may need to use `python3` instead of `python`

### Permission denied

On macOS/Linux, if you get permission errors:

```bash
sudo python -m pip install s3sync
```

Or use a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
pip install s3sync
```

### Module not found errors

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```
