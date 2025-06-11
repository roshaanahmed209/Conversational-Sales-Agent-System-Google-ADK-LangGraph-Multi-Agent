#!/usr/bin/env python3
"""
Minimal Sales Agent Application for Testing
"""

import os
import sys
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

# Set up basic configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_agent.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Simple Lead model
class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)
    age = db.Column(db.String(10), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    interest = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), default='started')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'lead_id': self.lead_id,
            'name': self.name,
            'age': self.age,
            'country': self.country,
            'interest': self.interest,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Simple agent response function
def simple_agent_response(message):
    """Simple chatbot responses for testing"""
    message = message.lower().strip()
    
    if any(word in message for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm your sales assistant. I'm here to help you find great products. What's your name?"
    
    elif any(word in message for word in ['name', 'called', "i'm", 'my name']):
        return "Nice to meet you! Could you also tell me your age?"
    
    elif any(word in message for word in ['age', 'old', 'years']):
        return "Great! And which country are you from?"
    
    elif any(word in message for word in ['country', 'from', 'live']):
        return "Perfect! What kind of products are you interested in? (Technology, Fashion, Home & Living, etc.)"
    
    elif any(word in message for word in ['product', 'interest', 'buy', 'looking']):
        return "Excellent! Based on your interests, I can recommend some great products. Would you like me to show you our catalog?"
    
    elif 'confirm' in message:
        return "Thank you for confirming! Your information has been saved. How else can I help you?"
    
    else:
        return "I understand! Could you tell me more about what you're looking for? I'm here to help you find the perfect products."

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    lead_id = str(uuid.uuid4())
    name = request.form.get('name', '')
    
    if name:
        # Create new lead
        lead = Lead(lead_id=lead_id, name=name)
        db.session.add(lead)
        db.session.commit()
        
        return redirect(url_for('conversation', lead_id=lead_id))
    
    return render_template('index.html', message="Please provide your name.")

@app.route('/conversation/<lead_id>')
def conversation(lead_id):
    # Get lead from database
    lead = Lead.query.filter_by(lead_id=lead_id).first()
    
    if not lead:
        return redirect(url_for('home'))
    
    welcome = f"Hello {lead.name}! I'm your sales assistant. Let's get started!"
    return render_template('conversation.html', lead_id=lead_id, response=welcome)

@app.route('/chat', methods=['POST'])
def chat():
    lead_id = request.args.get('lead_id')
    message = request.json.get('message', '')
    
    if not lead_id or not message:
        return jsonify({"error": "Missing lead_id or message"}), 400
    
    # Get simple agent response
    response = simple_agent_response(message)
    
    return jsonify({
        "response": response,
        "status": "ok"
    })

@app.route('/api/system/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "message": "Simple Sales Agent is running!",
        "timestamp": datetime.utcnow().isoformat()
    })

# Initialize database and run
if __name__ == '__main__':
    print("🚀 Starting Simple Sales Agent...")
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")
    
    print("🌐 Server starting at http://localhost:5000")
    print("="*50)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000) 