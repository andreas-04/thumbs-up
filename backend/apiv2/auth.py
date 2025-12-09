#!/usr/bin/env python3
"""
Token-based authentication system for ThumbsUp.
Generates and validates JWT tokens for secure access.
"""

import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify


class TokenAuth:
    """Handle JWT token generation and validation."""
    
    def __init__(self, secret_key=None, token_expiry_hours=24, admin_pin=None):
        """
        Initialize token authentication.
        
        Args:
            secret_key: Secret key for JWT signing (random if None)
            token_expiry_hours: Token validity period in hours
            admin_pin: PIN for admin authentication
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.token_expiry_hours = token_expiry_hours
        self.algorithm = 'HS256'
        self.admin_pin_hash = self._hash_pin(admin_pin) if admin_pin else None
        
        # In-memory storage for active guest tokens
        # Format: {token_id: {'token': str, 'created': datetime, 'expires': datetime}}
        self.active_guest_tokens = {}
    
    def _hash_pin(self, pin):
        """Hash PIN using SHA256."""
        if not pin:
            return None
        return hashlib.sha256(pin.encode()).hexdigest()
    
    def validate_admin_pin(self, pin):
        """
        Validate admin PIN.
        
        Args:
            pin: PIN to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not self.admin_pin_hash or not pin:
            return False
        return self._hash_pin(pin) == self.admin_pin_hash
    
    def generate_admin_session(self):
        """
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
    
    def require_admin(self):
        """
        Decorator to require admin authentication for Flask routes.
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                token = self.get_admin_token_from_request()
                
                if not token:
                    return jsonify({'error': 'Admin authentication required'}), 401
                
                if not self.is_admin(token):
                    return jsonify({'error': 'Invalid admin session'}), 401
                
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
    
    def get_token_from_request(self):
        """
        Extract token from request (cookie or URL param for /auth endpoint).
        
        Returns:
            Token string or None
        """
        # Check cookie (primary method after authentication)
        token = request.cookies.get('auth_token')
        if token:
            return token
        
        # Check URL parameter (only for /auth endpoint)
        token = request.args.get('token')
        if token:
            return token
        
        return None
    
    def require_auth(self, permission=None):
        """
        Decorator to require authentication for Flask routes.
        
        Args:
            permission: Required permission (read, write, delete)
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                token = self.get_token_from_request()
                
                if not token:
                    return jsonify({'error': 'No token provided'}), 401
                
                payload = self.validate_token(token)
                
                if not payload:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                
                # Check permission if specified
                if permission and permission not in payload.get('permissions', []):
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
