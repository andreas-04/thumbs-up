"""
Database models for ThumbsUp authentication system.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User model for authentication and authorization."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')  # 'admin' or 'user'
    is_default_pin = db.Column(db.Boolean, default=False)  # True if using initial PIN
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
    
    def to_dict(self, include_permissions=False):
        """Convert user to dictionary (without password_hash)."""
        result = {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'requiresPasswordChange': self.is_default_pin,  # Frontend-friendly name
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        if include_permissions:
            result['folderPermissions'] = [p.to_dict() for p in self.folder_permissions]
        return result


class SystemSettings(db.Model):
    """System settings model for application configuration."""
    
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(50), nullable=False, default='open')  # 'open' or 'protected'
    auth_method = db.Column(db.String(50), nullable=False, default='email+password')  # 'email', 'email+password', 'username+password'
    tls_enabled = db.Column(db.Boolean, default=True)
    https_port = db.Column(db.Integer, default=8443)
    device_name = db.Column(db.String(255), default='ThumbsUp File Share')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemSettings mode={self.mode} auth={self.auth_method}>'
    
    def to_dict(self):
        """Convert settings to dictionary."""
        return {
            'id': self.id,
            'mode': self.mode,
            'authMethod': self.auth_method,
            'tlsEnabled': self.tls_enabled,
            'httpsPort': self.https_port,
            'deviceName': self.device_name,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class FolderPermission(db.Model):
    """Folder permissions model for user-level ACLs."""
    
    __tablename__ = 'folder_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    folder_path = db.Column(db.String(1024), nullable=False)
    can_read = db.Column(db.Boolean, default=True)
    can_write = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('folder_permissions', lazy=True, cascade='all, delete-orphan'))
    
    # Unique constraint: one permission entry per user per folder
    __table_args__ = (
        db.UniqueConstraint('user_id', 'folder_path', name='unique_user_folder'),
    )
    
    def __repr__(self):
        return f'<FolderPermission user_id={self.user_id} path={self.folder_path} r={self.can_read} w={self.can_write}>'
    
    def to_dict(self):
        """Convert permission to dictionary."""
        return {
            'id': self.id,
            'userId': self.user_id,
            'path': self.folder_path,
            'read': self.can_read,
            'write': self.can_write,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
