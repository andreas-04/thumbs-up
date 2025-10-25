#!/bin/bash
# Build script for creating Debian .deb package

set -e  # Exit on error

echo "=========================================="
echo "Building ThumbsUp Client .deb Package"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo "Error: setup.py not found. Run this script from client-dist directory."
    exit 1
fi

# Check for required tools
echo "Checking dependencies..."
if ! command -v dpkg-buildpackage &> /dev/null; then
    echo "Error: dpkg-buildpackage not found."
    echo "Install with: sudo apt-get install dpkg-dev debhelper dh-python"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/ debian/thumbsup-client/ debian/.debhelper/ debian/files
rm -f ../thumbsup-client_*.deb ../thumbsup-client_*.tar.* ../thumbsup-client_*.dsc ../thumbsup-client_*.changes ../thumbsup-client_*.buildinfo

# Build the package
echo ""
echo "Building Debian package..."
dpkg-buildpackage -us -uc -b

# Move built package to dist/
echo ""
echo "Organizing build artifacts..."
mkdir -p dist
mv ../thumbsup-client_*.deb dist/ 2>/dev/null || true
mv ../thumbsup-client_*.changes dist/ 2>/dev/null || true
mv ../thumbsup-client_*.buildinfo dist/ 2>/dev/null || true

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo ""
echo "Package location: dist/thumbsup-client_0.0.0-1_all.deb"
echo ""
echo "To install:"
echo "  sudo dpkg -i dist/thumbsup-client_0.0.0-1_all.deb"
echo "  sudo apt-get install -f  # Fix any dependency issues"
echo ""
echo "Or test in Docker:"
echo "  docker run --rm -v \$(pwd)/dist:/dist -it ubuntu:22.04 bash"
echo "  # apt-get update && apt-get install -y /dist/thumbsup-client_0.0.0-1_all.deb"
echo ""
