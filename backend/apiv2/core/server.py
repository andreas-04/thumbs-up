#!/usr/bin/env python3
"""
ThumbsUp API v2 - Main Server
Ad-hoc file sharing server with web interface.
"""

import os
import sys
import socket
import mimetypes
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.serving import run_simple
import ssl

# Local imports
from core.auth import TokenAuth
from utils.qr_generator import QRGenerator
from services.mdns_advertiser import MDNSAdvertiser


# Get the apiv2 directory (parent of core)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'

# Configuration
CONFIG = {
    'HOST': os.getenv('HOST', '0.0.0.0'),
    'PORT': int(os.getenv('PORT', 8443)),  # HTTPS port
    'STORAGE_PATH': os.getenv('STORAGE_PATH', './storage'),
    'CERT_PATH': os.getenv('CERT_PATH', './certs/server_cert.pem'),
    'KEY_PATH': os.getenv('KEY_PATH', './certs/server_key.pem'),
    'TOKEN_EXPIRY_HOURS': int(os.getenv('TOKEN_EXPIRY_HOURS', 24)),
    'ENABLE_UPLOADS': os.getenv('ENABLE_UPLOADS', 'true').lower() == 'true',
    'ENABLE_DELETE': os.getenv('ENABLE_DELETE', 'false').lower() == 'true',
    'SERVICE_NAME': os.getenv('SERVICE_NAME', 'ThumbsUp File Share'),
    'MAX_UPLOAD_SIZE': int(os.getenv('MAX_UPLOAD_SIZE', 100 * 1024 * 1024)),  # 100MB
    'ADMIN_PIN': os.getenv('ADMIN_PIN'),  # Must be set via environment
}

# Initialize Flask app with explicit template folder
app = Flask(__name__, 
            template_folder=str(TEMPLATE_DIR),
            static_folder=str(STATIC_DIR) if STATIC_DIR.exists() else None)
app.config['MAX_CONTENT_LENGTH'] = CONFIG['MAX_UPLOAD_SIZE']
CORS(app)

# Validate ADMIN_PIN is set
if not CONFIG['ADMIN_PIN']:
    print("ERROR: ADMIN_PIN environment variable is not set!")
    print("   Please run startup.py which will configure the PIN.")
    sys.exit(1)

# Initialize auth with admin PIN
auth = TokenAuth(
    token_expiry_hours=CONFIG['TOKEN_EXPIRY_HOURS'],
    admin_pin=CONFIG['ADMIN_PIN']
)

# Ensure storage directory exists
os.makedirs(CONFIG['STORAGE_PATH'], exist_ok=True)


def get_server_url():
    """Get the server's access URL."""
    hostname = socket.gethostname()
    # Remove .local suffix if already present to avoid double .local
    if hostname.endswith('.local'):
        hostname = hostname[:-6]
    
    # Try to get actual IP address for better compatibility
    try:
        # Get local IP that's not loopback
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        return f"https://{local_ip}:{CONFIG['PORT']}"
    except:
        # Fallback to hostname
        return f"https://{hostname}.local:{CONFIG['PORT']}"


def get_file_list(path=''):
    """
    Get list of files in directory.
    
    Args:
        path: Relative path within storage
    
    Returns:
        List of file/directory info dicts
    """
    full_path = os.path.join(CONFIG['STORAGE_PATH'], path)
    
    if not os.path.exists(full_path):
        return []
    
    items = []
    
    try:
        dir_entries = os.listdir(full_path)
    except (PermissionError, OSError) as e:
        print(f"Error listing directory {full_path}: {e}")
        return []
    
    for item in dir_entries:
        # Skip hidden files and macOS metadata files
        if item.startswith('.') or item.startswith('._'):
            continue
            
        item_path = os.path.join(full_path, item)
        rel_path = os.path.join(path, item) if path else item
        
        try:
            # Skip broken symlinks
            if os.path.islink(item_path) and not os.path.exists(item_path):
                continue
                
            stat = os.stat(item_path)
            
            items.append({
                'name': item,
                'path': rel_path,
                'is_dir': os.path.isdir(item_path),
                'size': stat.st_size if os.path.isfile(item_path) else 0,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except (PermissionError, OSError, FileNotFoundError) as e:
            # Skip files we can't access
            print(f"Skipping {item}: {e}")
            continue
    
    # Sort: directories first, then files alphabetically
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    return items


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page with PIN entry."""
    if request.method == 'POST':
        pin = request.form.get('pin')
        
        if auth.validate_admin_pin(pin):
            # Generate admin session token
            admin_token = auth.generate_admin_session()
            
            # Set cookie and redirect to admin dashboard
            response = redirect('/admin')
            response.set_cookie(
                'admin_token',
                admin_token,
                httponly=True,
                secure=True,
                samesite='Strict',
                max_age=2 * 3600  # 2 hours
            )
            return response
        else:
            # Invalid PIN
            return render_admin_login_page(error="Invalid PIN")
    
    # GET request - show login form
    return render_admin_login_page()


def render_admin_login_page(error=None):
    """Render admin login page."""
    return render_template(
        'admin_login.html',
        service_name=CONFIG['SERVICE_NAME'],
        error=error
    )


@app.route('/auth')
def authenticate():
    """Guest authentication endpoint - sets cookie and redirects to main page."""
    token = request.args.get('token')
    
    if not token:
        return "No token provided", 401
    
    if not auth.validate_token(token):
        return "Invalid or expired token", 401
    
    # Set secure HttpOnly cookie
    response = redirect('/')
    response.set_cookie(
        'auth_token',
        token,
        httponly=True,
        secure=True,
        samesite='Strict',
        max_age=CONFIG['TOKEN_EXPIRY_HOURS'] * 3600
    )
    
    return response


@app.route('/admin')
@auth.require_admin()
def admin_dashboard():
    """Admin dashboard - manage guest tokens and QR codes."""
    return render_admin_dashboard()


@app.route('/admin/generate-token', methods=['POST'])
@auth.require_admin()
def admin_generate_token():
    """Generate a new guest token."""
    token = auth.generate_guest_token(read_only=not CONFIG['ENABLE_UPLOADS'])
    return redirect('/admin')


@app.route('/admin/revoke-token/<token_id>', methods=['POST'])
@auth.require_admin()
def admin_revoke_token(token_id):
    """Revoke a guest token."""
    auth.revoke_guest_token(token_id)
    return redirect('/admin')


def render_admin_dashboard():
    """Render the admin dashboard with active tokens."""
    active_tokens = auth.get_active_guest_tokens()
    server_url = get_server_url()
    
    # Generate QR codes for each token
    token_items = []
    for token_info in active_tokens:
        qr_gen = QRGenerator(server_url, token_info['token'])
        qr_image = qr_gen.generate_qr_base64()
        token_items.append({
            'id': token_info['id'],
            'qr_image': qr_image,
            'created': token_info['created'],
            'expires': token_info['expires'],
        })
    
    return render_template(
        'admin_dashboard.html',
        service_name=CONFIG['SERVICE_NAME'],
        token_items=token_items
    )


@app.route('/')
def index():
    """Main page - file browser for authenticated guests."""
    token = auth.get_token_from_request()
    
    if not token or not auth.validate_token(token):
        # No valid token, redirect to admin login
        return redirect('/admin/login')
    
    # Valid guest token, show file browser
    return render_file_browser()


def render_file_browser():
    """Render the file browser interface."""
    path = request.args.get('path', '')
    files = get_file_list(path)
    
    # Add formatted size to each file
    for file in files:
        file['size_formatted'] = format_size(file['size'])
    
    # Get parent path
    parent_path = os.path.dirname(path) if path else ''
    
    return render_template(
        'file_browser.html',
        service_name=CONFIG['SERVICE_NAME'],
        enable_uploads=CONFIG['ENABLE_UPLOADS'],
        current_path=path,
        parent_path=parent_path,
        files=files
    )


def format_size(size):
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


@app.route('/download/<path:filepath>')
@auth.require_auth('read')
def download_file(filepath):
    """Download a file with chunked streaming for mobile compatibility."""
    full_path = os.path.join(CONFIG['STORAGE_PATH'], filepath)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Use send_file with conditional response and chunked streaming
        # This enables range requests for mobile browsers and resumable downloads
        return send_file(
            full_path,
            as_attachment=True,
            conditional=True,  # Enable If-Modified-Since and range requests
            max_age=0,  # No caching for private files
            download_name=os.path.basename(filepath)  # Clean filename
        )
    except Exception as e:
        print(f"Error serving file {filepath}: {e}")
        return jsonify({'error': 'Error downloading file'}), 500


@app.route('/upload', methods=['POST'])
@auth.require_auth('write')
def upload_file():
    """Upload a file."""
    if not CONFIG['ENABLE_UPLOADS']:
        return jsonify({'error': 'Uploads disabled'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    path = request.form.get('path', '')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    full_path = os.path.join(CONFIG['STORAGE_PATH'], path, filename)
    
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    file.save(full_path)
    
    token = auth.get_token_from_request()
    return redirect(f'/?path={path}&token={token}')


@app.route('/qr')
def qr_code():
    """Generate QR code for current access."""
    token = request.args.get('token', '')
    if not token:
        token = auth.generate_guest_token()
    
    server_url = get_server_url()
    qr_gen = QRGenerator(server_url, token)
    qr_image = qr_gen.generate_qr_base64()
    
    return jsonify({
        'qr_image': qr_image,
        'access_url': qr_gen.generate_access_url(),
        'token': token
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'service': CONFIG['SERVICE_NAME']
    })


def main():
    """Main server entry point."""
    print("=" * 60)
    print(f"ThumbsUp API v2 - {CONFIG['SERVICE_NAME']}")
    print("=" * 60)
    
    # Check certificates
    if not os.path.exists(CONFIG['CERT_PATH']) or not os.path.exists(CONFIG['KEY_PATH']):
        print("ERROR: SSL certificates not found!")
        print("   Certificate path: " + CONFIG['CERT_PATH'])
        print("   Key path: " + CONFIG['KEY_PATH'])
        print("   Run: python utils/generate_certs.py")
        sys.exit(1)
    
    # Generate initial access token
    token = auth.generate_guest_token(read_only=not CONFIG['ENABLE_UPLOADS'])
    
    # Setup mDNS advertising
    mdns = MDNSAdvertiser(
        service_name=CONFIG['SERVICE_NAME'],
        port=CONFIG['PORT']
    )
    mdns.advertise()
    # Setup SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CONFIG['CERT_PATH'], CONFIG['KEY_PATH'])
    
    # Display access information
    server_url = get_server_url()
    qr_gen = QRGenerator(server_url, token)
    
    print()
    print("✅ Server started successfully!")
    print()
    print(f"📍 Server URL: {server_url}")
    print(f"🔑 Access Token: {token}")
    print()
    # Run server with mobile-friendly settings
    try:
        run_simple(
            CONFIG['HOST'],
            CONFIG['PORT'],
            app,
            ssl_context=ssl_context,
            use_reloader=False,
            use_debugger=False,
            threaded=True,  # Handle multiple requests concurrently
            request_handler=None,  # Use default handler with keep-alive support
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down server...")
        mdns.stop()
        print("✅ Server stopped")
        run_simple(
            CONFIG['HOST'],
            CONFIG['PORT'],
            app,
            ssl_context=ssl_context,
            use_reloader=False,
            use_debugger=False
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down server...")
        mdns.stop()
        print("✅ Server stopped")



if __name__ == "__main__":
    main()
