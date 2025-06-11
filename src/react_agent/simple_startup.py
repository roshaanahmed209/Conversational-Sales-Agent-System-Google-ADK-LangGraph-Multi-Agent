#!/usr/bin/env python3
"""
Simple startup script for the sales agent without RAG initialization
"""

import os
import sys
import re
import csv
import uuid
from datetime import datetime

# Add paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Load environment variables
from dotenv import load_dotenv
load_dotenv('config.env')

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

print("🚀 Starting Simple Sales Agent (No RAG)...")

# --- Flask app setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'simple-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///simple_sales.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple conversation state
conversation_state = {}

# CSV setup
CSV_FILE = "simple_leads.csv"
CSV_COLUMNS = ["lead_id", "name", "age", "country", "interest", "status"]

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

def save_to_csv(lead_id, name, age, country, interest, status):
    """Save lead data to CSV"""
    try:
        with open(CSV_FILE, "a", newline="", encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow({
                "lead_id": lead_id,
                "name": str(name).strip() if name else "",
                "age": str(age).strip() if age else "",
                "country": str(country).strip() if country else "",
                "interest": str(interest).strip() if interest else "",
                "status": str(status).strip() if status else ""
            })
        print(f"✅ Saved to CSV: {name}, {age}, {country}, {interest}, {status}")
    except Exception as e:
        print(f"❌ CSV Error: {e}")

def extract_user_details_from_user_message(message, lead_id):
    """Extract user details directly from what the user says"""
    details = {}
    current_details = conversation_state.get(lead_id, {})
    message_lower = message.lower().strip()
    
    # Extract name if not already collected
    if not current_details.get('name'):
        name_patterns = [
            r'(?:my name is|i\'m|i am|call me|name\'s)\s+([a-zA-Z]+)',
            r'([a-zA-Z]+)\s+is my name',
            r'^([a-zA-Z]+)$'  # Single word response when asking for name
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message_lower)
            if match:
                name = match.group(1).strip().title()
                # Validate name
                invalid_names = ['hi', 'hello', 'hey', 'yes', 'no', 'ok', 'sure', 'good', 'great', 'fine']
                if (len(name) >= 2 and len(name) <= 15 and 
                    name.isalpha() and 
                    name.lower() not in invalid_names):
                    details['name'] = name
                    break
    
    # Extract age if not already collected
    elif not current_details.get('age'):
        age_patterns = [
            r'(?:i\'m|i am|my age is)\s*(\d+)',
            r'(\d+)\s*(?:years old|yo)',
            r'^(\d+)$'  # Just a number
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, message_lower)
            if match:
                age = match.group(1)
                if 13 <= int(age) <= 120:
                    details['age'] = age
                    break
    
    # Extract country if not already collected
    elif not current_details.get('country'):
        country_patterns = [
            r'(?:i\'m from|from|i live in|in)\s+([a-zA-Z\s]+)',
            r'^([a-zA-Z\s]+)$'  # Direct country name
        ]
        
        for pattern in country_patterns:
            match = re.search(pattern, message_lower)
            if match:
                country = match.group(1).strip().title()
                if len(country) > 2:
                    details['country'] = country
                    break
    
    # Extract product interest if not already collected
    elif not current_details.get('interest'):
        tech_keywords = ['technology', 'tech', 'smartphone', 'laptop', 'computer', 'phone', 'electronics']
        fashion_keywords = ['fashion', 'clothes', 'clothing', 'dress', 'shirt', 'shoes', 'accessories']
        home_keywords = ['home', 'furniture', 'decoration', 'living', 'kitchen', 'bedroom']
        
        if any(keyword in message_lower for keyword in tech_keywords):
            details['interest'] = 'Technology'
        elif any(keyword in message_lower for keyword in fashion_keywords):
            details['interest'] = 'Fashion'
        elif any(keyword in message_lower for keyword in home_keywords):
            details['interest'] = 'Home & Living'
    
    return details

def generate_structured_response(collected_details, user_message):
    """Generate a structured response based on collected details"""
    name = collected_details.get('name')
    age = collected_details.get('age')
    country = collected_details.get('country')
    interest = collected_details.get('interest')
    
    if name and not age:
        return f"Nice to meet you, {name}! To help me find the perfect products for you, could you tell me your age?"
    elif age and not country:
        return f"Thank you, {name}! So you're {age} years old. And which country are you from?"
    elif country and not interest:
        return f"Great! So you're {name}, {age} years old, from {country}. Now, what type of products are you most interested in?\n\n📱 Technology\n🏠 Home & Living\n👔 Fashion"
    elif all([name, age, country, interest]):
        return format_details_for_confirmation(collected_details)
    else:
        return "Thank you for sharing that information! Let me help you find what you're looking for."

def format_details_for_confirmation(details):
    """Format details for confirmation"""
    return (
        f"Great! Let's review the details you've provided:\n\n"
        f"Your name: {details.get('name', '[Not provided]')}\n"
        f"Age: {details.get('age', '[Not provided]')}\n"
        f"Country: {details.get('country', '[Not provided]')}\n"
        f"Product interest: {details.get('interest', '[Not provided]')}\n\n"
        f"Please confirm if the above details are correct by typing 'confirm'."
    )

def are_details_complete(details):
    """Check if all required details are present"""
    return all(details.get(key) for key in ['name', 'age', 'country', 'interest'])

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    lead_id = request.form.get('lead_id') or str(uuid.uuid4())
    name = request.form.get('name')
    
    if name:
        # Initialize conversation state
        conversation_state[lead_id] = {'name': name}
        save_to_csv(lead_id, name, '', '', '', 'started')
        return redirect(url_for('conversation', lead_id=lead_id))
    
    return render_template('index.html', message="Please provide valid details.")

@app.route('/conversation/<lead_id>', methods=['GET', 'POST'])
def conversation(lead_id):
    # Initialize state if not exists
    if lead_id not in conversation_state:
        conversation_state[lead_id] = {}
    
    if request.method == 'POST':
        message = request.form.get('message')
        current_details = conversation_state[lead_id]
        
        # Check for confirmation
        if message.lower().strip() == 'confirm':
            if are_details_complete(current_details):
                save_to_csv(
                    lead_id,
                    current_details['name'],
                    current_details['age'], 
                    current_details['country'],
                    current_details['interest'],
                    'confirmed'
                )
                
                agent_reply = f"Thank you for confirming your details, {current_details['name']}! "
                agent_reply += "Your information has been saved successfully. "
                agent_reply += f"Based on your interest in {current_details['interest']}, here are some recommendations:\n\n"
                
                if current_details['interest'] == 'Technology':
                    agent_reply += "📱 Samsung Galaxy S24 ($799.99)\n📱 iPhone 15 Pro ($999.99)\n💻 MacBook Pro M3 ($1,999.99)"
                elif current_details['interest'] == 'Fashion':
                    agent_reply += "👔 Men's Slim Fit Jeans ($49.99)\n👗 Designer Dress ($89.99)\n👟 Running Shoes ($79.99)"
                elif current_details['interest'] == 'Home & Living':
                    agent_reply += "🛏️ King Size Bed ($599.99)\n🪑 Office Chair ($199.99)\n🏠 Storage Solutions ($99.99)"
                else:
                    agent_reply += "I'll help you find the perfect products for your needs!"
                
                return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
        
        # Extract user details
        user_details = extract_user_details_from_user_message(message, lead_id)
        if user_details:
            # Update conversation state
            conversation_state[lead_id].update(user_details)
            current_details = conversation_state[lead_id]
            
            # Generate structured response
            agent_reply = generate_structured_response(current_details, message)
        else:
            # Simple conversation response
            agent_reply = f"I understand you said '{message}'. Let me help you with our products!"
        
        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
    
    # GET request - provide welcome message
    current_details = conversation_state[lead_id]
    name = current_details.get('name', '')
    
    if not current_details.get('age'):
        welcome = f"Hello {name}! Nice to meet you. To help you find the perfect products, may I ask your age?"
    elif not current_details.get('country'):
        welcome = f"Thanks {name}! And which country are you from?"
    elif not current_details.get('interest'):
        welcome = f"Great! Now {name}, what type of products are you interested in?"
    else:
        welcome = format_details_for_confirmation(current_details)
    
    return render_template('conversation.html', lead_id=lead_id, response=welcome)

@app.route('/chat', methods=['POST'])
def chat_api():
    """Simple chat API endpoint"""
    lead_id = request.args.get('lead_id')
    message = request.json.get('message')
    
    if not lead_id or not message:
        return jsonify({"error": "Missing lead_id or message"}), 400
    
    # Initialize state if not exists
    if lead_id not in conversation_state:
        conversation_state[lead_id] = {}
    
    current_details = conversation_state[lead_id]
    
    # Process message similar to conversation route
    if message.lower().strip() == 'confirm':
        if are_details_complete(current_details):
            agent_reply = f"Thank you for confirming, {current_details['name']}! Your details have been saved."
        else:
            agent_reply = "Please provide all required details first."
    else:
        user_details = extract_user_details_from_user_message(message, lead_id)
        if user_details:
            conversation_state[lead_id].update(user_details)
            current_details = conversation_state[lead_id]
            agent_reply = generate_structured_response(current_details, message)
        else:
            agent_reply = f"Thank you for your message: '{message}'. How can I help you today?"
    
    return jsonify({
        "response": agent_reply,
        "details_complete": are_details_complete(current_details),
        "collected_details": current_details
    })

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'message': 'Connected to simple sales agent'})

@socketio.on('send_message')
def handle_message(data):
    """Handle WebSocket messages"""
    lead_id = data.get('lead_id')
    message = data.get('message')
    
    if not lead_id or not message:
        emit('error', {'message': 'Missing lead_id or message'})
        return
    
    # Process the message
    if lead_id not in conversation_state:
        conversation_state[lead_id] = {}
    
    current_details = conversation_state[lead_id]
    user_details = extract_user_details_from_user_message(message, lead_id)
    
    if user_details:
        conversation_state[lead_id].update(user_details)
        current_details = conversation_state[lead_id]
        agent_reply = generate_structured_response(current_details, message)
    else:
        agent_reply = f"I received: '{message}'. This is a simple test response."
    
    # Emit response
    emit('message_update', {
        'lead_id': lead_id,
        'message': agent_reply,
        'role': 'assistant',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 SIMPLE SALES AGENT (NO RAG)")
    print("="*50)
    print(f"🌐 URL: http://localhost:5000")
    print(f"📊 CSV File: {CSV_FILE}")
    print("✅ Conversation flow working")
    print("❌ RAG system disabled")
    print("="*50 + "\n")
    
    try:
        socketio.run(app, debug=True, port=5000, host='0.0.0.0', use_reloader=False)
    except Exception as e:
        print(f"❌ Error: {e}")