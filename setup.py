from setuptools import setup, find_packages
import os

# Read the README file for long description
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="s3sync",
    version="0.1.0",
    description="Cross-platform, multithreaded S3 file synchronization daemon",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mtahle/s3-sync.git",
    project_urls={
        "Documentation": "https://github.com/mtahle/s3-sync.git#readme",
        "Source": "https://github.com/mtahle/s3-sync.git",
        "Issues": "https://github.com/mtahle/s3-sync.git/issues",
    },
    author="mtahle",
    author_email="",
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
            "s3sync=s3sync.cli:main",
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
