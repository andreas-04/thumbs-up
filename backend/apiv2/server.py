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
from flask import Flask, request, jsonify, send_file, render_template_string, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.serving import run_simple
import ssl

# Local imports
from auth import TokenAuth
from qr_generator import QRGenerator
from mdns_advertiser import MDNSAdvertiser


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
    'ADMIN_PIN': os.getenv('ADMIN_PIN', '123456'),  # Default PIN for development
}

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = CONFIG['MAX_UPLOAD_SIZE']
CORS(app)

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
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login - {CONFIG['SERVICE_NAME']}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                max-width: 400px;
                margin: 100px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
                text-align: center;
            }}
            .subtitle {{
                color: #666;
                margin-bottom: 30px;
                text-align: center;
            }}
            input[type="password"], input[type="text"] {{
                width: 100%;
                padding: 15px;
                margin: 10px 0;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 16px;
                box-sizing: border-box;
            }}
            input[type="password"]:focus, input[type="text"]:focus {{
                outline: none;
                border-color: #007bff;
            }}
            button {{
                width: 100%;
                padding: 15px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 10px;
            }}
            button:hover {{
                background: #0056b3;
            }}
            .error {{
                background: #fee;
                color: #c33;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Admin Login</h1>
            <p class="subtitle">{CONFIG['SERVICE_NAME']}</p>
            
            {'<div class="error">' + error + '</div>' if error else ''}
            
            <form method="post">
                <input type="password" name="pin" placeholder="Enter Admin PIN" required autofocus>
                <button type="submit">Login</button>
            </form>
        </div>
    </body>
    </html>
    """
    return html


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
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - {CONFIG['SERVICE_NAME']}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                max-width: 1200px;
                margin: 20px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .header {{
                background: white;
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            h1 {{
                color: #333;
                margin: 0;
            }}
            .btn {{
                padding: 12px 24px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }}
            .btn:hover {{
                background: #0056b3;
            }}
            .btn-danger {{
                background: #dc3545;
            }}
            .btn-danger:hover {{
                background: #c82333;
            }}
            .tokens-list {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .token-item {{
                border-bottom: 1px solid #eee;
            }}
            .token-item:last-child {{
                border-bottom: none;
            }}
            .token-header {{
                padding: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .token-header:hover {{
                background: #f9f9f9;
            }}
            .token-summary {{
                flex: 1;
            }}
            .token-summary h3 {{
                margin: 0 0 8px 0;
                color: #333;
            }}
            .token-meta {{
                font-size: 13px;
                color: #666;
            }}
            .expand-icon {{
                font-size: 20px;
                color: #666;
                transition: transform 0.3s;
            }}
            .token-item.expanded .expand-icon {{
                transform: rotate(180deg);
            }}
            .token-details {{
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease-out;
            }}
            .token-item.expanded .token-details {{
                max-height: 500px;
            }}
            .token-content {{
                padding: 20px;
                border-top: 1px solid #eee;
                background: #f9f9f9;
            }}
            .qr-container {{
                text-align: center;
                margin: 20px 0;
            }}
            .qr-code {{
                max-width: 250px;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                background: white;
            }}
            .revoke-btn {{
                width: 100%;
                margin-top: 15px;
            }}
            .empty-state {{
                background: white;
                border-radius: 12px;
                padding: 60px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .empty-state h2 {{
                color: #666;
                margin-bottom: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Thumbs Up Admin Dashboard</h1>
            <form method="post" action="/admin/generate-token">
                <button type="submit" class="btn">➕ Generate New Guest QR Code</button>
            </form>
        </div>
        
        {'<div class="tokens-list">' + ''.join([f'''
            <div class="token-item" id="token-{item['id']}">
                <div class="token-header" onclick="toggleToken('{item['id']}')">
                    <div class="token-summary">
                        <h3>Guest Access Token</h3>
                        <div class="token-meta">
                            Created: {item['created'][:19]} • Expires: {item['expires'][:19]}
                        </div>
                    </div>
                    <span class="expand-icon">▼</span>
                </div>
                <div class="token-details">
                    <div class="token-content">
                        <div class="qr-container">
                            <img src="{item['qr_image']}" class="qr-code" alt="QR Code">
                        </div>
                        <form method="post" action="/admin/revoke-token/{item['id']}">
                            <button type="submit" class="btn btn-danger revoke-btn">Revoke Access</button>
                        </form>
                    </div>
                </div>
            </div>
        ''' for item in token_items]) + '</div>' if token_items else '''
            <div class="empty-state">
                <h2>No Active Guest Tokens</h2>
                <p>Click "Generate New Guest QR Code" to create one</p>
            </div>
        '''}
        
        <script>
            function toggleToken(tokenId) {{
                const item = document.getElementById('token-' + tokenId);
                item.classList.toggle('expanded');
            }}
        </script>
    </body>
    </html>
    """
    
    return html


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
    
    # Build breadcrumb
    breadcrumb = []
    if path:
        parts = path.split('/')
        current = ''
        for part in parts:
            current = os.path.join(current, part) if current else part
            breadcrumb.append({'name': part, 'path': current})
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Files - {CONFIG['SERVICE_NAME']}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }}
            .header {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .header h1 {{
                margin: 0 0 10px 0;
                color: #333;
            }}
            .breadcrumb {{
                color: #666;
                font-size: 14px;
            }}
            .breadcrumb a {{
                color: #007bff;
                text-decoration: none;
            }}
            .breadcrumb a:hover {{
                text-decoration: underline;
            }}
            .upload-section {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .file-list {{
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .file-item {{
                padding: 15px 20px;
                border-bottom: 1px solid #eee;
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .file-item:hover {{
                background: #f9f9f9;
            }}
            .file-item:last-child {{
                border-bottom: none;
            }}
            .file-icon {{
                font-size: 24px;
                width: 30px;
                text-align: center;
            }}
            .file-info {{
                flex: 1;
            }}
            .file-name {{
                font-weight: 500;
                color: #333;
                text-decoration: none;
            }}
            .file-name:hover {{
                color: #007bff;
            }}
            .file-meta {{
                font-size: 12px;
                color: #999;
                margin-top: 4px;
            }}
            .file-actions {{
                display: flex;
                gap: 10px;
            }}
            .btn {{
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
            }}
            .btn-primary {{
                background: #007bff;
                color: white;
            }}
            .btn-primary:hover {{
                background: #0056b3;
            }}
            .btn-danger {{
                background: #dc3545;
                color: white;
            }}
            .btn-danger:hover {{
                background: #c82333;
            }}
            input[type="file"] {{
                padding: 10px;
                border: 2px dashed #ddd;
                border-radius: 4px;
                width: 100%;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📁 {CONFIG['SERVICE_NAME']}</h1>
        </div>
        
        {'<div class="upload-section"><h3>📤 Upload File</h3><form action="/upload" method="post" enctype="multipart/form-data"><input type="hidden" name="path" value="' + path + '"><input type="file" name="file" required><br><br><button type="submit" class="btn btn-primary">Upload</button></form></div>' if CONFIG['ENABLE_UPLOADS'] else ''}
        
        <div class="file-list">
            {'<div class="file-item"><div class="file-icon">📂</div><div class="file-info"><a href="/?path=' + os.path.dirname(path) + '" class="file-name">.. (Parent Directory)</a></div></div>' if path else ''}
            
            {''.join([f'''
            <div class="file-item">
                <div class="file-icon">{'📁' if f['is_dir'] else '📄'}</div>
                <div class="file-info">
                    <a href="{'/?path=' + f['path'] if f['is_dir'] else '/download/' + f['path']}" class="file-name">
                        {f['name']}
                    </a>
                    <div class="file-meta">
                        {format_size(f['size']) if not f['is_dir'] else 'Folder'} • Modified: {f['modified'][:19]}
                    </div>
                </div>
                <div class="file-actions">
                    {'<a href="/download/' + f['path'] + '" class="btn btn-primary" download>Download</a>' if not f['is_dir'] else ''}
                </div>
            </div>
            ''' for f in files]) if files else '<div class="file-item"><div class="file-info">No files found</div></div>'}
        </div>
    </body>
    </html>
    """
    
    return html


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
    print(f"🚀 ThumbsUp API v2 - {CONFIG['SERVICE_NAME']}")
    print("=" * 60)
    
    # Check certificates
    if not os.path.exists(CONFIG['CERT_PATH']) or not os.path.exists(CONFIG['KEY_PATH']):
        print("❌ SSL certificates not found!")
        print("   Run: python generate_certs.py")
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
