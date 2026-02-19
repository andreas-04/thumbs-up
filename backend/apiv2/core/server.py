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
from models import db, User


# Get the apiv2 directory (parent of core)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'

# Configuration
CONFIG = {
    'HOST': os.getenv('HOST', '0.0.0.0'),
    'PORT': int(os.getenv('PORT', 8443)),  # HTTPS port
    'STORAGE_PATH': os.getenv('STORAGE_PATH', str(BASE_DIR / 'storage')),  # Absolute path
    'CERT_PATH': os.getenv('CERT_PATH', str(BASE_DIR / 'certs' / 'server_cert.pem')),
    'KEY_PATH': os.getenv('KEY_PATH', str(BASE_DIR / 'certs' / 'server_key.pem')),
    'TOKEN_EXPIRY_HOURS': int(os.getenv('TOKEN_EXPIRY_HOURS', 24)),
    'ENABLE_UPLOADS': os.getenv('ENABLE_UPLOADS', 'true').lower() == 'true',
    'ENABLE_DELETE': os.getenv('ENABLE_DELETE', 'false').lower() == 'true',
    'SERVICE_NAME': os.getenv('SERVICE_NAME', 'ThumbsUp File Share'),
    'MAX_UPLOAD_SIZE': int(os.getenv('MAX_UPLOAD_SIZE', 100 * 1024 * 1024)),  # 100MB
    'ADMIN_PIN': os.getenv('ADMIN_PIN'),  # Must be set via environment
    'DATABASE_URI': os.getenv('DATABASE_URI', f'sqlite:///{BASE_DIR}/data/thumbsup.db'),
    'CORS_ORIGINS': os.getenv('CORS_ORIGINS', '*'),  # Comma-separated origins or '*'
}

# Initialize Flask app with explicit template folder
app = Flask(__name__, 
            template_folder=str(TEMPLATE_DIR),
            static_folder=str(STATIC_DIR) if STATIC_DIR.exists() else None)
app.config['MAX_CONTENT_LENGTH'] = CONFIG['MAX_UPLOAD_SIZE']
app.config['SQLALCHEMY_DATABASE_URI'] = CONFIG['DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure CORS
cors_origins = CONFIG['CORS_ORIGINS']
if cors_origins == '*':
    CORS(app)
else:
    origins = [origin.strip() for origin in cors_origins.split(',')]
    CORS(app, origins=origins)

# Initialize database
db.init_app(app)

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
            is_directory = os.path.isdir(item_path)
            
            items.append({
                'id': rel_path,  # Use path as unique ID
                'name': item,
                'path': rel_path,
                'type': 'folder' if is_directory else 'file',
                'size': stat.st_size if not is_directory else 0,
                'modifiedAt': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'parentPath': '/' + path if path else '/',
            })
        except (PermissionError, OSError, FileNotFoundError) as e:
            # Skip files we can't access
            print(f"Skipping {item}: {e}")
            continue
    
    # Sort: directories first, then files alphabetically
    items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    
    return items


# =============================================================================
# REST API v1 Endpoints
# =============================================================================

@app.route('/api/v1/auth/login', methods=['POST'])
def api_login():
    """Authenticate user and return JWT token."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({'error': 'Email and password required', 'code': 'MISSING_CREDENTIALS'}), 400
    
    # Authenticate user
    user = auth.authenticate_user(email, password)
    
    if not user:
        return jsonify({'error': 'Invalid credentials', 'code': 'INVALID_CREDENTIALS'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate JWT token
    token = auth.generate_session_token(user)
    
    return jsonify({
        'token': token,
        'user': user.to_dict()
    }), 200


@app.route('/api/v1/auth/signup', methods=['POST'])
def api_signup():
    """Register new user account."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    username = data.get('username', '').strip()
    
    # Validation
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required', 'code': 'INVALID_EMAIL'}), 400
    
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters', 'code': 'INVALID_PASSWORD'}), 400
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email already registered', 'code': 'EMAIL_EXISTS'}), 409
    
    # Create new user (no admin approval required in protected mode)
    new_user = User(
        email=email,
        password_hash=auth.hash_password(password),
        role='user',
        is_default_pin=False
    )
    db.session.add(new_user)
    db.session.commit()
    
    # Generate token for immediate login
    token = auth.generate_session_token(new_user)
    
    return jsonify({
        'token': token,
        'user': new_user.to_dict()
    }), 201


@app.route('/api/v1/auth/logout', methods=['POST'])
@auth.require_auth()
def api_logout():
    """Logout current user."""
    # JWT tokens are stateless, so we just return success
    # Frontend should delete the token
    return jsonify({'success': True}), 200


@app.route('/api/v1/auth/me', methods=['GET'])
@auth.require_auth()
def api_get_current_user():
    """Get current authenticated user info."""
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)
    
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    return jsonify({'user': user.to_dict(include_permissions=True)}), 200


@app.route('/api/v1/auth/refresh', methods=['POST'])
@auth.require_auth()
def api_refresh_token():
    """Refresh JWT token."""
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)
    
    if not user:
        return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401
    
    # Generate new token
    new_token = auth.generate_session_token(user)
    
    return jsonify({'token': new_token}), 200


@app.route('/api/v1/auth/change-password', methods=['POST'])
@auth.require_auth()
def api_change_password():
    """Change user password."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    current_password = data.get('currentPassword', '').strip()
    new_password = data.get('newPassword', '').strip()
    
    if not new_password or len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters', 'code': 'INVALID_PASSWORD'}), 400
    
    # Get current user
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)
    
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    # For first-time password change, allow skipping current password check
    if not user.is_default_pin:
        if not current_password:
            return jsonify({'error': 'Current password required', 'code': 'MISSING_CURRENT_PASSWORD'}), 400
        
        # Verify current password
        if not auth.verify_password(current_password, user.password_hash):
            return jsonify({'error': 'Current password is incorrect', 'code': 'INVALID_CURRENT_PASSWORD'}), 401
    
    # Update password
    user.password_hash = auth.hash_password(new_password)
    user.is_default_pin = False  # Clear the flag
    db.session.commit()
    
    # Generate new token
    new_token = auth.generate_session_token(user)
    
    return jsonify({
        'token': new_token,
        'user': user.to_dict()
    }), 200


@app.route('/api/v1/settings', methods=['GET'])
def api_get_settings():
    """Get system settings (public endpoint)."""
    from models import SystemSettings
    
    settings = SystemSettings.query.first()
    if not settings:
        return jsonify({'error': 'Settings not found', 'code': 'SETTINGS_NOT_FOUND'}), 404
    
    return jsonify(settings.to_dict()), 200


@app.route('/api/v1/settings', methods=['PUT'])
@auth.require_admin()
def api_update_settings():
    """Update system settings (admin only)."""
    from models import SystemSettings
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    settings = SystemSettings.query.first()
    if not settings:
        return jsonify({'error': 'Settings not found', 'code': 'SETTINGS_NOT_FOUND'}), 404
    
    # Update allowed fields
    if 'mode' in data:
        if data['mode'] not in ['open', 'protected']:
            return jsonify({'error': 'Invalid mode value', 'code': 'INVALID_MODE'}), 400
        settings.mode = data['mode']
    
    if 'authMethod' in data:
        if data['authMethod'] not in ['email', 'email+password', 'username+password']:
            return jsonify({'error': 'Invalid authMethod value', 'code': 'INVALID_AUTH_METHOD'}), 400
        settings.auth_method = data['authMethod']
    
    if 'tlsEnabled' in data:
        settings.tls_enabled = bool(data['tlsEnabled'])
    
    if 'httpsPort' in data:
        port = int(data['httpsPort'])
        if port < 1 or port > 65535:
            return jsonify({'error': 'Invalid port number', 'code': 'INVALID_PORT'}), 400
        settings.https_port = port
    
    if 'deviceName' in data:
        settings.device_name = data['deviceName'].strip()
    
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(settings.to_dict()), 200


@app.route('/api/v1/users', methods=['GET'])
@auth.require_admin()
def api_list_users():
    """List all users with optional search and pagination (admin only)."""
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    
    query = User.query
    
    if search:
        query = query.filter(User.email.ilike(f'%{search}%'))
    
    # Paginate
    total = query.count()
    users = query.offset((page - 1) * limit).limit(limit).all()
    
    return jsonify({
        'users': [user.to_dict() for user in users],
        'total': total,
        'page': page,
        'limit': limit
    }), 200


@app.route('/api/v1/users', methods=['POST'])
@auth.require_admin()
def api_create_user():
    """Create new user (admin only)."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user').strip()
    
    # Validation
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required', 'code': 'INVALID_EMAIL'}), 400
    
    if role not in ['admin', 'user']:
        return jsonify({'error': 'Invalid role', 'code': 'INVALID_ROLE'}), 400
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email already exists', 'code': 'EMAIL_EXISTS'}), 409
    
    # Create user
    new_user = User(
        email=email,
        password_hash=auth.hash_password(password) if password else auth.hash_password('changeme'),
        role=role,
        is_default_pin=False
    )
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'user': new_user.to_dict()}), 201


@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
@auth.require_admin()
def api_get_user(user_id):
    """Get user by ID (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    return jsonify({'user': user.to_dict(include_permissions=True)}), 200


@app.route('/api/v1/users/<int:user_id>', methods=['PUT'])
@auth.require_admin()
def api_update_user(user_id):
    """Update user (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    # Update allowed fields
    if 'email' in data:
        email = data['email'].strip()
        if not email or '@' not in email:
            return jsonify({'error': 'Valid email required', 'code': 'INVALID_EMAIL'}), 400
        
        # Check if email is taken by another user
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user_id:
            return jsonify({'error': 'Email already exists', 'code': 'EMAIL_EXISTS'}), 409
        
        user.email = email
    
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters', 'code': 'INVALID_PASSWORD'}), 400
        user.password_hash = auth.hash_password(data['password'])
    
    if 'role' in data:
        if data['role'] not in ['admin', 'user']:
            return jsonify({'error': 'Invalid role', 'code': 'INVALID_ROLE'}), 400
        user.role = data['role']
    
    db.session.commit()
    
    return jsonify({'user': user.to_dict()}), 200


@app.route('/api/v1/users/<int:user_id>', methods=['DELETE'])
@auth.require_admin()
def api_delete_user(user_id):
    """Delete user (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    # Prevent deleting yourself
    token = auth.get_token_from_request()
    current_user = auth.get_user_from_token(token)
    if current_user and current_user.id == user_id:
        return jsonify({'error': 'Cannot delete yourself', 'code': 'CANNOT_DELETE_SELF'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True}), 200


@app.route('/api/v1/users/<int:user_id>/permissions', methods=['GET'])
@auth.require_admin()
def api_get_user_permissions(user_id):
    """Get user folder permissions (admin only)."""
    from models import FolderPermission
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    permissions = FolderPermission.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'permissions': [p.to_dict() for p in permissions]
    }), 200


@app.route('/api/v1/users/<int:user_id>/permissions', methods=['PUT'])
@auth.require_admin()
def api_update_user_permissions(user_id):
    """Update user folder permissions (admin only)."""
    from models import FolderPermission
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 404
    
    data = request.get_json()
    if not data or 'permissions' not in data:
        return jsonify({'error': 'Permissions array required', 'code': 'MISSING_PERMISSIONS'}), 400
    
    # Delete existing permissions
    FolderPermission.query.filter_by(user_id=user_id).delete()
    
    # Add new permissions
    for perm_data in data['permissions']:
        permission = FolderPermission(
            user_id=user_id,
            folder_path=perm_data.get('path', '/'),
            can_read=perm_data.get('read', True),
            can_write=perm_data.get('write', False)
        )
        db.session.add(permission)
    
    db.session.commit()
    
    # Return updated permissions
    permissions = FolderPermission.query.filter_by(user_id=user_id).all()
    return jsonify({
        'permissions': [p.to_dict() for p in permissions]
    }), 200


@app.route('/api/v1/folders', methods=['GET'])
@auth.require_admin()
def api_list_folders():
    """List all folders in storage for permission management (admin only)."""
    storage_path = Path(CONFIG['STORAGE_PATH'])
    folders = [{'path': '/', 'name': 'Root'}]
    
    try:
        for item in storage_path.rglob('*'):
            if item.is_dir():
                rel_path = '/' + str(item.relative_to(storage_path))
                folders.append({
                    'path': rel_path,
                    'name': item.name
                })
    except Exception as e:
        return jsonify({'error': str(e), 'code': 'FOLDER_SCAN_ERROR'}), 500
    
    return jsonify({'folders': folders}), 200


@app.route('/api/v1/files', methods=['GET'])
def api_list_files():
    """List files in directory (respects permissions in protected mode)."""
    from models import SystemSettings, FolderPermission
    
    path = request.args.get('path', '')
    search = request.args.get('search', '').strip()
    
    # Check system mode and permissions
    settings = SystemSettings.query.first()
    if settings and settings.mode == 'protected':
        # Require authentication in protected mode
        token = auth.get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
        
        user = auth.get_user_from_token(token)
        if not user:
            return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401
        
        # Check folder permissions (admin has full access)
        if user.role != 'admin':
            permission = FolderPermission.query.filter_by(
                user_id=user.id,
                folder_path='/' + path if path else '/'
            ).first()
            
            if not permission or not permission.can_read:
                return jsonify({'error': 'Access denied', 'code': 'ACCESS_DENIED'}), 403
    
    # Get file list
    try:
        files = get_file_list(path)
        
        # Filter by search if provided
        if search:
            files = [f for f in files if search.lower() in f['name'].lower()]
        
        # Format response
        return jsonify({
            'files': files,
            'currentPath': '/' + path if path else '/',
            'parentPath': '/' + str(Path(path).parent) if path and path != '.' else None
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'code': 'FILE_LIST_ERROR'}), 500


@app.route('/api/v1/files/upload', methods=['POST'])
def api_upload_file():
    """Upload file (respects permissions in protected mode)."""
    from models import SystemSettings, FolderPermission
    
    if not CONFIG['ENABLE_UPLOADS']:
        return jsonify({'error': 'Uploads are disabled', 'code': 'UPLOADS_DISABLED'}), 403
    
    # Check system mode and permissions
    settings = SystemSettings.query.first()
    path = request.form.get('path', '')
    
    if settings and settings.mode == 'protected':
        token = auth.get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
        
        user = auth.get_user_from_token(token)
        if not user:
            return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401
        
        # Check write permissions (admin has full access)
        if user.role != 'admin':
            permission = FolderPermission.query.filter_by(
                user_id=user.id,
                folder_path='/' + path if path else '/'
            ).first()
            
            if not permission or not permission.can_write:
                return jsonify({'error': 'Write access denied', 'code': 'WRITE_ACCESS_DENIED'}), 403
    
    # Handle upload
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided', 'code': 'NO_FILE'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected', 'code': 'NO_FILE'}), 400
    
    # Secure filename and save
    filename = secure_filename(file.filename)
    target_dir = Path(CONFIG['STORAGE_PATH']) / path
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    
    file.save(str(target_path))
    
    # Return file info
    stat = target_path.stat()
    return jsonify({
        'file': {
            'name': filename,
            'path': str(Path(path) / filename) if path else filename,
            'size': stat.st_size,
            'modifiedAt': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    }), 201


@app.route('/api/v1/files/download', methods=['GET'])
def api_download_file():
    """Download file (respects permissions in protected mode)."""
    from models import SystemSettings, FolderPermission
    
    path = request.args.get('path', '')
    if not path:
        return jsonify({'error': 'Path required', 'code': 'MISSING_PATH'}), 400
    
    # Check system mode and permissions
    settings = SystemSettings.query.first()
    
    if settings and settings.mode == 'protected':
        token = auth.get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
        
        user = auth.get_user_from_token(token)
        if not user:
            return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401
        
        # Check read permissions
        if user.role != 'admin':
            folder_path = '/' + str(Path(path).parent)
            permission = FolderPermission.query.filter_by(
                user_id=user.id,
                folder_path=folder_path
            ).first()
            
            if not permission or not permission.can_read:
                return jsonify({'error': 'Read access denied', 'code': 'READ_ACCESS_DENIED'}), 403
    
    # Serve file
    file_path = Path(CONFIG['STORAGE_PATH']) / path
    
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found', 'code': 'FILE_NOT_FOUND'}), 404
    
    return send_file(str(file_path), as_attachment=True)


@app.route('/api/v1/files/mkdir', methods=['POST'])
@auth.require_auth()
def api_create_directory():
    """Create directory (respects permissions in protected mode)."""
    from models import SystemSettings, FolderPermission
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required', 'code': 'MISSING_BODY'}), 400
    
    path = data.get('path', '')
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Directory name required', 'code': 'MISSING_NAME'}), 400
    
    # Check permissions
    settings = SystemSettings.query.first()
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)
    
    if settings and settings.mode == 'protected' and user.role != 'admin':
        permission = FolderPermission.query.filter_by(
            user_id=user.id,
            folder_path='/' + path if path else '/'
        ).first()
        
        if not permission or not permission.can_write:
            return jsonify({'error': 'Write access denied', 'code': 'WRITE_ACCESS_DENIED'}), 403
    
    # Create directory
    target_dir = Path(CONFIG['STORAGE_PATH']) / path / secure_filename(name)
    
    try:
        target_dir.mkdir(parents=True, exist_ok=False)
        return jsonify({
            'folder': {
                'name': name,
                'path': str(Path(path) / name) if path else name
            }
        }), 201
    except FileExistsError:
        return jsonify({'error': 'Directory already exists', 'code': 'DIR_EXISTS'}), 409
    except Exception as e:
        return jsonify({'error': str(e), 'code': 'CREATE_DIR_ERROR'}), 500


@app.route('/api/v1/files', methods=['DELETE'])
@auth.require_auth()
def api_delete_file():
    """Delete file or directory (respects permissions in protected mode)."""
    from models import SystemSettings, FolderPermission
    
    if not CONFIG['ENABLE_DELETE']:
        return jsonify({'error': 'Delete is disabled', 'code': 'DELETE_DISABLED'}), 403
    
    path = request.args.get('path', '')
    if not path:
        return jsonify({'error': 'Path required', 'code': 'MISSING_PATH'}), 400
    
    # Check permissions
    settings = SystemSettings.query.first()
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)
    
    if settings and settings.mode == 'protected' and user.role != 'admin':
        folder_path = '/' + str(Path(path).parent)
        permission = FolderPermission.query.filter_by(
            user_id=user.id,
            folder_path=folder_path
        ).first()
        
        if not permission or not permission.can_write:
            return jsonify({'error': 'Write access denied', 'code': 'WRITE_ACCESS_DENIED'}), 403
    
    # Delete file/directory
    target_path = Path(CONFIG['STORAGE_PATH']) / path
    
    if not target_path.exists():
        return jsonify({'error': 'File not found', 'code': 'FILE_NOT_FOUND'}), 404
    
    try:
        if target_path.is_dir():
            import shutil
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'code': 'DELETE_ERROR'}), 500


@app.route('/api/v1/stats/dashboard', methods=['GET'])
@auth.require_admin()
def api_get_dashboard_stats():
    """Get dashboard statistics (admin only)."""
    from models import SystemSettings
    
    # Count users
    user_count = User.query.filter_by(role='user').count()
    
    # Count files and folders
    storage_path = Path(CONFIG['STORAGE_PATH'])
    file_count = 0
    folder_count = 0
    total_size = 0
    
    try:
        for item in storage_path.rglob('*'):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
            elif item.is_dir():
                folder_count += 1
    except Exception:
        pass
    
    # Get system settings
    settings = SystemSettings.query.first()
    
    return jsonify({
        'userCount': user_count,
        'fileCount': file_count,
        'folderCount': folder_count,
        'totalSize': total_size,
        'mode': settings.mode if settings else 'open',
        'tlsEnabled': settings.tls_enabled if settings else True
    }), 200


# =============================================================================
# Legacy HTML Endpoints (for backward compatibility)
# =============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login - supports PIN (first-time) or email/password."""
    if request.method == 'POST':
        pin = request.form.get('pin')
        email = request.form.get('email')
        password = request.form.get('password')
        
        admin_user = None
        
        # Try PIN authentication (for first-time login with is_default_pin=True)
        if pin:
            admin_user = auth.validate_admin_pin(pin)
            if admin_user:
                # PIN is valid - generate session and check if first-time setup needed
                admin_token = auth.generate_session_token(admin_user)
                
                if admin_user.is_default_pin:
                    # First-time login - redirect to setup
                    response = redirect('/admin/first-setup')
                else:
                    # Normal login
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
        
        # Try email/password authentication
        if email and password:
            admin_user = auth.authenticate_user(email, password)
            if admin_user and admin_user.role == 'admin':
                # Generate session token
                admin_token = auth.generate_session_token(admin_user)
                
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
        
        # Invalid credentials
        return render_admin_login_page(error="Invalid credentials")
    
    # GET request - show login form
    return render_admin_login_page()


def render_admin_login_page(error=None):
    """Render admin login page."""
    return render_template(
        'admin_login.html',
        service_name=CONFIG['SERVICE_NAME'],
        error=error
    )


@app.route('/admin/first-setup', methods=['GET', 'POST'])
@auth.require_admin()
def admin_first_setup():
    """First-time setup for admin - set email and new password."""
    # Get user from token
    token = auth.get_admin_token_from_request()
    admin_user = auth.get_user_from_token(token)
    
    if not admin_user or not admin_user.is_default_pin:
        # Already set up or invalid token
        return redirect('/admin')
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        errors = []
        if not email or '@' not in email:
            errors.append("Valid email is required")
        if not password:
            errors.append("Password is required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters")
        
        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != admin_user.id:
            errors.append("Email already in use")
        
        if errors:
            return render_template(
                'first_setup.html',
                service_name=CONFIG['SERVICE_NAME'],
                errors=errors,
                email=email
            )
        
        # Update admin user
        admin_user.email = email
        admin_user.password_hash = auth.hash_password(password)
        admin_user.is_default_pin = False
        db.session.commit()
        
        return redirect('/admin')
    
    # GET request - show setup form
    return render_template(
        'first_setup.html',
        service_name=CONFIG['SERVICE_NAME']
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        errors = []
        if not email or '@' not in email:
            errors.append("Valid email is required")
        if not password:
            errors.append("Password is required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters")
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            errors.append("Email already registered")
        
        if errors:
            return render_template(
                'register.html',
                service_name=CONFIG['SERVICE_NAME'],
                errors=errors,
                email=email
            )
        
        # Create new user
        new_user = User(
            email=email,
            password_hash=auth.hash_password(password),
            role='user',
            is_default_pin=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Auto-login after registration
        user_token = auth.generate_session_token(new_user)
        response = redirect('/')
        response.set_cookie(
            'auth_token',
            user_token,
            httponly=True,
            secure=True,
            samesite='Strict',
            max_age=CONFIG['TOKEN_EXPIRY_HOURS'] * 3600
        )
        return response
    
    # GET request - show registration form
    return render_template(
        'register.html',
        service_name=CONFIG['SERVICE_NAME']
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        # Authenticate
        user = auth.authenticate_user(email, password)
        
        if not user:
            return render_template(
                'login.html',
                service_name=CONFIG['SERVICE_NAME'],
                error="Invalid email or password",
                email=email
            )
        
        # Don't allow admin to login via regular login page
        if user.role == 'admin':
            return render_template(
                'login.html',
                service_name=CONFIG['SERVICE_NAME'],
                error="Admin users must use /admin/login",
                email=email
            )
        
        # Generate session token
        user_token = auth.generate_session_token(user)
        response = redirect('/')
        response.set_cookie(
            'auth_token',
            user_token,
            httponly=True,
            secure=True,
            samesite='Strict',
            max_age=CONFIG['TOKEN_EXPIRY_HOURS'] * 3600
        )
        return response
    
    # GET request - show login form
    return render_template(
        'login.html',
        service_name=CONFIG['SERVICE_NAME']
    )


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout user."""
    response = redirect('/login')
    response.set_cookie('auth_token', '', expires=0)
    response.set_cookie('admin_token', '', expires=0)
    return response


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
    """Admin dashboard - user management and settings."""
    # TODO: Create new admin dashboard for user management
    # For now, show simple welcome message
    token = auth.get_admin_token_from_request()
    admin_user = auth.get_user_from_token(token)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - {CONFIG['SERVICE_NAME']}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #333; }}
            .info {{ margin: 20px 0; color: #666; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👨‍💼 Admin Dashboard</h1>
            <p class="info">Welcome, {admin_user.email if admin_user else 'Admin'}!</p>
            <p class="info">
                <a href="/">Browse Files</a> | 
                <a href="/logout">Logout</a>
            </p>
            <p class="info" style="margin-top: 40px; color: #999;">
                TODO: User management features coming soon
            </p>
        </div>
    </body>
    </html>
    """


# TODO: Refactor token management for user-specific tokens
# @app.route('/admin/generate-token', methods=['POST'])
# @auth.require_admin()
# def admin_generate_token():
#     """Generate a new guest token."""
#     token = auth.generate_guest_token(read_only=not CONFIG['ENABLE_UPLOADS'])
#     return redirect('/admin')


# @app.route('/admin/revoke-token/<token_id>', methods=['POST'])
# @auth.require_admin()
# def admin_revoke_token(token_id):
#     """Revoke a guest token."""
#     auth.revoke_guest_token(token_id)
#     return redirect('/admin')


# def render_admin_dashboard():
#     """Render the admin dashboard with active tokens."""
# def render_admin_dashboard():
#     """Render the admin dashboard with active tokens."""
#     active_tokens = auth.get_active_guest_tokens()
#     server_url = get_server_url()
#     
#     # Generate QR codes for each token
#     token_items = []
#     for token_info in active_tokens:
#         qr_gen = QRGenerator(server_url, token_info['token'])
#         qr_image = qr_gen.generate_qr_base64()
#         token_items.append({
#             'id': token_info['id'],
#             'qr_image': qr_image,
#             'created': token_info['created'],
#             'expires': token_info['expires'],
#         })
#     
#     return render_template(
#         'admin_dashboard.html',
#         service_name=CONFIG['SERVICE_NAME'],
#         token_items=token_items
#     )


@app.route('/')
def index():
    """Main page - file browser for authenticated users."""
    token = auth.get_token_from_request()
    
    if not token or not auth.validate_token(token):
        # No valid token, redirect to login
        return redirect('/login')
    
    # Valid token, show file browser (accessible to all authenticated users)
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


# TODO: Refactor QR code generation for user-specific tokens
# @app.route('/qr')
# def qr_code():
#     """Generate QR code for current access."""
#     token = request.args.get('token', '')
#     if not token:
#         token = auth.generate_guest_token()
#     
#     server_url = get_server_url()
#     qr_gen = QRGenerator(server_url, token)
#     qr_image = qr_gen.generate_qr_base64()
#     
#     return jsonify({
#         'qr_image': qr_image,
#         'access_url': qr_gen.generate_access_url(),
#         'token': token
#     })


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
    
    # Ensure database directory exists
    db_path = Path(CONFIG['DATABASE_URI'].replace('sqlite:///', ''))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize database tables
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")
        
        # Create default system settings if not exists
        from models import SystemSettings
        if not SystemSettings.query.first():
            default_settings = SystemSettings(
                mode='open',
                auth_method='email+password',
                tls_enabled=True,
                https_port=CONFIG['PORT'],
                device_name=CONFIG['SERVICE_NAME']
            )
            db.session.add(default_settings)
            db.session.commit()
            print("✅ Default system settings created")
        
        # Create default admin user if no admin exists
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            # Use ADMIN_PIN as temporary password for default admin
            default_admin = User(
                email='admin@thumbsup.local',
                password_hash=auth.hash_password(CONFIG['ADMIN_PIN']),
                role='admin',
                is_default_pin=True  # Flag to force password change on first login
            )
            db.session.add(default_admin)
            db.session.commit()
            print("✅ Default admin user created (admin@thumbsup.local)")
            print(f"   Password: {CONFIG['ADMIN_PIN']} (must be changed on first login)")
    
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
