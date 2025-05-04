import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import asyncio
from agent import root_agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import pandas as pd
import csv
import time
import re
from threading import Thread

# --- Environment & API Key ---
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "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")

# --- CSV Setup for leads ---
CSV_FILE = "leads.csv"
CSV_COLUMNS = ["lead_id", "name", "age", "country", "interest", "status"]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

# --- Flask app ---
app = Flask(__name__)

# --- Global variables ---
user_input_counter = 0
follow_up_messages = {}  

# --- ADK Session & Runner Setup ---
APP_NAME = "sales_agent_app"
USER_ID = "user_1"
session_service = InMemorySessionService()
# We'll create sessions dynamically per lead

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service
)

# --- Helper: Sync wrapper around async runner ---
async def _run_agent_async(conversation_id: str, text: str) -> str:
    content = types.Content(role='user', parts=[types.Part(text=text)])
    final_text = ""
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
    return final_text

def call_agent_sync(conversation_id: str, text: str) -> str:
    # Create session if not exists
    try:
        session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=conversation_id)
    except KeyError:
        session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=conversation_id)
    return asyncio.run(_run_agent_async(conversation_id, text))

# --- Memory to store conversation details ---
conversation_details = {}  # Will store lead details by lead_id

# --- Helper to save lead data ---
def save_to_csv(lead_id, name, age, country, interest, status):
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow({
            "lead_id": lead_id,
            "name": name,
            "age": age,
            "country": country,
            "interest": interest,
            "status": status
        })

# --- Helper to extract user details from a structured response ---
def extract_user_details(message):
    details = {
        'name': None,
        'age': None,
        'country': None,
        'interest': None
    }
    
    # Extract details using more robust regex patterns
    name_match = re.search(r'(?:your|the|their|customer\'?s?)\s*name:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    age_match = re.search(r'(?:your|the|their|customer\'?s?)\s*age:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    country_match = re.search(r'(?:your|the|their|customer\'?s?)\s*country:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    interest_match = re.search(r'(?:product\s*)?interest:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    
    # Fall back to simpler patterns if the more specific ones don't match
    if not name_match:
        name_match = re.search(r'name:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r'age:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    if not country_match:
        country_match = re.search(r'country:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    
    # Enhanced patterns for product interest - try multiple approaches
    if not interest_match:
        # Look for standard product interest format
        interest_match = re.search(r'product\s+interest:?\s*([^\n\.,]+)', message, re.IGNORECASE)
    if not interest_match:
        # Check for interest expressed as phrases
        interest_phrases = [
            r'interested in(?:\s+purchasing)?:?\s*([^\n\.,]+)',
            r'looking (?:to buy|for|to purchase):?\s*([^\n\.,]+)',
            r'want to (?:buy|purchase):?\s*([^\n\.,]+)',
            r'would like to (?:buy|purchase|get):?\s*([^\n\.,]+)',
            r'seeking to (?:buy|purchase):?\s*([^\n\.,]+)',
            r'shopping for:?\s*([^\n\.,]+)'
        ]
        for phrase in interest_phrases:
            match = re.search(phrase, message, re.IGNORECASE)
            if match:
                interest_match = match
                break
    
    # Look for product-specific keywords if still no match
    if not interest_match:
        product_keywords = [
            r'(?:laptop|computer|pc|desktop):?\s*([^\n\.,]+)?',
            r'(?:phone|smartphone|mobile):?\s*([^\n\.,]+)?',
            r'(?:tablet|ipad):?\s*([^\n\.,]+)?',
            r'(?:headphone|earphone|earbud):?\s*([^\n\.,]+)?',
            r'(?:camera|webcam):?\s*([^\n\.,]+)?',
            r'(?:tv|television|monitor|display):?\s*([^\n\.,]+)?',
        ]
        for keyword in product_keywords:
            match = re.search(keyword, message, re.IGNORECASE)
            if match:
                # If there's a capture group with content, use it, otherwise use the keyword itself
                interest = match.group(1).strip() if match.group(1) and match.group(1).strip() else keyword.split('|')[0].replace('(?:', '')
                details['interest'] = interest
                break
    
    if name_match:
        details['name'] = name_match.group(1).strip()
    if age_match:
        details['age'] = age_match.group(1).strip()
    if country_match:
        details['country'] = country_match.group(1).strip()
    if interest_match and not details['interest']:  # Only set if not already set by product keywords
        details['interest'] = interest_match.group(1).strip()
    
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

@app.route('/chat', methods=['POST'])
def chat():
    lead_id = request.args.get('lead_id')
    if not lead_id:
        return "Missing lead_id parameter", 400
    
    message = request.json.get('message')
    if not message:
        return "Missing message in request body", 400
    
    # Increment the counter when a user sends a message
    global user_input_counter
    user_input_counter += 1
    print(f"[CHAT] User message received. Counter incremented to {user_input_counter}")
    
    # Check if this is a confirmation message
    if message.lower().strip() == 'confirm':
        if lead_id in conversation_details and 'last_details_message' in conversation_details[lead_id]:
            previous_response = conversation_details[lead_id]['last_details_message']
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
                agent_reply = "Thank you for confirming your details! Your information has been saved successfully. How else can I assist you today?"
                return {"response": agent_reply}
    
    # Send message to agent for normal conversation
    agent_reply = call_agent_sync(lead_id, message)
    
    # Check if the agent response contains user details in a structured format
    details = extract_user_details(agent_reply)
    if are_details_complete(details):
        # Store the formatted details for later confirmation
        if lead_id not in conversation_details:
            conversation_details[lead_id] = {}
        conversation_details[lead_id]['last_details_message'] = agent_reply
        
        # Replace agent response with formatted confirmation prompt
        agent_reply = format_details_for_confirmation(details)
    
    return {"response": agent_reply}


@app.route('/check_follow_up', methods=['GET'])
def check_follow_up():
    save_csv_complete("leads.csv")
    lead_id = request.args.get('lead_id')
    if not lead_id:
        return {"has_follow_up": False}
    
    if lead_id in follow_up_messages and follow_up_messages[lead_id]:
        # Get the first message from the list
        follow_up = follow_up_messages[lead_id].pop(0)
        # If the list is now empty, clean up
        if not follow_up_messages[lead_id]:
            del follow_up_messages[lead_id]
        return {"has_follow_up": True, "message": follow_up}
    
    save_csv_complete("leads.csv")
    return {"has_follow_up": False}

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    save_csv_complete("leads.csv")
    lead_id = request.form.get('lead_id')
    name = request.form.get('name')
    if lead_id and name:
        # Initialize session
        session_service.create_session(
            app_name=APP_NAME, 
            user_id=USER_ID, 
            session_id=lead_id
        )
        
        # Initialize conversation details
        conversation_details[lead_id] = {
            'last_details_message': ''
        }
        
        # Greet lead via agent with VERY explicit instructions
        prompt = f"""Hello {name}, I'm your sales assistant. I need to collect some information from you in a specific order.

        First, let me confirm your name - are you {name}?

        After you confirm your name, I'll ask for:
        1. Your age
        2. Your country of residence
        3. And FINALLY, I'll ask what specific products you're interested in purchasing

        Let's start with confirming your name. Are you {name}?"""
        
        response = call_agent_sync(lead_id, prompt)
        # Optionally store initial status
        save_to_csv(lead_id, name, '', '', '', 'started')
        return redirect(url_for('conversation', lead_id=lead_id))
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
                    agent_reply = "Thank you for confirming your details! Your information has been saved successfully. How else can I assist you today?"
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
    welcome = "Hello! I'm ready to assist you. What would you like to know about our products?"
    save_csv_complete("leads.csv")
    return render_template('conversation.html', lead_id=lead_id, response=welcome)



# --- Follow-up checker ---
def follow_up_checker():
    save_csv_complete("leads.csv")
    global user_input_counter, follow_up_messages
    previous_count = user_input_counter
    last_follow_up_time = time.time()
    last_log_time = time.time()
    
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        current_count = user_input_counter
        current_time = time.time()
        
        # Only start checking after the first user message
        if current_count > 0:
            # If the counter hasn't changed for 30 seconds, send follow-up
            if current_count == previous_count and (current_time - last_follow_up_time) >= 30:
                print("\n" + "="*30)
                print("INACTIVITY DETECTED: Sending follow-up messages...")
                print("="*30 + "\n")
                
                # Send follow-up to all active conversations
                for lead_id in conversation_details:
                    try:
                        # Create the follow-up message
                        follow_up_message = "Just checking in to see if you're still interested. Let me know when you're ready to continue."
                        
                        # Send the follow-up message directly to the agent
                        # This ensures it appears in the conversation history
                        agent_response = call_agent_sync(lead_id, follow_up_message)
                        
                        # Store the follow-up message in the conversation details
                        if lead_id not in conversation_details:
                            conversation_details[lead_id] = {}
                        
                        # Add the follow-up message to the conversation history
                        if 'messages' not in conversation_details[lead_id]:
                            conversation_details[lead_id]['messages'] = []
                        
                        # Add both the follow-up message and the agent's response
                        conversation_details[lead_id]['messages'].append({
                            'role': 'system',
                            'content': follow_up_message
                        })
                        
                        if agent_response:
                            conversation_details[lead_id]['messages'].append({
                                'role': 'assistant',
                                'content': agent_response
                            })
                        
                        # Store the follow-up message for the frontend to display
                        if lead_id not in follow_up_messages:
                            follow_up_messages[lead_id] = []
                        follow_up_messages[lead_id].append(agent_response or follow_up_message)
                        
                        # Increment the counter for follow-up messages
                        user_input_counter += 1
                        print(f"\n[FOLLOW-UP] Message sent for lead_id: {lead_id}")
                        print(f"[COUNTER] Incremented from {previous_count} to {user_input_counter}")
                        
                        # Update the last follow-up time to prevent continuous follow-ups
                        last_follow_up_time = current_time
                    except Exception as e:
                        print(f"[ERROR] Failed to send follow-up: {str(e)}")
            elif current_count != previous_count:
                print(f"[ACTIVITY] User activity detected. Counter changed from {previous_count} to {current_count}")
                # Reset the follow-up timer when user is active
                last_follow_up_time = current_time
                
                # Only log activity check every 30 seconds to reduce console spam
                if (current_time - last_log_time) >= 30:
                    print(f"[CHECK] Monitoring user activity. Current counter: {current_count}")
                    last_log_time = current_time
        
        # Update previous count for next check
        previous_count = current_count

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



if __name__ == '__main__':
    start_follow_up_thread()
    app.run(debug=True, port=5000)
    
