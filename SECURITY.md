# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Yes             |
| < 0.1   | ❌ No              |

## Reporting Security Vulnerabilities

**Please do not open public GitHub issues for security vulnerabilities.**

Instead, report security issues to: **[GitHub Security Advisory](https://github.com/mtahle/s3syncy/security/advisories)**

**Please include:**
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

## Security Measures

### Continuous Security Scanning

s3syncy implements multiple layers of security scanning:

#### 1. **SAST (Static Application Security Testing)**
   - **Bandit**: Finds common security issues in Python code
   - **CodeQL**: Advanced static analysis for security vulnerabilities
   - Runs on every push and pull request

#### 2. **Dependency Vulnerability Scanning**
   - **Safety**: Checks Python dependencies for known vulnerabilities
   - **Pip-Audit**: Alternative dependency vulnerability scanner
   - **Trivy**: Container and dependency image scanning
   - Weekly scheduled scans

#### 3. **Secret Detection**
   - **TruffleHog**: Scans for leaked credentials and secrets
   - Prevents accidental exposure of API keys, tokens, etc.

#### 4. **Automated Dependency Management**
   - **Dependabot**: Automatic security and patch updates
   - Weekly checks for outdated dependencies
   - Automated PRs for available updates

### Code Quality & Security Standards

- Linting with `flake8`
- Type checking with `mypy` (can be enabled)
- Tested on Python 3.10, 3.11, 3.12
- Cross-platform testing (Windows, macOS, Linux)

### Security Best Practices

The s3syncy project follows these security principles:

- ✅ **No hardcoded credentials** - Uses AWS SDK credential chain
- ✅ **Minimal dependencies** - Core functionality depends only on: boto3, watchdog, PyYAML, pathspec
- ✅ **Input validation** - Configuration and file paths are validated
- ✅ **Integrity checking** - Optional MD5/SHA256 verification for uploads
- ✅ **Bandwidth throttling** - Prevents resource exhaustion
- ✅ **Error handling** - Graceful error handling without information disclosure

## Dependency Vulnerability Management

### Automated Updates
- Dependabot checks weekly for security and patch updates
- Critical security updates are prioritized
- Updates are tested against full test suite before merge

### Manual Security Audits
Run manual security checks:

```bash
# Check for vulnerable dependencies
pip install safety
safety check

# Alternative: pip-audit
pip install pip-audit
pip-audit

# Run SAST with Bandit
pip install bandit
bandit -r s3syncy/
```

## Secure Configuration

### AWS Credentials
- Use AWS credential files or environment variables
- Never commit credentials to Git
- Consider using IAM roles when running on AWS infrastructure

### File Permissions
- Ensure `config.yaml` has restricted permissions (600)
- `.syncignore` should match your security policies
- Log files may contain sensitive information

## Compliance

- Published package follows PyPI security guidelines
- Uses OIDC-based trusted publishing (no API tokens in CI/CD)
- GitHub repository configured with branch protection rules

## Security Headers

The GitHub repository is configured with:
- ✅ Branch protection on `main`
- ✅ Require status checks before merge
- ✅ Dismiss stale PR approvals
- ✅ Require code reviews
- ✅ Signed commits (recommended)

## Contact

For security questions or concerns: Please use GitHub Security Advisories or contact the maintainer.

---

**Last Updated:** March 2026
**Maintained By:** mtahle
