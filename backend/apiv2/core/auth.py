#!/usr/bin/env python3
"""
Token-based authentication system for ThumbsUp.
Generates and validates JWT tokens for secure access with database-backed user accounts.
"""

import jwt
import secrets
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from models import db, User

class TokenAuth:
    """Handle JWT token generation and validation with database-backed authentication."""
    
    def __init__(self, secret_key=None, token_expiry_hours=24, admin_pin=None):
        """
        Initialize token authentication.
        
        Args:
            secret_key: Secret key for JWT signing (random if None)
            token_expiry_hours: Token validity period in hours
            admin_pin: PIN for initial admin authentication (legacy support)
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.token_expiry_hours = token_expiry_hours
        self.algorithm = 'HS256'
        # Keep admin_pin for backward compatibility during transition
        self.admin_pin = admin_pin
        
        # In-memory storage for active guest tokens (will be deprecated)
        # Format: {token_id: {'token': str, 'created': datetime, 'expires': datetime}}
        self.active_guest_tokens = {}
    
    def hash_password(self, password):
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password string
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password, password_hash):
        """
        Verify password against hash.
        
        Args:
            password: Plain text password
            password_hash: Stored hash
        
        Returns:
            True if valid, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except:
            return False
    
    def authenticate_user(self, email, password):
        """
        Authenticate user with email and password.
        
        Args:
            email: User email
            password: User password
        
        Returns:
            User object if valid, None otherwise
        """
        user = User.query.filter_by(email=email).first()
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user
    
    def validate_admin_pin(self, pin):
        """
        Validate admin PIN (for first-time login only).
        
        Args:
            pin: PIN to validate
        
        Returns:
            User object if valid, None otherwise
        """
        if not self.admin_pin or not pin:
            return None
        
        # Only allow PIN login for admin with is_default_pin=True
        admin_user = User.query.filter_by(role='admin', is_default_pin=True).first()
        if not admin_user:
            return None
        
        # Verify PIN against admin's password hash
        if self.verify_password(pin, admin_user.password_hash):
            return admin_user
        
        return None
    
    def generate_session_token(self, user):
        """
        Generate session token for authenticated user.
        
        Args:
            user: User object
        
        Returns:
            JWT token string
        """
        expiry_hours = 2 if user.role == 'admin' else self.token_expiry_hours
        
        payload = {
            'user_id': user.id,
            'email': user.email,
            'role': user.role,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'jti': secrets.token_urlsafe(16)
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def generate_admin_session(self):
        """
        DEPRECATED: Use generate_session_token(user) instead.
        Generate ephemeral admin session token (not persisted).
        
        Returns:
            Session token string
        """
        payload = {
            'user_id': 'admin',
            'role': 'admin',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=2),  # Admin sessions expire after 2 hours
            'jti': secrets.token_urlsafe(16)
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def get_user_from_token(self, token):
        """
        Get user object from token.
        
        Args:
            token: JWT token string
        
        Returns:
            User object or None
        """
        payload = self.validate_token(token)
        if not payload:
            return None
        
        user_id = payload.get('user_id')
        if not user_id or user_id == 'admin' or user_id == 'guest':
            # Legacy token format
            return None
        
        user = User.query.get(user_id)
        return user
    
    def is_admin(self, token):
        """
        Check if token belongs to admin.
        
        Args:
            token: Token to check
        
        Returns:
            True if admin token, False otherwise
        """
        payload = self.validate_token(token)
        return payload and payload.get('role') == 'admin'
    
    def get_admin_token_from_request(self):
        """
        Extract admin token from request cookie.
        
        Returns:
            Token string or None
        """
        return request.cookies.get('admin_token')
    
    def get_token_from_request(self):
        """
        Extract token from request (Authorization header, cookie, or URL param).
        
        Returns:
            Token string or None
        """
        # Try Authorization header first (Bearer token)
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        
        # Fall back to cookies
        token = request.cookies.get('auth_token') or request.cookies.get('admin_token')
        if token:
            return token
        
        # Check URL parameter (legacy support)
        token = request.args.get('token')
        if token:
            return token
        
        return None
    
    def require_admin(self):
        """
        Decorator to require admin authentication for Flask routes.
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                token = self.get_token_from_request()
                
                if not token:
                    return jsonify({'error': 'Admin authentication required', 'code': 'ADMIN_AUTH_REQUIRED'}), 401
                
                user = self.get_user_from_token(token)
                if not user or user.role != 'admin':
                    return jsonify({'error': 'Admin access required', 'code': 'ADMIN_ACCESS_REQUIRED'}), 403
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator

    
    def generate_token(self, user_id='guest', permissions=None):
        """
        Generate a new access token.
        
        Args:
            user_id: User identifier
            permissions: List of permissions (read, write, delete)
        
        Returns:
            JWT token string
        """
        if permissions is None:
            permissions = ['read', 'write']
        
        payload = {
            'user_id': user_id,
            'permissions': permissions,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            'jti': secrets.token_urlsafe(16)  # Unique token ID
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def validate_token(self, token):
        """
        Validate and decode a token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def require_auth(self, permission=None):
        """
        Decorator to require authentication for Flask routes.
        
        Args:
            permission: Required permission (read, write, delete). None means any authenticated user.
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                token = self.get_token_from_request()
                
                if not token:
                    return jsonify({'error': 'No token provided', 'code': 'NO_TOKEN'}), 401
                
                # Try user-based auth first (new system with DB-backed users)
                user = self.get_user_from_token(token)
                if user:
                    # Authenticated DB user - attach info and allow
                    request.user = {
                        'user_id': user.id,
                        'email': user.email,
                        'role': user.role,
                    }
                    return f(*args, **kwargs)
                
                # Fall back to payload-based auth (legacy guest tokens)
                payload = self.validate_token(token)
                if not payload:
                    return jsonify({'error': 'Invalid or expired token', 'code': 'INVALID_TOKEN'}), 401
                
                # Check permissions for legacy tokens
                if permission:
                    permissions = payload.get('permissions', [])
                    role = payload.get('role')
                    
                    # New format: authenticated users have all permissions
                    if role in ('admin', 'user'):
                        pass
                    # Old format: check permissions array
                    elif permission not in permissions:
                        return jsonify({'error': 'Insufficient permissions'}), 403
                
                # Attach user info to request
                request.user = payload
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def generate_guest_token(self, read_only=False):
        """
        Generate a guest token and track it.
        
        Args:
            read_only: If True, only allow read permission
        
        Returns:
            JWT token string
        """
        permissions = ['read']
        if not read_only:
            permissions.append('write')
        
        token_id = secrets.token_urlsafe(16)
        created = datetime.utcnow()
        expires = created + timedelta(hours=self.token_expiry_hours)
        
        payload = {
            'user_id': 'guest',
            'permissions': permissions,
            'iat': created,
            'exp': expires,
            'jti': token_id
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Store in active tokens
        self.active_guest_tokens[token_id] = {
            'token': token,
            'created': created,
            'expires': expires
        }
        
        return token
    
    def get_active_guest_tokens(self):
        """
        Get all active guest tokens.
        
        Returns:
            List of token info dicts
        """
        # Clean up expired tokens
        now = datetime.utcnow()
        expired_ids = [tid for tid, info in self.active_guest_tokens.items() 
                      if info['expires'] < now]
        for tid in expired_ids:
            del self.active_guest_tokens[tid]
        
        # Return active tokens
        return [
            {
                'id': tid,
                'token': info['token'],
                'created': info['created'].isoformat(),
                'expires': info['expires'].isoformat(),
            }
            for tid, info in self.active_guest_tokens.items()
        ]
    
    def revoke_guest_token(self, token_id):
        """
        Revoke a guest token by ID.
        
        Args:
            token_id: Token ID to revoke
        
        Returns:
            True if revoked, False if not found
        """
        if token_id in self.active_guest_tokens:
            del self.active_guest_tokens[token_id]
            return True
        return False


# Example usage
if __name__ == "__main__":
    auth = TokenAuth()
    
    # Generate token
    token = auth.generate_guest_token()
    print(f"Generated token: {token}")
    
    # Validate token
    payload = auth.validate_token(token)
    print(f"Token payload: {payload}")
