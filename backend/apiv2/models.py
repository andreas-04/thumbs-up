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
    
    def to_dict(self):
        """Convert user to dictionary (without password_hash)."""
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'is_default_pin': self.is_default_pin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
