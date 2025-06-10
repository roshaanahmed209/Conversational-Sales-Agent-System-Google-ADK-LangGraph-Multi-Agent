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

# Import with fallback handling
try:
    from root_agent_system import root_agent
    from enhanced_rag_system import dual_rag_system
except ImportError:
    print("[WARNING] Could not import enhanced systems, using legacy system")
    try:
        from agent import call_agent_sync, langgraph_agent, sales_agent
        root_agent = None
        dual_rag_system = None
    except ImportError:
        print("[ERROR] Could not import any agent system")
        root_agent = None
        dual_rag_system = None

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

# Initialize runner with safety checks
runner = None
try:
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

# --- Helper: Sync wrapper around async runner ---
async def _run_agent_async(conversation_id: str, text: str) -> str:
    """Run agent async with safety checks"""
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
    """Enhanced call agent with better error handling"""
    # Check if we have a working root agent and runner first
    if root_agent is None or runner is None:
        # Fallback to legacy agent system
        print(f"[FALLBACK] Using legacy agent for {conversation_id} (root_agent: {root_agent is not None}, runner: {runner is not None})")
        try:
            # Use the legacy agent system
            from agent import call_agent_sync as legacy_call_agent
            return legacy_call_agent(conversation_id, text)
        except Exception as e:
            print(f"[ERROR] Legacy agent failed: {e}")
            return "I'm experiencing technical difficulties. Please try again later."
    
    # Try Google ADK system
    try:
        # Ensure session exists - create it if it doesn't
        try:
            session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=conversation_id)
        except (KeyError, AttributeError, Exception) as e:
            print(f"[SESSION] Creating new session for {conversation_id}")
            try:
                session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=conversation_id)
            except Exception as create_error:
                print(f"[SESSION] Failed to create session: {create_error}")
                # Fallback to legacy system
                try:
                    from agent import call_agent_sync as legacy_call_agent
                    return legacy_call_agent(conversation_id, text)
                except Exception as fallback_error:
                    print(f"[ERROR] Fallback also failed: {fallback_error}")
                    return "I'm having trouble starting our conversation. Please try again."
        
        # Run the async agent
        return asyncio.run(_run_agent_async(conversation_id, text))
        
    except Exception as e:
        print(f"[ERROR] Google ADK agent failed: {e}")
        # Fallback to legacy agent
        try:
            from agent import call_agent_sync as legacy_call_agent
            return legacy_call_agent(conversation_id, text)
        except Exception as fallback_error:
            print(f"[ERROR] Fallback failed: {fallback_error}")
            return "I'm experiencing technical difficulties. Please try again later."

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

# --- Helper to extract user details from a structured response ---
def extract_user_details(message):
    details = {
        'name': None,
        'age': None,
        'country': None,
        'interest': None
    }
    
    print(f"[DEBUG] Extracting details from message (first 200 chars): {message[:200]}...")
    
    # Clean the message by removing markdown formatting
    clean_message = re.sub(r'\*\*', '', message)  # Remove ** formatting
    clean_message = re.sub(r'^\s*-\s*', '', clean_message, flags=re.MULTILINE)  # Remove bullet points
    
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
            if not re.search(r'\?|what|how|when|where|why', name_candidate, re.IGNORECASE):
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
                    
                    agent_reply = "Thank you for confirming your details! Your information has been saved successfully. How else can I assist you today?"
                    
                    # Save agent response
                    state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
                    
                    # Emit real-time update
                    socketio.emit('message_update', {
                        'lead_id': lead_id,
                        'message': agent_reply,
                        'role': 'assistant',
                        'timestamp': datetime.utcnow().isoformat()
                    }, room=lead_id)
                    
                    return jsonify({"response": agent_reply, "status": "confirmed"})
        
        # Send message to agent for normal conversation
        agent_reply = call_agent_sync(lead_id, message)
        
        # Check if the agent response contains user details in a structured format
        details = extract_user_details(agent_reply)
        if details:
            # Update collected details
            state_manager.update_collected_details(lead_id, details)
            
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
    save_csv_complete("leads.csv")
    lead_id = request.args.get('lead_id')
    if not lead_id:
        return jsonify({"has_follow_up": False})
    
    try:
        # Check for follow-up messages using state manager
        messages = state_manager.get_follow_up_messages(lead_id)
        
        if messages:
            # Return the first message
            message = messages[0]
            return jsonify({
                "has_follow_up": True, 
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        save_csv_complete("leads.csv")
        return jsonify({"has_follow_up": False})
        
    except Exception as e:
        logger.error(f"Error checking follow-up: {str(e)}")
        return jsonify({"has_follow_up": False, "error": str(e)})

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    save_csv_complete("leads.csv")
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
    global user_input_counter
    
    if request.method == 'POST':
        message = request.form.get('message')
        
        # Increment the counter when a user sends a message
        user_input_counter += 1
        
        # Check if this is an exit command
        if is_exit_command(message):
            # Provide a farewell message and redirect
            return render_template('exit.html', message="Thank you for chatting with me! Goodbye!", redirect_url=url_for('home'))
        
        # Check if this is a confirmation message
        if message.lower().strip() == 'confirm':
            if lead_id in conversation_details and 'last_details_message' in conversation_details[lead_id]:
                previous_response = conversation_details[lead_id]['last_details_message']
                
                # Get details either from the stored message or collected details
                if 'collected_details' in conversation_details[lead_id] and all(conversation_details[lead_id]['collected_details'].get(key) for key in ['name', 'age', 'country', 'interest']):
                    details = conversation_details[lead_id]['collected_details']
                else:
                    details = extract_user_details(previous_response)
                
                if are_details_complete(details):
                    save_to_csv(
                        lead_id, 
                        details['name'], 
                        details['age'], 
                        details['country'], 
                        details['interest'], 
                        'confirmed'
                    )
                    
                    # Provide product recommendations using RAG system
                    agent_reply = "Thank you for confirming your details! Your information has been saved successfully. "
                    
                    if dual_rag_system:
                        try:
                            # Get personalized product recommendations
                            user_data = {
                                "name": details['name'],
                                "age": details['age'],
                                "country": details['country'],
                                "interest": details['interest']
                            }
                            recommendations = dual_rag_system.get_product_recommendations(user_data, f"products for {details['interest']}")
                            agent_reply += f"\n\nBased on your interest in {details['interest']}, here are some personalized product recommendations:\n\n{recommendations}"
                        except Exception as e:
                            print(f"[ERROR] Failed to get recommendations: {e}")
                            agent_reply += "Let me know if you'd like to see our product catalog or if you have any specific questions!"
                    else:
                        agent_reply += "Let me know if you'd like to see our product catalog or if you have any specific questions!"
                    
                    return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
        
        # Check if user is asking for product suggestions/recommendations - PRIORITY CHECK
        message_lower = message.lower().strip()
        suggestion_keywords = ['suggestion', 'suggestions', 'recommend', 'recommendation', 'recommendations', 
                             'what do you have', 'show me products', 'product catalog', 'catalog', 
                             'what products', 'products available', 'what can you offer', 'suggest me', 'can suggest']
        
        is_asking_for_suggestions = any(keyword in message_lower for keyword in suggestion_keywords)
        
        if is_asking_for_suggestions:
            print(f"[DEBUG] User asking for suggestions: {message}")
            
            # Check if we have user details
            user_details = {}
            if lead_id in conversation_details and 'collected_details' in conversation_details[lead_id]:
                user_details = conversation_details[lead_id]['collected_details']
                print(f"[DEBUG] Found user details: {user_details}")
            
            # Always try to provide suggestions if RAG system is available
            if dual_rag_system:
                try:
                    # Provide general suggestions from our product catalog
                    print("[DEBUG] Getting general product suggestions from RAG system")
                    suggestions = dual_rag_system.company_docs_rag.get_product_suggestions("general products", k=6)
                    
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
                        
                        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
                        
                except Exception as e:
                    print(f"[ERROR] Failed to get product suggestions: {e}")
                    # Fallback with basic suggestions
                    agent_reply = "I'd be happy to help you with product recommendations! Here are our main categories:\n\n"
                    agent_reply += "📱 **Technology**: Smartphones, Laptops, Electronics\n"
                    agent_reply += "🏠 **Home & Living**: Furniture, Storage, Decor\n" 
                    agent_reply += "👔 **Fashion**: Clothing, Shoes, Accessories\n\n"
                    agent_reply += "What type of products interest you most?"
                    return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
            else:
                print("[DEBUG] RAG system not available, using basic suggestions")
                # Basic suggestions if RAG system not available
                agent_reply = "Here are our main product categories:\n\n"
                agent_reply += "📱 Technology (smartphones, laptops)\n"
                agent_reply += "🏠 Home & Living (furniture, storage)\n" 
                agent_reply += "👔 Fashion (clothing, accessories)\n\n"
                agent_reply += "What type of products are you most interested in?"
                return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
        
        # Send lead message to agent
        agent_reply = call_agent_sync(lead_id, message)
        
        # Check if the agent response contains user details in a structured format
        details = extract_user_details(agent_reply)
        
        # Store partial details we've collected so far
        if lead_id not in conversation_details:
            conversation_details[lead_id] = {'last_details_message': '', 'collected_details': {}}
        
        # Update collected details with any new information
        for key, value in details.items():
            if value:
                if 'collected_details' not in conversation_details[lead_id]:
                    conversation_details[lead_id]['collected_details'] = {}
                conversation_details[lead_id]['collected_details'][key] = value
        
        # Check if we have everything except product interest
        if 'collected_details' in conversation_details[lead_id]:
            collected = conversation_details[lead_id]['collected_details']
            if collected.get('name') and collected.get('age') and collected.get('country') and not collected.get('interest'):
                # Specifically ask for product interest
                return render_template('conversation.html', lead_id=lead_id, response=format_product_interest_request())
        
        # If we have all the details from various messages, prepare for confirmation
        if 'collected_details' in conversation_details[lead_id] and all(conversation_details[lead_id]['collected_details'].get(key) for key in ['name', 'age', 'country', 'interest']):
            # Check if the interest is generic/invalid - if so, ask for specific interest
            collected = conversation_details[lead_id]['collected_details']
            interest = collected.get('interest', '').lower()
            
            generic_interests = ['general', 'everything', 'anything', 'all products', 'various', 'multiple', 'different']
            if any(generic in interest for generic in generic_interests) or len(interest) < 4:
                agent_reply = f"Thanks {collected['name']}! I have your basic details. To give you the best product recommendations, what specific type of products are you most interested in?\n\n"
                agent_reply += "📱 Technology (smartphones, laptops)\n"
                agent_reply += "🏠 Home & Living (furniture, storage)\n"
                agent_reply += "👔 Fashion (clothing, accessories)\n\n"
                agent_reply += "Please let me know which category interests you most!"
                return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
            
            # Store the complete details for confirmation
            conversation_details[lead_id]['last_details_message'] = format_details_for_confirmation(conversation_details[lead_id]['collected_details'])
            return render_template('conversation.html', lead_id=lead_id, response=conversation_details[lead_id]['last_details_message'])
        
        # If all details are complete in the current message
        if are_details_complete(details):
            # Store the formatted details for later confirmation
            conversation_details[lead_id]['last_details_message'] = agent_reply
            
            # Replace agent response with formatted confirmation prompt
            agent_reply = format_details_for_confirmation(details)
        
        save_csv_complete("leads.csv")
        return render_template('conversation.html', lead_id=lead_id, response=agent_reply)
    
    # GET
    # Provide a personalized welcome message using the stored name
    if lead_id in conversation_details and 'collected_details' in conversation_details[lead_id]:
        name = conversation_details[lead_id]['collected_details'].get('name', '')
        if name:
            welcome = "I'm your sales assistant. I need to collect some information to help you find the perfect products. May I ask your age?"
        else:
            welcome = "Hello! I'm your sales assistant. To get started, what's your name?"
    else:
        welcome = "Hello! I'm your sales assistant. To get started, what's your name?"
    
    save_csv_complete("leads.csv")
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
        
        # Emit user message to room
        socketio.emit('message_update', {
            'lead_id': lead_id,
            'message': message,
            'role': 'user',
            'timestamp': datetime.utcnow().isoformat()
        }, room=lead_id)
        
        # Get agent response
        agent_reply = call_agent_sync(lead_id, message)
        
        # Process any extracted details
        details = extract_user_details(agent_reply)
        if details:
            state_manager.update_collected_details(lead_id, details)
        
        # Save agent response
        state_manager.save_conversation_message(lead_id, 'assistant', agent_reply)
        
        # Emit agent response to room
        socketio.emit('message_update', {
            'lead_id': lead_id,
            'message': agent_reply,
            'role': 'assistant',
            'timestamp': datetime.utcnow().isoformat()
        }, room=lead_id)
        
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
    save_csv_complete("leads.csv")
    last_check_time = time.time()
    
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
                        
                        # Get agent response for the follow-up
                        try:
                            agent_response = call_agent_sync(lead_id, follow_up_message)
                        except Exception:
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
                state_manager.cleanup_inactive_sessions(hours=24)
                last_check_time = current_time
                print("[CLEANUP] Cleaned up inactive sessions")
                
        except Exception as e:
            logger.error(f"Error in follow-up checker: {str(e)}")
            time.sleep(60)  # Wait longer on error

def start_follow_up_thread():
    t = Thread(target=follow_up_checker, daemon=True)
    t.start()


def save_csv_complete(csv_file_path):
    # Load the CSV into a DataFrame
    df = pd.read_csv(csv_file_path)
    
    # Drop rows where any of 'age', 'country', or 'interest' are missing (NaN or empty string)
    df_cleaned = df.dropna(subset=['age', 'country', 'interest'])

    # Also remove rows where fields are just empty strings after stripping spaces
    df_cleaned = df_cleaned[
        (df_cleaned['age'].astype(str).str.strip() != '') &
        (df_cleaned['country'].astype(str).str.strip() != '') &
        (df_cleaned['interest'].astype(str).str.strip() != '')
    ]
    
    # Save the cleaned DataFrame back to the same CSV
    df_cleaned.to_csv(csv_file_path, index=False)

    print("CSV saved!")

# --- New API Endpoints for Enhanced RAG System ---

@app.route('/api/rag_status', methods=['GET'])
def rag_status():
    """Get status of both RAG systems"""
    try:
        if dual_rag_system:
            status = dual_rag_system.get_system_status()
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
            "enhanced_system_active": dual_rag_system is not None
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
        
        if dual_rag_system:
            context = dual_rag_system.get_user_context(user_id, query)
        else:
            context = ""
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "context": context,
            "enhanced_system_active": dual_rag_system is not None
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
        
        if dual_rag_system:
            recommendations = dual_rag_system.get_product_recommendations(user_data, query)
        else:
            recommendations = "Enhanced recommendation system not available"
        
        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "user_data": user_data,
            "enhanced_system_active": dual_rag_system is not None
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
        if dual_rag_system:
            dual_rag_system.clear_user_data(user_id)
            message = f"Cleared all data for user {user_id}"
        else:
            message = f"Enhanced system not available - cannot clear data for user {user_id}"
        
        return jsonify({
            "success": True,
            "message": message,
            "enhanced_system_active": dual_rag_system is not None
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
        if dual_rag_system:
            user_context = dual_rag_system.get_user_context(user_id, message)
        
        details = state_manager.get_collected_details(user_id)
        
        return jsonify({
            "success": True,
            "response": response,
            "user_id": user_id,
            "session_id": session_id,
            "collected_details": details,
            "details_complete": state_manager.are_details_complete(user_id),
            "has_context": bool(user_context),
            "enhanced_system_active": dual_rag_system is not None
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
            "root_agent_available": root_agent is not None,
            "dual_rag_available": dual_rag_system is not None,
            "runner_available": runner is not None
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
    if dual_rag_system:
        try:
            print("[RAG] Initializing company documents...")
            # Force reload documents to ensure Word document is loaded
            dual_rag_system.company_docs_rag.load_company_documents("src/react_agent/docs")
            print("[RAG] Company documents loaded successfully")
            
            # Test the system
            test_suggestions = dual_rag_system.company_docs_rag.get_product_suggestions("technology", k=2)
            if test_suggestions:
                print(f"[RAG] ✅ System working - found {len(test_suggestions)} test suggestions")
            else:
                print("[RAG] ⚠️ System loaded but no suggestions found")
                
        except Exception as e:
            print(f"[RAG] ❌ Error initializing RAG system: {e}")
    else:
        print("[RAG] ⚠️ DualRAGSystem not available")

def create_app():
    """Application factory function"""
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
    
    # Initialize RAG system
    initialize_rag_system()
    
    # Start background threads
    start_follow_up_thread()
    
    return app

if __name__ == '__main__':
    # Create and configure the app
    app = create_app()
    
    # Check for required environment variables
    required_env_vars = ['GROQ_API_KEY', 'GEMINI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("The application will use fallback values, but functionality may be limited.")
    
    # Print startup information
    print("\n" + "="*50)
    print("🚀 SALES AGENT SYSTEM STARTING")
    print("="*50)
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"🔐 Secret Key: {'Set' if app.config['SECRET_KEY'] != 'your-secret-key-here' else 'Using default (please change)'}")
    print(f"🤖 Root Agent: {'Available' if root_agent else 'Not available'}")
    print(f"📚 RAG System: {'Available' if dual_rag_system else 'Not available'}")
    print(f"🔄 WebSocket: Enabled")
    print(f"📱 Real-time Chat: Enabled")
    print("="*50 + "\n")
    
    # Start the application with SocketIO
    try:
        socketio.run(
            app, 
            debug=True, 
            port=5000,
            host='0.0.0.0',
            use_reloader=False  # Disable reloader to prevent duplicate threads
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        raise
    
