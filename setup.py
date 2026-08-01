from setuptools import setup, find_packages
import os
import re

# Read the README file for long description
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

# Read version from package __init__.py (single source of truth)
with open(os.path.join(here, "s3syncy", "__init__.py"), encoding="utf-8") as f:
    version = re.search(r'__version__\s*=\s*["\'](.+?)["\']', f.read()).group(1)

setup(
    name="s3syncy",
    version=version,
    description="Cross-platform, multithreaded S3 file synchronization daemon",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mtahle/s3syncy",
    project_urls={
        "Documentation": "https://github.com/mtahle/s3syncy#readme",
        "Source": "https://github.com/mtahle/s3syncy",
        "Issues": "https://github.com/mtahle/s3syncy/issues",
    },
    author="mtahle",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "boto3>=1.28",
        "watchdog>=3.0",
        "pathspec>=0.11",
        "PyYAML>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "s3syncy=s3syncy.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Filesystems",
        "Topic :: Utilities",
    ],
    keywords="s3 sync daemon file backup cloud storage aws",
)
