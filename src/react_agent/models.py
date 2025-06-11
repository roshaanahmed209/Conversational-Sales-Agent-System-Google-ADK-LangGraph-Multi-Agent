from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import JSON
import json

db = SQLAlchemy()

class Lead(db.Model):
    """Lead model for storing customer information"""
    __tablename__ = 'leads'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    country = db.Column(db.String(100), nullable=True)
    interest = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='started')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='lead', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', backref='lead', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'name': self.name,
            'age': self.age,
            'country': self.country,
            'interest': self.interest,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Conversation(db.Model):
    """Conversation model for storing chat messages"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(100), db.ForeignKey('leads.lead_id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    message_metadata = db.Column(JSON, nullable=True)  # Additional message metadata
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'message_metadata': self.message_metadata,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class UserSession(db.Model):
    """User session model for state management"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    lead_id = db.Column(db.String(100), db.ForeignKey('leads.lead_id'), nullable=False)
    session_data = db.Column(JSON, nullable=True)  # Store session state
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'lead_id': self.lead_id,
            'session_data': self.session_data,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class FollowUpMessage(db.Model):
    """Follow-up messages model"""
    __tablename__ = 'follow_up_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(100), db.ForeignKey('leads.lead_id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_delivered = db.Column(db.Boolean, default=False)
    delivery_attempted_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'message': self.message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'is_delivered': self.is_delivered,
            'delivery_attempted_at': self.delivery_attempted_at.isoformat() if self.delivery_attempted_at else None
        }

class ProductRecommendation(db.Model):
    """Product recommendations model"""
    __tablename__ = 'product_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(100), db.ForeignKey('leads.lead_id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    price = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    recommendation_score = db.Column(db.Float, nullable=True)
    recommended_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'product_name': self.product_name,
            'category': self.category,
            'price': self.price,
            'description': self.description,
            'recommendation_score': self.recommendation_score,
            'recommended_at': self.recommended_at.isoformat() if self.recommended_at else None
        }

class SystemMetrics(db.Model):
    """System metrics for monitoring"""
    __tablename__ = 'system_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    metric_data = db.Column(JSON, nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'metric_data': self.metric_data,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        } 