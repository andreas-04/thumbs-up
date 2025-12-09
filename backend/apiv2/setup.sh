#!/bin/bash
#
# ThumbsUp API v2 Setup Script
# Initializes the development environment
#

set -e

echo "========================================"
echo "🚀 ThumbsUp API v2 Setup"
echo "========================================"
echo ""

# Check Python version
echo "📌 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found Python $python_version"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "   ✅ Dependencies installed"
echo ""

# Generate SSL certificates
if [ ! -f "certs/server_cert.pem" ]; then
    echo "🔐 Generating SSL certificates..."
    python generate_certs.py
    echo "   ✅ Certificates generated"
else
    echo "🔐 SSL certificates already exist"
fi
echo ""

# Create storage directory
echo "📁 Setting up storage directory..."
mkdir -p storage
echo "   ✅ Storage directory ready"
echo ""

# Create demo file
echo "📝 Creating demo file..."
cat > storage/README.txt << 'EOF'
Welcome to ThumbsUp File Share!

This is a demonstration file showing how easy it is to share files
with people nearby.

Features:
- 🌐 Access files from any web browser
- 📱 Scan QR code for instant access
- 💻 Mount as network drive on desktop
- 🔒 Secure HTTPS encryption
- 🎫 Time-limited token authentication

How to use:
1. Start the server: python server.py
2. Scan the QR code displayed
3. Browse, upload, and download files

Enjoy secure ad-hoc file sharing!
EOF
echo "   ✅ Demo file created"
echo ""

# Create .env file from example
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env configuration file..."
    cp .env.example .env
    echo "   ✅ Configuration file created"
else
    echo "⚙️  Configuration file already exists"
fi
echo ""

echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "To start the server:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run server: python server.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up --build"
echo ""
