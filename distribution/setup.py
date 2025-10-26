#!/usr/bin/env python3
"""
Setup script for ThumbsUp Client
Packages the client for distribution as .deb and .exe
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

setup(
    name="thumbsup-client",
    version="0.0.0",
    description="Secure NAS Client for ThumbsUp - mDNS Discovery + mTLS Authentication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Andreas Neacsu",
    author_email="andreasneacsu@gmail.com",
    url="https://github.com/andreas-04/thumbs-up",
    license="MIT",
    
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    # Include certificate files
    package_data={
        "thumbsup_client": [
            "certs/*.pem",
        ],
    },
    
    # Python version requirement
    python_requires=">=3.8",
    
    # Dependencies
    install_requires=[
        # Zeroconf is a small pure-Python mDNS implementation used as a
        # cross-platform fallback when Avahi command-line tools are
        # not available (Windows/macOS). Keep it minimal.
        "zeroconf>=0.52.0",
    ],
    
    # Entry point for command-line usage
    entry_points={
        "console_scripts": [
            "thumbsup-client=thumbsup_client.client:main",
            "thumbsup=thumbsup_client.client:main",
        ],
    },
    
    # Platform-specific system dependencies (documented, not enforced by pip)
    extras_require={
        "linux": [],  # Requires: avahi-utils, nfs-common (installed via .deb)
        "windows": [],  # Requires: NFS client feature (handled by installer)
    },
    
    # Classifiers for PyPI
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Filesystems",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
    ],
    
    keywords="nas secure-storage mtls nfs file-sharing mDNS",
)
