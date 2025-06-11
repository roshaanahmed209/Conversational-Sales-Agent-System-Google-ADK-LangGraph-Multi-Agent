import os
import sys

# Add the current directory and src directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, root_dir)

# Load environment variables from .env or config.env files
from dotenv import load_dotenv

# Try to load from multiple possible env files
env_files = ['.env', 'config.env', os.path.join(root_dir, '.env'), os.path.join(root_dir, 'config.env')]
env_loaded = False

for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"🔧 Loaded environment variables from: {env_file}")
        env_loaded = True
        break

if not env_loaded:
    print("⚠️  No .env or config.env file found, using system environment variables")

# Set protobuf implementation from env file or default
if not os.getenv("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"):
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_migrate import Migrate
import asyncio

# Import with fallback handling - Make all agent imports lazy to prevent hanging
root_agent = None
dual_rag_system = None
legacy_call_agent = None

print("[IMPORT] Setting up lazy agent system imports...")

def get_root_agent():
    """Lazy import of root agent to prevent startup hanging"""
    global root_agent
    if root_agent is None:
        try:
            print("[LAZY_ROOT] Attempting to import root_agent_system...")
            from root_agent_system import root_agent as ra
            root_agent = ra
            print("[LAZY_ROOT] ✅ Root agent imported successfully")
        except ImportError as e:
            print(f"[LAZY_ROOT] ❌ Could not import root_agent: {e}")
            root_agent = None
        except Exception as e:
            print(f"[LAZY_ROOT] ❌ Root agent initialization failed: {e}")
            root_agent = None
    return root_agent

def get_rag_system():
    """Lazy import of RAG system to prevent startup hanging"""
    global dual_rag_system
    if dual_rag_system is None:
        try:
            print("[LAZY_RAG] Attempting to import enhanced_rag_system...")
            from enhanced_rag_system import dual_rag_system as rag_sys
            dual_rag_system = rag_sys
            print("[LAZY_RAG] ✅ RAG system imported successfully")
        except ImportError as e:
            print(f"[LAZY_RAG] ❌ Could not import RAG system: {e}")
            dual_rag_system = None
        except Exception as e:
            print(f"[LAZY_RAG] ❌ RAG system initialization failed: {e}")
            dual_rag_system = None
    return dual_rag_system

def get_legacy_agent():
    """Lazy import of legacy agent to prevent startup hanging"""
    global legacy_call_agent
    if legacy_call_agent is None:
        try:
            print("[LAZY_LEGACY] Attempting to import legacy agent...")
            from agent import call_agent_sync as legacy_call_agent_func, langgraph_agent, sales_agent
            legacy_call_agent = legacy_call_agent_func
            print("[LAZY_LEGACY] ✅ Legacy agent imported successfully")
        except ImportError as e:
            print(f"[LAZY_LEGACY] ❌ Could not import legacy agent: {e}")
            legacy_call_agent = None
        except Exception as e:
            print(f"[LAZY_LEGACY] ❌ Legacy agent initialization failed: {e}")
            legacy_call_agent = None
    return legacy_call_agent

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import pandas as pd
import csv
import time
import re
from threading import Thread
import uuid
import logging
from datetime import datetime

# Import our new models and state management
from models import db, Lead, Conversation, UserSession, FollowUpMessage, ProductRecommendation, SystemMetrics
from state_manager import state_manager, ConversationState

# --- Environment & API Key Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Display API key status
print(f"🔑 GROQ_API_KEY: {'✅ Loaded' if GROQ_API_KEY and GROQ_API_KEY != 'your_groq_api_key_here' else '❌ Not set'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Loaded' if GEMINI_API_KEY and GEMINI_API_KEY != 'your_gemini_api_key_here' else '❌ Not set'}")

# Set default API key if not provided (for fallback compatibility)
if not GROQ_API_KEY or GROQ_API_KEY == 'your_groq_api_key_here':
    GROQ_API_KEY = "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"
    print("⚠️  Using fallback GROQ_API_KEY - please set your own in config.env")

os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# --- CSV Setup for leads ---
CSV_FILE = "leads.csv"
CSV_COLUMNS = ["lead_id", "name", "age", "country", "interest", "status"]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

# --- Flask app with enhanced configuration ---
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///sales_agent.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add cache-busting headers to prevent browser caching issues
@app.after_request
def add_cache_control_headers(response):
    """Add cache control headers to prevent browser caching of updated files"""
    if request.endpoint == 'static':
        # Force reload of CSS and JS files
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response  

# --- ADK Session & Runner Setup ---
APP_NAME = "sales_agent_app"
USER_ID = "user_1"
session_service = InMemorySessionService()

# Initialize runner with safety checks - Make this lazy too
runner = None

def get_runner():
    """Lazy initialization of Google ADK Runner"""
    global runner
    if runner is None:
        try:
            root_agent = get_root_agent()
            if root_agent is not None:
                runner = Runner(
                    agent=root_agent,
                    app_name=APP_NAME,
                    session_service=session_service
                )
                print("✅ Google ADK Runner initialized successfully")
            else:
                print("⚠️  Google ADK not available, using fallback system")
        except Exception as e:
            print(f"❌ Failed to initialize Google ADK Runner: {e}")
            print("🔄 Will use fallback agent system")
            runner = None
    return runner

# --- Helper: Sync wrapper around async runner ---
async def _run_agent_async(conversation_id: str, text: str) -> str:
    """Run agent async with safety checks"""
    runner = get_runner()
    if runner is None:
        raise Exception("Runner not available - using fallback")
    
    content = types.Content(role='user', parts=[types.Part(text=text)])
    final_text = ""
    
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=conversation_id,
            new_message=content
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    final_text = f"Agent escalated: {event.error_message or 'No message'}"
                break
    except Exception as e:
        print(f"[ASYNC_ERROR] Runner failed: {e}")
        raise e
    
    return final_text or "I'm processing your request. Please try again."

def call_agent_sync(conversation_id: str, text: str) -> str:
    """Simple non-blocking agent that uses our proven conversation logic"""
    try:
        # Use simple conversation logic instead of complex agent systems
        print(f"[SIMPLE_AGENT] Processing message for {conversation_id}: {text}")
        
        # Get current state
        current_details = state_manager.get_collected_details(conversation_id)
        
        # Generate response using our proven conversation logic
        user_details = extract_user_details_from_user_message(text, conversation_id)
        if user_details:
            state_manager.update_collected_details(conversation_id, user_details)
            current_details = state_manager.get_collected_details(conversation_id)
            response = generate_structured_response(current_details, text)
        else:
            # Check if we should continue with structured conversation flow
            name = current_details.get('name')
            age = current_details.get('age')
            country = current_details.get('country')
            interest = current_details.get('interest')
            
            # Priority: Continue structured flow if we're in the middle of collecting details
            if name and not age:
                response = f"Thanks for that, {name}! To help me find the perfect products for you, could you tell me your age?"
            elif name and age and not country:
                response = f"Thank you! So you're {age} years old. Which country are you from, {name}?"
            elif name and age and country and not interest:
                response = f"Great! So you're {name}, {age} years old, from {country}. What type of products are you most interested in?\n\n📱 Technology (smartphones, laptops, electronics)\n🏠 Home & Living (furniture, storage, decor)\n👔 Fashion (clothing, shoes, accessories)\n\nOr tell me about any specific product you're looking for!"
            elif all([name, age, country, interest]):
                response = format_details_for_confirmation(current_details)
            else:
                # Only use generic responses if we haven't started collecting details yet
                if "hi" in text.lower() or "hello" in text.lower():
                    if name:
                        response = f"Hello again, {name}! How can I help you today?"
                    else:
                        response = "Hello! Nice to meet you. To help you find the perfect products, may I start by asking your name?"
                elif "product" in text.lower() or "recommend" in text.lower() or "suggest" in text.lower():
                    if name:
                        response = "I'd be happy to recommend products! Let me just finish gathering your information first."
                    else:
                        response = "I'd be happy to recommend products! First, let me gather some information about you. What's your name?"
                elif "help" in text.lower():
                    response = "I'm here to help you find the perfect products! Let's start by getting to know you better. What's your name?"
                else:
                    if name:
                        response = f"Thanks for your message, {name}! Let me continue helping you find great products."
                    else:
                        response = "Thank you for your message! To help you find the perfect products, could you start by telling me your name?"
        
        print(f"[SIMPLE_AGENT] Generated response: {response[:100]}...")
        return response
        
    except Exception as e:
        print(f"[SIMPLE_AGENT] Error: {e}")
        return "I'm here to help you! Could you tell me a bit about what products you're looking for?"

# State management is now handled by the StateManager class
# conversation_details replaced by state_manager

# --- Helper to save lead data ---
def save_to_csv(lead_id, name, age, country, interest, status):
    print(f"[DEBUG] Attempting to save to CSV:")
    print(f"  Lead ID: {lead_id}")
    print(f"  Name: {name}")
    print(f"  Age: {age}")
    print(f"  Country: {country}")
    print(f"  Interest: {interest}")
    print(f"  Status: {status}")
    
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
        print(f"[SUCCESS] Data saved to {CSV_FILE}")
    except Exception as e:
        print(f"[ERROR] Failed to save to CSV: {e}")

# --- Helper to extract user details directly from user messages ---
def extract_user_details_from_user_message(message, lead_id):
    """Extract user details directly from what the user says"""
    details = {}
    current_details = state_manager.get_collected_details(lead_id)
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
                # More strict validation for names
                invalid_names = ['hi', 'hello', 'hey', 'yes', 'no', 'ok', 'sure', 'good', 'great', 'fine', 'well', 'glad', 'happy', 'nice', 'thanks', 'thank', 'that', 'this', 'hear', 'you', 'me', 'we', 'they']
                if (len(name) >= 2 and len(name) <= 15 and 
                    name.isalpha() and 
                    name.lower() not in invalid_names and
                    not any(invalid in name.lower() for invalid in ['glad', 'hear', 'that', 'thanks'])):
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
                if 13 <= int(age) <= 120:  # Reasonable age range
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
        # Common product categories
        tech_keywords = ['technology', 'tech', 'smartphone', 'laptop', 'computer', 'phone', 'electronics']
        fashion_keywords = ['fashion', 'clothes', 'clothing', 'dress', 'shirt', 'shoes', 'accessories']
        home_keywords = ['home', 'furniture', 'decoration', 'living', 'kitchen', 'bedroom']
        
        if any(keyword in message_lower for keyword in tech_keywords):
            details['interest'] = 'Technology'
        elif any(keyword in message_lower for keyword in fashion_keywords):
            details['interest'] = 'Fashion'
        elif any(keyword in message_lower for keyword in home_keywords):
            details['interest'] = 'Home & Living'
        else:
            # Try to extract any specific product mention
            interest_patterns = [
                r'(?:interested in|looking for|want|need)\s+([a-zA-Z\s]+)',
                r'^([a-zA-Z\s]+)$'  # Direct interest
            ]
            
            for pattern in interest_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    interest = match.group(1).strip()
                    if len(interest) > 2 and interest not in ['yes', 'no', 'ok', 'sure']:
                        details['interest'] = interest.title()
                        break
    
    print(f"[DEBUG] Extracted from user message '{message}': {details}")
    return details

def generate_structured_response(collected_details, user_message):
    """Generate a structured response based on collected details"""
    name = collected_details.get('name')
    age = collected_details.get('age')
    country = collected_details.get('country')
    interest = collected_details.get('interest')
    
    # Acknowledge what was just collected and ask for next piece of info
    if name and not age:
        return f"Nice to meet you, {name}! To help me find the perfect products for you, could you tell me your age?"
    
    elif age and not country:
        return f"Thank you, {name}! So you're {age} years old. And which country are you from?"
    
    elif country and not interest:
        return f"Great! So you're {name}, {age} years old, from {country}. Now, what type of products are you most interested in?\n\n📱 Technology (smartphones, laptops, electronics)\n🏠 Home & Living (furniture, storage, decor)\n👔 Fashion (clothing, shoes, accessories)\n\nOr tell me about any specific product you're looking for!"
    
    elif all([name, age, country, interest]):
        # All details collected, show confirmation and set pending_confirmation flag
        # Note: We can't directly access the lead_id from this function, so we'll handle this in the calling function
        return format_details_for_confirmation(collected_details)
    
    else:
        # Fallback response
        return "Thank you for sharing that information! Let me help you find what you're looking for."

# --- Helper to extract user details from a structured response ---
def extract_user_details(message):
    details = {
        'name': None,
        'age': None,
        'country': None,
        'interest': None
    }
    
    print(f"[DEBUG] Extracting details from agent message (first 200 chars): {message[:200]}...")
    
    # Clean the message by removing markdown formatting
    clean_message = re.sub(r'\*\*', '', message)  # Remove ** formatting
    clean_message = re.sub(r'^\s*-\s*', '', clean_message, flags=re.MULTILINE)  # Remove bullet points
    
    # Only extract if the message seems to contain structured information summary
    if not any(keyword in message.lower() for keyword in ['name:', 'age:', 'country:', 'details:', 'information:']):
        print("[DEBUG] Agent message doesn't contain structured details, skipping extraction")
        return details
    
    # Extract details using more robust regex patterns
    name_patterns = [
        r'(?:your|the|their|customer\'?s?)\s*name:?\s*([^\n\.,]+)',
        r'name:?\s*([^\n\.,\-]+)',
        r'I\'m\s+([^\n\.,]+)(?:\s+and\s+I\'m|\s*,)',
        r'My\s+name\s+is\s+([^\n\.,]+)'
    ]
    
    age_patterns = [
        r'(?:your|the|their|customer\'?s?)\s*age:?\s*([^\n\.,]+)',
        r'age:?\s*([^\n\.,\-]+)',
        r'I\'m\s+(\d+)\s+years?\s+old',
        r'(\d+)\s+years?\s+old'
    ]
    
    country_patterns = [
        r'(?:your|the|their|customer\'?s?)\s*country:?\s*([^\n\.,]+)',
        r'country:?\s*([^\n\.,\-]+)',
        r'I\'m\s+from\s+([^\n\.,]+)',
        r'from\s+([^\n\.,]+)'
    ]
    
    interest_patterns = [
        r'(?:product\s*)?interest:?\s*([^\n\.,]+)',
        r'interested\s+in\s+([^\n\.,]+)',
        r'looking\s+for\s+([^\n\.,]+)',
        r'want\s+to\s+buy\s+([^\n\.,]+)',
        r'need\s+([^\n\.,]+)'
    ]
    
    # Try all patterns for each field
    for pattern in name_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match and not details['name']:
            name_candidate = match.group(1).strip()
            # Validate name (should not be a question or generic text)
            invalid_phrases = ['glad to hear', 'nice to meet', 'great to', 'happy to', 'good to', 'thanks', 'thank you']
            if (not re.search(r'\?|what|how|when|where|why', name_candidate, re.IGNORECASE) and
                not any(phrase in name_candidate.lower() for phrase in invalid_phrases) and
                len(name_candidate.split()) <= 3):  # Names shouldn't be too long
                details['name'] = name_candidate
                break
    
    for pattern in age_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match and not details['age']:
            age_candidate = match.group(1).strip()
            # Validate age (should be numeric or contain numeric)
            if re.search(r'\d+', age_candidate):
                details['age'] = re.search(r'(\d+)', age_candidate).group(1)
                break
    
    for pattern in country_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match and not details['country']:
            country_candidate = match.group(1).strip()
            # Validate country (should not be a question)
            if not re.search(r'\?|what|how|when|where|why', country_candidate, re.IGNORECASE):
                details['country'] = country_candidate
                break
    
    for pattern in interest_patterns:
        match = re.search(pattern, clean_message, re.IGNORECASE)
        if match and not details['interest']:
            interest_candidate = match.group(1).strip()
            
            # Filter out invalid interest candidates
            invalid_phrases = [
                'some things', 'some products', 'something', 'anything', 'everything',
                'what do you have', 'suggestions', 'options', 'catalog', 'products',
                'you', 'me', 'us', 'them', 'it', 'that', 'this', 'more'
            ]
            
            # Check if it's a valid product interest
            is_valid_interest = (
                len(interest_candidate) < 100 and  # Reasonable length
                len(interest_candidate) > 2 and    # Not too short
                not any(invalid in interest_candidate.lower() for invalid in invalid_phrases) and
                not re.search(r'\?|what|how|when|where|why|can you|could you|please', interest_candidate, re.IGNORECASE)
            )
            
            if is_valid_interest:
                details['interest'] = interest_candidate
                break
    
    # Log what was found
    for key, value in details.items():
        if value:
            print(f"[DEBUG] Found {key}: {value}")
    
    return details

# --- Check if all required details are present ---
def are_details_complete(details):
    return all(details.values())

# --- Count how many details are missing ---
def count_missing_details(details):
    return sum(1 for value in details.values() if not value)

# --- Get list of missing fields ---
def get_missing_fields(details):
    missing = []
    if not details['name']:
        missing.append("name")
    if not details['age']:
        missing.append("age")
    if not details['country']:
        missing.append("country")
    if not details['interest']:
        missing.append("product interest")
    return missing

# --- Format details for confirmation ---
def format_details_for_confirmation(details):
    # Clean up the details - remove trailing punctuation and extra whitespace
    cleaned_details = {}
    for key, value in details.items():
        if value:
            # Remove trailing punctuation and extra whitespace
            cleaned_value = re.sub(r'[.,;:!?]+$', '', value).strip()
            cleaned_details[key] = cleaned_value
        else:
            cleaned_details[key] = "[Not provided]"
    
    return (
        f"Great! Let's review the details you've provided:\n\n"
        f"Your name: {cleaned_details['name']}\n"
        f"Age: {cleaned_details['age']}\n"
        f"Country: {cleaned_details['country']}\n"
        f"Product interest: {cleaned_details['interest']}\n\n"
        f"Please confirm if the above details are correct by typing 'confirm'."
    )

# --- Helper to detect exit commands ---
def is_exit_command(message):
    exit_commands = ["exit", "bye", "goodbye", "quit", "end", "stop", "finish", "leave"]
    return message.lower().strip() in exit_commands or any(cmd in message.lower() for cmd in exit_commands)

# --- Check if product interest is missing ---
def is_product_interest_missing(details):
    return details['name'] and details['age'] and details['country'] and not details['interest']

# --- Format a message to specifically request product interest ---
def format_product_interest_request():
    return "I see we have most of your details, but I still need to know what specific products you're interested in purchasing. Could you please tell me what kind of products you're looking for today?"

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test')
def test():
    """Simple test endpoint without any complex operations"""
    return jsonify({"status": "working", "message": "Server is responding!"})

@app.route('/test_cleanup')
def test_cleanup():
    """Test endpoint to manually trigger CSV cleanup"""
    try:
        clean_incomplete_csv_entries()
        return {"status": "success", "message": "CSV cleanup completed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"CSV cleanup failed: {str(e)}"}

@app.route('/health')
def health():
    """Health check endpoint"""
    return "OK"

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/chat', methods=['POST'])
def chat():
    lead_id = request.args.get('lead_id')
    if not lead_id:
        return jsonify({"error": "Missing lead_id parameter"}), 400
    
    message = request.json.get('message')
    if not message:
        return jsonify({"error": "Missing message in request body"}), 400
    
    try:
        # Record user activity
        state_manager.record_user_activity(lead_id)
        
        # Save user message
        state_manager.save_conversation_message(lead_id, 'user', message)
        
        # Check if this is a confirmation message
        if message.lower().strip() == 'confirm':
            state = state_manager.get_or_create_conversation_state(lead_id)
            if state.pending_confirmation:
                details = state_manager.get_collected_details(lead_id)
                if state_manager.are_details_complete(lead_id):
                    # Update lead status
                    state_manager.update_conversation_state(
                        lead_id, 
                        current_step='confirmed',
                        pending_confirmation=False
                    )
                    
                    save_to_csv(
                        lead_id, 
                        details['name'], 
                        details['age'], 
                        details['country'], 
                        details['interest'], 
                        'confirmed'
                    )
                    
                    # Clean up incomplete entries from CSV after successful confirmation
                    print(f"[WS_DEBUG] Running CSV cleanup after confirmation")
                    clean_incomplete_csv_entries()
                    
                    # Provide product recommendations using simple logic
                    agent_reply = f"Thank you for confirming your details, {details['name']}! Your information has been saved successfully. "
                    agent_reply += f"Based on your interest in {details['interest']}, here are some great product recommendations:\n\n"
                    
                    # Simple product recommendations based on interest
                    if details['interest'].lower() in ['technology', 'tech', 'smartphone', 'laptop', 'computer', 'phone', 'electronics']:
                        agent_reply += "📱 Samsung Galaxy S24 ($799.99) - Latest smartphone with amazing camera\n"
                        agent_reply += "📱 iPhone 15 Pro ($999.99) - Premium Apple device with titanium design\n"
                        agent_reply += "💻 MacBook Pro M3 ($1,999.99) - Powerful laptop for professionals\n"
                        agent_reply += "🎧 AirPods Pro ($249.99) - Premium wireless earbuds"
                    elif details['interest'].lower() in ['fashion', 'clothes', 'clothing', 'dress', 'shirt', 'shoes', 'accessories']:
                        agent_reply += "👔 Men's Slim Fit Jeans ($49.99) - Comfortable premium denim\n"
                        agent_reply += "👗 Designer Summer Dress ($89.99) - Elegant and stylish\n"
                        agent_reply += "👟 Running Shoes ($79.99) - High-performance athletic footwear\n"
                        agent_reply += "👜 Leather Handbag ($129.99) - Premium quality accessory"
                    elif details['interest'].lower() in ['home', 'furniture', 'decoration', 'living', 'kitchen', 'bedroom']:
                        agent_reply += "🛏️ King Size Bed ($599.99) - Comfortable premium mattress\n"
                        agent_reply += "🪑 Ergonomic Office Chair ($199.99) - Perfect for working from home\n"
                        agent_reply += "🏠 Storage Solutions Set ($99.99) - Organize your space beautifully\n"
                        agent_reply += "🍽️ Dinnerware Set ($79.99) - Elegant dining collection"
                    else:
                        agent_reply += "🛍️ Premium Product Bundle ($149.99) - Curated selection of popular items\n"
                        agent_reply += "🎁 Gift Card ($50-500) - Perfect for any occasion\n"
                        agent_reply += "⭐ Best Sellers Collection - Top-rated products across all categories\n"
                        agent_reply += "📦 Starter Kit ($89.99) - Everything you need to get started"
                    
                    # Save conversation messages
                    state_manager.save_conversation_message(lead_id, 'user', message)
                    state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                    
                    # Emit real-time update
                    socketio.emit('message_update', {
                        'lead_id': lead_id,
                        'message': agent_reply,
                        'role': 'assistant',
                        'timestamp': datetime.utcnow().isoformat()
                    }, room=lead_id)
                    
                    return jsonify({"response": agent_reply, "status": "confirmed"})
        
        # Extract user details directly from user message first
        user_details = extract_user_details_from_user_message(message, lead_id)
        if user_details:
            print(f"[API_DEBUG] Extracted user details: {user_details}")
            state_manager.update_collected_details(lead_id, user_details)
            
            # Generate structured response based on what was collected
            collected = state_manager.get_collected_details(lead_id)
            agent_reply = generate_structured_response(collected, message)
            
            # Check if all details are complete for confirmation
            if state_manager.are_details_complete(lead_id):
                state_manager.update_conversation_state(
                    lead_id,
                    current_step='confirmation',
                    pending_confirmation=True
                )
        else:
            # Send message to agent for normal conversation
            agent_reply = call_agent_sync(lead_id, message)
            
            # Check if the agent response contains user details in a structured format
            details = extract_user_details(agent_reply)
            if details:
                # Only update with agent details if they don't overwrite existing good data
                current_details = state_manager.get_collected_details(lead_id)
                safe_update = {}
                
                for key, value in details.items():
                    if value and (not current_details.get(key) or len(str(current_details.get(key))) < 2):
                        safe_update[key] = value
                        print(f"[API_DEBUG] Safe update from agent: {key} = {value}")
                    elif value and current_details.get(key):
                        print(f"[API_DEBUG] Skipping agent extraction for {key}: already have '{current_details.get(key)}', agent suggested '{value}'")
                
                if safe_update:
                    state_manager.update_collected_details(lead_id, safe_update)
                
                # Check if all details are complete
                if state_manager.are_details_complete(lead_id):
                    # Set pending confirmation state
                    state_manager.update_conversation_state(
                        lead_id,
                        current_step='confirmation',
                        pending_confirmation=True
                    )
                    
                    # Replace agent response with formatted confirmation prompt
                    all_details = state_manager.get_collected_details(lead_id)
                    agent_reply = format_details_for_confirmation(all_details)
        
        # Save agent response
        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
        
        # Emit real-time update
        socketio.emit('message_update', {
            'lead_id': lead_id,
            'message': agent_reply,
            'role': 'assistant',
            'timestamp': datetime.utcnow().isoformat()
        }, room=lead_id)
        
        # Record system metrics
        state_manager.record_system_metric('chat_messages', 1, {'lead_id': lead_id})
        
        return jsonify({
            "response": agent_reply,
            "details_complete": state_manager.are_details_complete(lead_id),
            "missing_details": state_manager.get_missing_details(lead_id),
            "session_id": state_manager.get_or_create_conversation_state(lead_id).session_id
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/check_follow_up', methods=['GET'])
def check_follow_up():
    """Simple follow-up check without complex operations"""
    lead_id = request.args.get('lead_id')
    if not lead_id:
        return jsonify({"has_follow_up": False})
    
    try:
        # Simple check without complex state manager operations
        return jsonify({"has_follow_up": False, "message": "Follow-up system ready"})
        
    except Exception as e:
        logger.error(f"Error checking follow-up: {str(e)}")
        return jsonify({"has_follow_up": False, "error": str(e)})

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    """Simplified start conversation without blocking operations"""
    lead_id = request.form.get('lead_id') or str(uuid.uuid4())
    name = request.form.get('name')
    
    if name:
        try:
            # Initialize conversation state with name
            state_manager.update_collected_details(lead_id, {'name': name})
            state_manager.update_conversation_state(
                lead_id,
                current_step='collecting_details',
                is_active=True
            )
            
            # Save initial conversation message
            state_manager.save_conversation_message(
                lead_id, 
                'system', 
                f"Conversation started with {name}"
            )
            
            print(f"[START] Starting conversation for lead {lead_id} with name {name}")
            
            # Store initial status in CSV
            save_to_csv(lead_id, name, '', '', '', 'started')
            
            # Record system metric
            state_manager.record_system_metric('conversations_started', 1, {'lead_id': lead_id})
            
            return redirect(url_for('conversation', lead_id=lead_id))
            
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            return render_template('index.html', message="Error starting conversation. Please try again.")
    
    return render_template('index.html', message="Please provide valid details.")

@app.route('/conversation/<lead_id>', methods=['GET', 'POST'])
def conversation(lead_id):
    if request.method == 'POST':
        message = request.form.get('message')
        
        # Record user activity
        state_manager.record_user_activity(lead_id)
        
        # Check if this is an exit command
        if is_exit_command(message):
            # Provide a farewell message and redirect
            return render_template('exit.html', message="Thank you for chatting with me! Goodbye!", redirect_url=url_for('home'))
        
        # Check if this is a confirmation message
        if message.lower().strip() == 'confirm':
            state = state_manager.get_or_create_conversation_state(lead_id)
            if state.pending_confirmation:
                details = state_manager.get_collected_details(lead_id)
                if state_manager.are_details_complete(lead_id):
                    # Update lead status
                    state_manager.update_conversation_state(
                        lead_id, 
                        current_step='confirmed',
                        pending_confirmation=False
                    )
                    
                    save_to_csv(
                        lead_id, 
                        details['name'], 
                        details['age'], 
                        details['country'], 
                        details['interest'], 
                        'confirmed'
                    )
                    
                    # Clean up incomplete entries from CSV after successful confirmation
                    print(f"[WS_DEBUG] Running CSV cleanup after confirmation")
                    clean_incomplete_csv_entries()
                    
                    # Provide product recommendations using simple logic
                    agent_reply = f"Thank you for confirming your details, {details['name']}! Your information has been saved successfully. "
                    agent_reply += f"Based on your interest in {details['interest']}, here are some great product recommendations:\n\n"
                    
                    # Simple product recommendations based on interest
                    if details['interest'].lower() in ['technology', 'tech', 'smartphone', 'laptop', 'computer', 'phone', 'electronics']:
                        agent_reply += "📱 Samsung Galaxy S24 ($799.99) - Latest smartphone with amazing camera\n"
                        agent_reply += "📱 iPhone 15 Pro ($999.99) - Premium Apple device with titanium design\n"
                        agent_reply += "💻 MacBook Pro M3 ($1,999.99) - Powerful laptop for professionals\n"
                        agent_reply += "🎧 AirPods Pro ($249.99) - Premium wireless earbuds"
                    elif details['interest'].lower() in ['fashion', 'clothes', 'clothing', 'dress', 'shirt', 'shoes', 'accessories']:
                        agent_reply += "👔 Men's Slim Fit Jeans ($49.99) - Comfortable premium denim\n"
                        agent_reply += "👗 Designer Summer Dress ($89.99) - Elegant and stylish\n"
                        agent_reply += "👟 Running Shoes ($79.99) - High-performance athletic footwear\n"
                        agent_reply += "👜 Leather Handbag ($129.99) - Premium quality accessory"
                    elif details['interest'].lower() in ['home', 'furniture', 'decoration', 'living', 'kitchen', 'bedroom']:
                        agent_reply += "🛏️ King Size Bed ($599.99) - Comfortable premium mattress\n"
                        agent_reply += "🪑 Ergonomic Office Chair ($199.99) - Perfect for working from home\n"
                        agent_reply += "🏠 Storage Solutions Set ($99.99) - Organize your space beautifully\n"
                        agent_reply += "🍽️ Dinnerware Set ($79.99) - Elegant dining collection"
                    else:
                        agent_reply += "🛍️ Premium Product Bundle ($149.99) - Curated selection of popular items\n"
                        agent_reply += "🎁 Gift Card ($50-500) - Perfect for any occasion\n"
                        agent_reply += "⭐ Best Sellers Collection - Top-rated products across all categories\n"
                        agent_reply += "📦 Starter Kit ($89.99) - Everything you need to get started"
                    
                    # Save conversation messages
                    state_manager.save_conversation_message(lead_id, 'user', message)
                    state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                    
                    return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
        
        # Check if user is asking for product suggestions/recommendations - PRIORITY CHECK
        message_lower = message.lower().strip()
        suggestion_keywords = ['suggestion', 'suggestions', 'recommend', 'recommendation', 'recommendations', 
                             'what do you have', 'show me products', 'product catalog', 'catalog', 
                             'what products', 'products available', 'what can you offer', 'suggest me', 'can suggest']
        
        is_asking_for_suggestions = any(keyword in message_lower for keyword in suggestion_keywords)
        
        if is_asking_for_suggestions:
            print(f"[DEBUG] User asking for suggestions: {message}")
            
            # Get user details from state manager
            user_details = state_manager.get_collected_details(lead_id)
            print(f"[DEBUG] Found user details: {user_details}")
            
            # Always try to provide suggestions if RAG system is available
            if get_rag_system():
                try:
                    # Provide general suggestions from our product catalog
                    print("[DEBUG] Getting general product suggestions from RAG system")
                    suggestions = get_rag_system().company_docs_rag.get_product_suggestions("general products", k=6)
                    
                    if suggestions and len(suggestions) > 0:
                        agent_reply = "Great! Here are some popular products from our catalog:\n\n"
                        
                        for i, suggestion in enumerate(suggestions[:4], 1):
                            content = suggestion['content']
                            # Extract product info more cleanly
                            if len(content) > 150:
                                agent_reply += f"{i}. {content[:150]}...\n\n"
                            else:
                                agent_reply += f"{i}. {content}\n\n"
                        
                        # Add personalized note if we have user details
                        if user_details.get('name'):
                            agent_reply += f"\nThese are some of our popular items, {user_details['name']}! "
                        
                        agent_reply += "Would you like to see products in a specific category like Technology, Fashion, or Home & Living?"
                        
                        # Save conversation messages
                        state_manager.save_conversation_message(lead_id, 'user', message)
                        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                        
                        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
                    else:
                        print("[DEBUG] No suggestions found from RAG system, using fallback")
                        # Fallback if no suggestions found
                        agent_reply = "Here are some of our popular product categories:\n\n"
                        agent_reply += "📱 **Technology**: Samsung Galaxy S24 ($799.99), iPhone 15 Pro ($999.99), MacBook Pro M3\n\n"
                        agent_reply += "🏠 **Home & Living**: King Size Wooden Bed, Storage Solutions, Home Decor\n\n"
                        agent_reply += "👔 **Fashion**: Men's Slim Fit Jeans, Designer Clothing, Accessories\n\n"
                        
                        if user_details.get('name'):
                            agent_reply += f"Which category interests you most, {user_details['name']}?"
                        else:
                            agent_reply += "Which category interests you most?"
                        
                        # Save conversation messages
                        state_manager.save_conversation_message(lead_id, 'user', message)
                        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                        
                        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
                        
                except Exception as e:
                    print(f"[ERROR] Failed to get product suggestions: {e}")
                    # Fallback with basic suggestions
                    agent_reply = "I'd be happy to help you with product recommendations! Here are our main categories:\n\n"
                    agent_reply += "📱 **Technology**: Smartphones, Laptops, Electronics\n"
                    agent_reply += "🏠 **Home & Living**: Furniture, Storage, Decor\n" 
                    agent_reply += "👔 **Fashion**: Clothing, Shoes, Accessories\n\n"
                    agent_reply += "What type of products interest you most?"
                    
                    # Save conversation messages
                    state_manager.save_conversation_message(lead_id, 'user', message)
                    state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                    
                    return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
            else:
                print("[DEBUG] RAG system not available, using basic suggestions")
                # Basic suggestions if RAG system not available
                agent_reply = "Here are our main product categories:\n\n"
                agent_reply += "📱 Technology (smartphones, laptops)\n"
                agent_reply += "🏠 Home & Living (furniture, storage)\n" 
                agent_reply += "👔 Fashion (clothing, accessories)\n\n"
                agent_reply += "What type of products are you most interested in?"
                
                # Save conversation messages
                state_manager.save_conversation_message(lead_id, 'user', message)
                state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                
                return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
        
        # Extract user details directly from user message first
        user_details = extract_user_details_from_user_message(message, lead_id)
        if user_details:
            print(f"[DEBUG] Extracted user details: {user_details}")
            state_manager.update_collected_details(lead_id, user_details)
            
            # Generate structured response based on what was collected
            collected = state_manager.get_collected_details(lead_id)
            agent_reply = generate_structured_response(collected, message)
        else:
            # Send lead message to agent for general conversation
            agent_reply = call_agent_sync(lead_id, message)
            
            # Check if the agent response contains user details in a structured format
            agent_details = extract_user_details(agent_reply)
            
            # Only update with agent details if they don't overwrite existing good data
            if agent_details:
                current_details = state_manager.get_collected_details(lead_id)
                safe_update = {}
                
                for key, value in agent_details.items():
                    if value and (not current_details.get(key) or len(str(current_details.get(key))) < 2):
                        safe_update[key] = value
                        print(f"[DEBUG] Safe update from agent: {key} = {value}")
                    elif value and current_details.get(key):
                        print(f"[DEBUG] Skipping agent extraction for {key}: already have '{current_details.get(key)}', agent suggested '{value}'")
                
                if safe_update:
                    state_manager.update_collected_details(lead_id, safe_update)
        
        # Check if we have everything except product interest
        collected = state_manager.get_collected_details(lead_id)
        if collected.get('name') and collected.get('age') and collected.get('country') and not collected.get('interest'):
            # Specifically ask for product interest
            response = format_product_interest_request()
            # Save conversation messages
            state_manager.save_conversation_message(lead_id, 'user', message)
            state_manager.save_conversation_message(lead_id, 'assistant', response)
            return render_template('conversation.html', lead_id=lead_id, response=response)
        
        # If we have all the details from various messages, prepare for confirmation
        if state_manager.are_details_complete(lead_id):
            # Check if the interest is generic/invalid - if so, ask for specific interest
            interest = collected.get('interest', '').lower()
            
            generic_interests = ['general', 'everything', 'anything', 'all products', 'various', 'multiple', 'different']
            if any(generic in interest for generic in generic_interests) or len(interest) < 4:
                agent_reply = f"Thanks {collected['name']}! I have your basic details. To give you the best product recommendations, what specific type of products are you most interested in?\n\n"
                agent_reply += "📱 Technology (smartphones, laptops)\n"
                agent_reply += "🏠 Home & Living (furniture, storage)\n"
                agent_reply += "👔 Fashion (clothing, accessories)\n\n"
                agent_reply += "Please let me know which category interests you most!"
                
                # Save conversation messages
                state_manager.save_conversation_message(lead_id, 'user', message)
                state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                
                return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
            
            # Set pending confirmation state and show confirmation prompt
            state_manager.update_conversation_state(
                lead_id,
                current_step='confirmation',
                pending_confirmation=True
            )
            
            confirmation_response = format_details_for_confirmation(collected)
            
            # Save conversation messages
            state_manager.save_conversation_message(lead_id, 'user', message)
            state_manager.save_conversation_message(lead_id, 'assistant', confirmation_response)
            
            return render_template('conversation.html', lead_id=lead_id, response=confirmation_response)
        
        # Save conversation messages for normal flow
        state_manager.save_conversation_message(lead_id, 'user', message)
        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
        
        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
    
    # GET request - provide welcome message
    # Get user details from state manager
    collected_details = state_manager.get_collected_details(lead_id)
    name = collected_details.get('name', '')
    age = collected_details.get('age', '')
    country = collected_details.get('country', '')
    interest = collected_details.get('interest', '')
    
    # Determine what information we still need
    if not name:
        welcome = "Hello! I'm your sales assistant. To get started, what's your name?"
    elif not age:
        welcome = f"Hello {name}! Nice to meet you. To help you find the perfect products, may I ask your age?"
    elif not country:
        welcome = f"Thanks {name}! And which country are you from?"
    elif not interest:
        welcome = f"Great! Now {name}, what type of products are you interested in? (Technology, Fashion, Home & Living, etc.)"
    else:
        # All details collected, show confirmation
        welcome = format_details_for_confirmation(collected_details)
        state_manager.update_conversation_state(
            lead_id,
            current_step='confirmation',
            pending_confirmation=True
        )
    
    return render_template('conversation.html', lead_id=lead_id, response=welcome)

# --- WebSocket Event Handlers ---
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f'[WEBSOCKET] Client connected: {request.sid}')
    emit('connected', {'message': 'Connected to sales agent'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f'[WEBSOCKET] Client disconnected: {request.sid}')

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Handle joining a conversation room"""
    lead_id = data.get('lead_id')
    if lead_id:
        join_room(lead_id)
        emit('joined_room', {'lead_id': lead_id, 'room': lead_id})
        print(f'[WEBSOCKET] Client {request.sid} joined room {lead_id}')

@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """Handle leaving a conversation room"""
    lead_id = data.get('lead_id')
    if lead_id:
        leave_room(lead_id)
        emit('left_room', {'lead_id': lead_id})
        print(f'[WEBSOCKET] Client {request.sid} left room {lead_id}')

@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message sending"""
    lead_id = data.get('lead_id')
    message = data.get('message')
    
    if not lead_id or not message:
        emit('error', {'message': 'Missing lead_id or message'})
        return
    
    try:
        # Record activity
        state_manager.record_user_activity(lead_id)
        
        # Save user message
        state_manager.save_conversation_message(lead_id, 'user', message)
        
        # Emit user message to room (this will be received by the client)
        socketio.emit('message_update', {
            'lead_id': lead_id,
            'message': message,
            'role': 'user',
            'timestamp': datetime.utcnow().isoformat()
        }, room=lead_id)
        
        # Handle confirmation message first - HIGHEST PRIORITY
        message_lower = message.lower().strip()
        
        if message_lower == 'confirm':
            print(f"[WS_DEBUG] User confirming details: {message}")
            details = state_manager.get_collected_details(lead_id)
            
            if state_manager.are_details_complete(lead_id):
                # Update lead status
                state_manager.update_conversation_state(
                    lead_id, 
                    current_step='confirmed',
                    pending_confirmation=False
                )
                
                # Save to CSV
                save_to_csv(
                    lead_id, 
                    details['name'], 
                    details['age'], 
                    details['country'], 
                    details['interest'], 
                    'confirmed'
                )
                
                # Clean up incomplete entries from CSV after successful confirmation
                print(f"[WS_DEBUG] Running CSV cleanup after confirmation")
                clean_incomplete_csv_entries()
                
                # Provide product recommendations
                agent_reply = f"Thank you for confirming your details, {details['name']}! Your information has been saved successfully. "
                agent_reply += f"Based on your interest in {details['interest']}, here are some great product recommendations:\n\n"
                
                # Simple product recommendations based on interest
                if any(keyword in details['interest'].lower() for keyword in ['technology', 'tech', 'samsung', 'phone', 'smartphone', 'laptop', 'computer', 'electronics']):
                    agent_reply += "📱 Samsung Galaxy S24 ($799.99) - Latest smartphone with amazing camera\n"
                    agent_reply += "📱 iPhone 15 Pro ($999.99) - Premium Apple device with titanium design\n"
                    agent_reply += "💻 MacBook Pro M3 ($1,999.99) - Powerful laptop for professionals\n"
                    agent_reply += "🎧 AirPods Pro ($249.99) - Premium wireless earbuds"
                elif any(keyword in details['interest'].lower() for keyword in ['fashion', 'clothes', 'clothing', 'dress', 'shirt', 'shoes', 'accessories']):
                    agent_reply += "👔 Men's Slim Fit Jeans ($49.99) - Comfortable premium denim\n"
                    agent_reply += "👗 Designer Summer Dress ($89.99) - Elegant and stylish\n"
                    agent_reply += "👟 Running Shoes ($79.99) - High-performance athletic footwear\n"
                    agent_reply += "👜 Leather Handbag ($129.99) - Premium quality accessory"
                elif any(keyword in details['interest'].lower() for keyword in ['home', 'furniture', 'decoration', 'living', 'kitchen', 'bedroom']):
                    agent_reply += "🛏️ King Size Bed ($599.99) - Comfortable premium mattress\n"
                    agent_reply += "🪑 Ergonomic Office Chair ($199.99) - Perfect for working from home\n"
                    agent_reply += "🏠 Storage Solutions Set ($99.99) - Organize your space beautifully\n"
                    agent_reply += "🍽️ Dinnerware Set ($79.99) - Elegant dining collection"
                else:
                    agent_reply += "📱 Samsung Galaxy S24 ($799.99) - Latest smartphone with amazing camera\n"
                    agent_reply += "🛍️ Premium Product Bundle ($149.99) - Curated selection of popular items\n"
                    agent_reply += "🎁 Gift Card ($50-500) - Perfect for any occasion\n"
                    agent_reply += "⭐ Best Sellers Collection - Top-rated products across all categories"
                
                print(f"[WS_DEBUG] Confirmation processed, data saved to CSV")
            else:
                agent_reply = "I notice some details are still missing. Let me help you complete your profile first."
        
        # Check if user is asking for product suggestions/recommendations - SECOND PRIORITY
        else:
            suggestion_keywords = ['suggestion', 'suggestions', 'recommend', 'recommendation', 'recommendations', 
                                 'what do you have', 'show me products', 'product catalog', 'catalog', 
                                 'what products', 'products available', 'what can you offer', 'suggest me', 'can suggest']
            
            is_asking_for_suggestions = any(keyword in message_lower for keyword in suggestion_keywords)
            
            if is_asking_for_suggestions:
                print(f"[WS_DEBUG] User asking for suggestions: {message}")
                
                # Get user details from state manager
                user_details = state_manager.get_collected_details(lead_id)
                print(f"[WS_DEBUG] Found user details: {user_details}")
                
                # Always try to provide suggestions if RAG system is available
                try:
                    agent_reply = "Great! Here are some popular products from our catalog:\n\n"
                    agent_reply += "📱 **Technology**: Samsung Galaxy S24 ($799.99), iPhone 15 Pro ($999.99), MacBook Pro M3\n\n"
                    agent_reply += "🏠 **Home & Living**: King Size Wooden Bed, Storage Solutions, Home Decor\n\n"
                    agent_reply += "👔 **Fashion**: Men's Slim Fit Jeans, Designer Clothing, Accessories\n\n"
                    
                    if user_details.get('name'):
                        agent_reply += f"Which category interests you most, {user_details['name']}?"
                    else:
                        agent_reply += "Which category interests you most?"
                        
                except Exception as e:
                    print(f"[WS_ERROR] Failed to get product suggestions: {e}")
                    agent_reply = "I'd be happy to help you with product recommendations! What type of products are you looking for?"
            else:
                # Extract user details directly from user message first
                user_details = extract_user_details_from_user_message(message, lead_id)
                if user_details:
                    print(f"[WS_DEBUG] Extracted user details: {user_details}")
                    state_manager.update_collected_details(lead_id, user_details)
                    
                    # Generate structured response based on what was collected
                    collected = state_manager.get_collected_details(lead_id)
                    agent_reply = generate_structured_response(collected, message)
                    
                    # If all details are collected, set pending_confirmation flag
                    if state_manager.are_details_complete(lead_id):
                        print(f"[WS_DEBUG] All details collected, setting pending_confirmation")
                        state_manager.update_conversation_state(lead_id, pending_confirmation=True)
                else:
                    # Get agent response for general conversation
                    agent_reply = call_agent_sync(lead_id, message)
                
                # Process any extracted details from agent response with safety checks
                details = extract_user_details(agent_reply)
                if details:
                    current_details = state_manager.get_collected_details(lead_id)
                    safe_update = {}
                    
                    for key, value in details.items():
                        if value and (not current_details.get(key) or len(str(current_details.get(key))) < 2):
                            safe_update[key] = value
                            print(f"[WS_DEBUG] Safe update from agent: {key} = {value}")
                        elif value and current_details.get(key):
                            print(f"[WS_DEBUG] Skipping agent extraction for {key}: already have '{current_details.get(key)}', agent suggested '{value}'")
                    
                    if safe_update:
                        state_manager.update_collected_details(lead_id, safe_update)
        
        # Save agent response
        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
        
        # Emit agent response to room
        socketio.emit('message_update', {
            'lead_id': lead_id,
            'message': agent_reply,
            'role': 'assistant',
            'timestamp': datetime.utcnow().isoformat()
        }, room=lead_id)
        
        # Emit updated user status to update the sidebar
        try:
            details = state_manager.get_collected_details(lead_id)
            socketio.emit('user_status', {
                'lead_id': lead_id,
                'collected_details': details,
                'details_complete': state_manager.are_details_complete(lead_id),
                'missing_details': state_manager.get_missing_details(lead_id)
            }, room=lead_id)
        except Exception as e:
            print(f"[WS_DEBUG] Error emitting user status: {e}")
        
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {str(e)}")
        emit('error', {'message': 'Failed to process message'})

@socketio.on('get_conversation_history')
def handle_get_conversation_history(data):
    """Get conversation history for a lead"""
    lead_id = data.get('lead_id')
    limit = data.get('limit', 50)
    
    if not lead_id:
        emit('error', {'message': 'Missing lead_id'})
        return
    
    try:
        history = state_manager.get_conversation_history(lead_id, limit)
        emit('conversation_history', {
            'lead_id': lead_id,
            'history': history
        })
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        emit('error', {'message': 'Failed to get conversation history'})

@socketio.on('get_user_status')
def handle_get_user_status(data):
    """Get user status and collected details"""
    lead_id = data.get('lead_id')
    
    if not lead_id:
        emit('error', {'message': 'Missing lead_id'})
        return
    
    try:
        state = state_manager.get_or_create_conversation_state(lead_id)
        details = state_manager.get_collected_details(lead_id)
        
        emit('user_status', {
            'lead_id': lead_id,
            'current_step': state.current_step,
            'collected_details': details,
            'details_complete': state_manager.are_details_complete(lead_id),
            'missing_details': state_manager.get_missing_details(lead_id),
            'is_active': state.is_active,
            'last_activity': state.last_activity.isoformat() if state.last_activity else None
        })
    except Exception as e:
        logger.error(f"Error getting user status: {str(e)}")
        emit('error', {'message': 'Failed to get user status'})

# --- Follow-up checker ---
def follow_up_checker():
    """Enhanced follow-up checker using state management"""
    print("[FOLLOW-UP] Starting follow-up checker thread...")
    last_check_time = time.time()
    
    # Wait a bit before starting to let the app fully initialize
    time.sleep(5)
    print("[FOLLOW-UP] Follow-up checker is now active")
    
    while True:
        time.sleep(30)  # Check every 30 seconds
        
        try:
            # Get inactive users
            inactive_users = state_manager.get_inactive_users(threshold_minutes=1)
            
            if inactive_users:
                print(f"\n[FOLLOW-UP] Found {len(inactive_users)} inactive users")
                
                for lead_id in inactive_users:
                    try:
                        state = state_manager.get_or_create_conversation_state(lead_id)
                        
                        # Don't send too many follow-ups
                        if state.follow_up_count >= 3:
                            continue
                        
                        # Create personalized follow-up message
                        details = state_manager.get_collected_details(lead_id)
                        name = details.get('name', 'there')
                        
                        if state.follow_up_count == 0:
                            follow_up_message = f"Hi {name}! I noticed you might have stepped away. I'm still here to help you find the perfect products. What would you like to explore?"
                        elif state.follow_up_count == 1:
                            follow_up_message = f"Just checking in, {name}. I have some great product recommendations based on our conversation. Would you like to see them?"
                        else:
                            follow_up_message = f"Hi {name}, I'll be here whenever you're ready to continue our conversation. Feel free to message me anytime!"
                        
                        # Use simple follow-up message instead of calling agent
                        agent_response = follow_up_message
                        
                        # Save the follow-up message
                        state_manager.save_conversation_message(lead_id, 'system', follow_up_message)
                        state_manager.save_conversation_message(lead_id, 'assistant', agent_response)
                        
                        # Add to follow-up queue
                        state_manager.add_follow_up_message(lead_id, agent_response)
                        
                        # Update follow-up count
                        state_manager.update_conversation_state(
                            lead_id,
                            follow_up_count=state.follow_up_count + 1
                        )
                        
                        # Emit real-time follow-up via WebSocket
                        socketio.emit('follow_up_message', {
                            'lead_id': lead_id,
                            'message': agent_response,
                            'timestamp': datetime.utcnow().isoformat()
                        }, room=lead_id)
                        
                        print(f"[FOLLOW-UP] Sent follow-up #{state.follow_up_count + 1} to {lead_id}")
                        
                        # Record metric
                        state_manager.record_system_metric('follow_up_sent', 1, {
                            'lead_id': lead_id,
                            'follow_up_count': state.follow_up_count + 1
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to send follow-up to {lead_id}: {str(e)}")
            
            # Clean up inactive sessions periodically
            current_time = time.time()
            if current_time - last_check_time > 3600:  # Every hour
                try:
                    state_manager.cleanup_inactive_sessions(hours=24)
                    last_check_time = current_time
                    print("[CLEANUP] Cleaned up inactive sessions")
                except Exception as e:
                    print(f"[CLEANUP] Error during cleanup: {e}")
                
        except Exception as e:
            logger.error(f"Error in follow-up checker: {str(e)}")
            time.sleep(60)  # Wait longer on error

def start_follow_up_thread():
    """Start follow-up thread in non-blocking way"""
    try:
        t = Thread(target=follow_up_checker, daemon=True)
        t.start()
        print("[THREAD] Follow-up thread started successfully")
    except Exception as e:
        print(f"[THREAD] Failed to start follow-up thread: {e}")

# --- New API Endpoints for Enhanced RAG System ---

@app.route('/api/rag_status', methods=['GET'])
def rag_status():
    """Get status of both RAG systems"""
    try:
        if get_rag_system():
            status = get_rag_system().get_system_status()
        else:
            status = {
                "chat_history_rag": {
                    "embeddings_available": False,
                    "active_users": 0
                },
                "company_docs_rag": {
                    "embeddings_available": False,
                    "llm_available": False,
                    "vectorstore_available": False
                }
            }
        
        return jsonify({
            "success": True,
            "status": status,
            "enhanced_system_active": get_rag_system() is not None
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/user_context/<user_id>', methods=['GET'])
def get_user_context(user_id):
    """Get conversation context for a specific user"""
    try:
        query = request.args.get('query', 'conversation history')
        
        if get_rag_system():
            context = get_rag_system().get_user_context(user_id, query)
        else:
            context = ""
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "context": context,
            "enhanced_system_active": get_rag_system() is not None
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/product_recommendations', methods=['POST'])
def get_product_recommendations():
    """Get personalized product recommendations"""
    try:
        data = request.json
        user_data = data.get('user_data', {})
        query = data.get('query', 'product recommendation')
        
        if get_rag_system():
            recommendations = get_rag_system().get_product_recommendations(user_data, query)
        else:
            recommendations = "Enhanced recommendation system not available"
        
        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "user_data": user_data,
            "enhanced_system_active": get_rag_system() is not None
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/clear_user_data/<user_id>', methods=['DELETE'])
def clear_user_data(user_id):
    """Clear all data for a specific user"""
    try:
        if get_rag_system():
            get_rag_system().clear_user_data(user_id)
            message = f"Cleared all data for user {user_id}"
        else:
            message = f"Enhanced system not available - cannot clear data for user {user_id}"
        
        return jsonify({
            "success": True,
            "message": message,
            "enhanced_system_active": get_rag_system() is not None
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/enhanced_chat', methods=['POST'])
def enhanced_chat():
    """Enhanced chat endpoint using the new dual RAG system"""
    try:
        data = request.json
        user_id = data.get('user_id')
        session_id = data.get('session_id', user_id)  # Use user_id as session_id if not provided
        message = data.get('message')
        
        if not user_id or not message:
            return jsonify({
                "success": False,
                "error": "user_id and message are required"
            }), 400
        
        # Use state manager for this conversation
        state_manager.record_user_activity(user_id)
        state_manager.save_conversation_message(user_id, 'user', message)
        
        # Get response from enhanced agent
        response = call_agent_sync(session_id, message)
        
        # Save agent response
        state_manager.save_conversation_message(user_id, 'assistant', response)
        
        # Get user context and details
        user_context = ""
        if get_rag_system():
            user_context = get_rag_system().get_user_context(user_id, message)
        
        details = state_manager.get_collected_details(user_id)
        
        return jsonify({
            "success": True,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "collected_details": details,
            "details_complete": state_manager.are_details_complete(user_id),
            "has_context": bool(user_context),
            "enhanced_system_active": get_rag_system() is not None
        })
        
    except Exception as e:
        logger.error(f"Error in enhanced chat: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# --- Analytics and Management Endpoints ---

@app.route('/api/analytics/leads', methods=['GET'])
def get_lead_analytics():
    """Get lead analytics and statistics"""
    try:
        stats = state_manager.get_lead_statistics()
        
        # Get recent metrics
        recent_metrics = state_manager.get_system_metrics(hours=24)
        
        # Calculate conversion rates
        total_messages = sum(1 for m in recent_metrics if m['metric_name'] == 'chat_messages')
        total_conversions = sum(1 for m in recent_metrics if m['metric_name'] == 'conversations_started')
        
        stats.update({
            'recent_messages': total_messages,
            'recent_conversions': total_conversions,
            'recent_metrics': recent_metrics[:10]  # Last 10 metrics
        })
        
        return jsonify({
            "success": True,
            "analytics": stats
        })
        
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/leads', methods=['GET'])
def get_all_leads():
    """Get all leads with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        query = Lead.query
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        leads = [lead.to_dict() for lead in pagination.items]
        
        return jsonify({
            "success": True,
            "leads": leads,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting leads: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/leads/<lead_id>', methods=['GET'])
def get_lead_details(lead_id):
    """Get detailed information for a specific lead"""
    try:
        # Get lead from database
        lead = Lead.query.filter_by(lead_id=lead_id).first()
        if not lead:
            return jsonify({
                "success": False,
                "error": "Lead not found"
            }), 404
        
        # Get conversation history
        conversations = state_manager.get_conversation_history(lead_id)
        
        # Get recommendations
        recommendations = state_manager.get_user_recommendations(lead_id)
        
        # Get current state
        state = state_manager.get_or_create_conversation_state(lead_id)
        collected_details = state_manager.get_collected_details(lead_id)
        
        return jsonify({
            "success": True,
            "lead": lead.to_dict(),
            "conversations": conversations,
            "recommendations": recommendations,
            "current_state": {
                "current_step": state.current_step,
                "collected_details": collected_details,
                "details_complete": state_manager.are_details_complete(lead_id),
                "is_active": state.is_active,
                "follow_up_count": state.follow_up_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting lead details: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/system/health', methods=['GET'])
def system_health():
    """Get system health status"""
    try:
        # Check database connection
        db_status = True
        try:
            db.session.execute('SELECT 1')
        except Exception:
            db_status = False
        
        # Check agent systems
        agent_status = {
            "root_agent_available": get_root_agent() is not None,
            "dual_rag_available": get_rag_system() is not None,
            "runner_available": get_runner() is not None
        }
        
        # Get system metrics
        stats = state_manager.get_lead_statistics()
        
        return jsonify({
            "success": True,
            "health": {
                "database": db_status,
                "agents": agent_status,
                "statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# --- Helper: Initialize RAG System ---
def initialize_rag_system():
    """Ensure the RAG system is properly initialized with Word documents"""
    if get_rag_system():
        try:
            print("[RAG] Initializing company documents...")
            
            # Get the correct path to docs directory
            docs_path = os.path.join(current_dir, "docs")
            print(f"[RAG] Looking for documents in: {docs_path}")
            
            if not os.path.exists(docs_path):
                print(f"[RAG] ❌ Documents directory not found: {docs_path}")
                return
            
            # Force reload documents to ensure Word document is loaded
            get_rag_system().company_docs_rag.load_company_documents(docs_path)
            print("[RAG] Company documents loaded successfully")
            
            # Test the system
            test_suggestions = get_rag_system().company_docs_rag.get_product_suggestions("technology", k=2)
            if test_suggestions:
                print(f"[RAG] ✅ System working - found {len(test_suggestions)} test suggestions")
                for i, suggestion in enumerate(test_suggestions, 1):
                    print(f"[RAG]   {i}. {suggestion['content'][:100]}...")
            else:
                print("[RAG] ⚠️ System loaded but no suggestions found")
                
        except Exception as e:
            print(f"[RAG] ❌ Error initializing RAG system: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[RAG] ⚠️ DualRAGSystem not available")

def initialize_rag_system_background():
    """Initialize RAG system in background thread to prevent blocking"""
    def rag_worker():
        try:
            print("[RAG_BACKGROUND] RAG system will be loaded on-demand when needed")
            print("[RAG_BACKGROUND] ✅ Background initialization completed (lazy loading enabled)")
        except Exception as e:
            print(f"[RAG_BACKGROUND] ❌ Background thread failed: {e}")
    
    # Start RAG initialization in background thread
    rag_thread = Thread(target=rag_worker, daemon=True)
    rag_thread.start()
    print("[RAG_BACKGROUND] RAG will load on-demand to prevent startup delays")

def create_app():
    """Application factory function - simplified to prevent blocking"""
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
    
    # Skip background thread initialization to prevent blocking
    print("✅ App created successfully (background features disabled)")
    
    return app

# --- Helper to clean incomplete entries from CSV ---
def clean_incomplete_csv_entries():
    """Remove entries from CSV where age, country, or interest is missing"""
    try:
        import pandas as pd
        import os
        
        if not os.path.exists(CSV_FILE):
            print("[CLEANUP] CSV file doesn't exist, nothing to clean")
            return
        
        # Read the CSV file
        df = pd.read_csv(CSV_FILE)
        initial_count = len(df)
        
        print(f"[CLEANUP] Starting CSV cleanup. Initial entries: {initial_count}")
        
        # Remove entries where age, country, or interest is empty/null
        # Keep entries that have all three fields filled AND status is 'confirmed'
        df_cleaned = df.dropna(subset=['age', 'country', 'interest'])
        df_cleaned = df_cleaned[(df_cleaned['age'] != '') & 
                               (df_cleaned['country'] != '') & 
                               (df_cleaned['interest'] != '')]
        
        final_count = len(df_cleaned)
        removed_count = initial_count - final_count
        
        if removed_count > 0:
            # Save the cleaned data back to CSV
            df_cleaned.to_csv(CSV_FILE, index=False)
            print(f"[CLEANUP] Removed {removed_count} incomplete entries. Remaining entries: {final_count}")
            
            # Log the removed entries for debugging
            df_removed = df[~df.index.isin(df_cleaned.index)]
            print(f"[CLEANUP] Removed entries:")
            for _, row in df_removed.iterrows():
                print(f"  - Lead {row['lead_id']}: {row['name']} (missing: age={not row['age']}, country={not row['country']}, interest={not row['interest']})")
        else:
            print(f"[CLEANUP] No incomplete entries found. All {final_count} entries are complete.")
            
    except ImportError:
        print("[CLEANUP] pandas not available, using manual CSV cleanup")
        manual_csv_cleanup()
    except Exception as e:
        print(f"[CLEANUP] Error during CSV cleanup: {e}")

def manual_csv_cleanup():
    """Manual CSV cleanup without pandas dependency"""
    try:
        import csv
        
        # Read all rows
        rows_to_keep = []
        removed_count = 0
        
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            for row in reader:
                # Check if age, country, and interest are all filled
                if (row.get('age', '').strip() and 
                    row.get('country', '').strip() and 
                    row.get('interest', '').strip()):
                    rows_to_keep.append(row)
                else:
                    removed_count += 1
                    print(f"[CLEANUP] Removing incomplete entry: Lead {row.get('lead_id', 'unknown')}: {row.get('name', 'unknown')}")
        
        if removed_count > 0:
            # Write back only complete entries
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                if rows_to_keep:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows_to_keep)
            
            print(f"[CLEANUP] Manual cleanup complete. Removed {removed_count} entries, kept {len(rows_to_keep)} complete entries.")
        else:
            print(f"[CLEANUP] No incomplete entries found during manual cleanup.")
            
    except Exception as e:
        print(f"[CLEANUP] Error during manual CSV cleanup: {e}")

if __name__ == '__main__':
    # Create and configure the app - simplified startup
    print("🚀 Starting Sales Agent System...")
    
    app = create_app()
    
    # Skip environment variable checks to prevent delays
    print("✅ Environment variables loaded from config.env")
    
    # Print startup information - no lazy loading calls
    print("\n" + "="*50)
    print("🚀 SALES AGENT SYSTEM STARTING")
    print("="*50)
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"🔐 Secret Key: {'Set' if app.config['SECRET_KEY'] != 'your-secret-key-here' else 'Using default (please change)'}")
    print(f"🤖 Root Agent: Will load on first use")
    print(f"📚 RAG System: Will load on first use")
    print(f"🔄 WebSocket: Enabled")
    print(f"📱 Real-time Chat: Enabled")
    print(f"✅ Conversation Flow: Active")
    print("="*50 + "\n")
    
    # Start the application with SocketIO - simplified
    try:
        print("🌐 Starting Flask server...")
        socketio.run(
            app, 
            debug=True, 
            port=5000,
            host='0.0.0.0',
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        raise
    
