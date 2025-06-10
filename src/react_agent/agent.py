import os
import requests
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables from .env or config.env files
env_files = ['.env', 'config.env']
env_loaded = False

for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"🔧 Agent loaded environment variables from: {env_file}")
        env_loaded = True
        break

if not env_loaded:
    print("⚠️  Agent: No .env or config.env file found, using system environment variables")

# Set protobuf implementation
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# Direct imports to avoid package issues
from react_agent.state import LeadInfo
from react_agent.conversation_memory import conversation_memory

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Display API key status
print(f"🔑 Agent GROQ_API_KEY: {'✅ Loaded' if GROQ_API_KEY and GROQ_API_KEY != 'your_groq_api_key_here' else '❌ Not set'}")

if not GROQ_API_KEY or GROQ_API_KEY == 'your_groq_api_key_here':
    print("⚠️  Agent: GROQ_API_KEY not found in environment variables!")
    print("📝 Please set it in your config.env file:")
    print("   GROQ_API_KEY=your_actual_api_key_here")
    # Set a fallback for testing
    GROQ_API_KEY = "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"
    print("⚠️  Using fallback API key for testing")

print(f"🤖 Multi-Agent system initialized with API key: {GROQ_API_KEY[:10]}...{GROQ_API_KEY[-10:]}")

class UserStateManager:
    """Manages isolated state for each user to prevent cross-contamination"""
    
    def __init__(self):
        self.user_states = {}  # user_id -> LeadInfo
        self.user_conversations = {}  # user_id -> conversation_history
        print("🔧 User State Manager initialized")
    
    def get_user_state(self, user_id: str) -> LeadInfo:
        """Get or create user state"""
        if user_id not in self.user_states:
            self.user_states[user_id] = LeadInfo()
            print(f"[STATE] Created new state for user {user_id}")
        return self.user_states[user_id]
    
    def update_user_state(self, user_id: str, lead_info: LeadInfo):
        """Update user state"""
        self.user_states[user_id] = lead_info
        print(f"[STATE] Updated state for user {user_id}: name={lead_info.name}, age={lead_info.age}, country={lead_info.country}, product={lead_info.product_interest}")
    
    def clear_user_state(self, user_id: str):
        """Clear user state"""
        if user_id in self.user_states:
            del self.user_states[user_id]
        if user_id in self.user_conversations:
            del self.user_conversations[user_id]
        print(f"[STATE] Cleared state for user {user_id}")
    
    def get_user_conversation_summary(self, user_id: str) -> str:
        """Get a clean summary of ONLY this user's conversations"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        
        conversations = self.user_conversations[user_id]
        if not conversations:
            return ""
        
        # Return only recent conversations for this specific user
        recent_convs = conversations[-3:] if len(conversations) > 3 else conversations
        summary = []
        for conv in recent_convs:
            summary.append(f"User: {conv['user_message']}")
            summary.append(f"Agent: {conv['agent_response']}")
        
        return "\n".join(summary)
    
    def add_user_conversation(self, user_id: str, user_message: str, agent_response: str):
        """Add conversation to user's isolated history"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        
        self.user_conversations[user_id].append({
            'user_message': user_message,
            'agent_response': agent_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 10 conversations per user to prevent memory bloat
        if len(self.user_conversations[user_id]) > 10:
            self.user_conversations[user_id] = self.user_conversations[user_id][-10:]

class BaseAgent:
    """Base agent class with common functionality"""
    
    def __init__(self, agent_name: str, description: str):
        self.agent_name = agent_name
        self.description = description
        self.headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
    
    def get_model_response(self, system_prompt: str, user_message: str, user_id: str = None, isolated_context: str = "") -> str:
        """Get response from the language model with proper user isolation"""
        try:
            # Use ONLY the isolated context for this specific user
            if isolated_context:
                system_prompt += f"\n\nPrevious conversation context for THIS USER ONLY:\n{isolated_context}"
            
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(GROQ_API_URL, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"Groq API error: {response.status_code} - {response.text}")
                return "I'm experiencing technical difficulties. Please try again."
                
        except Exception as e:
            print(f"Error in model response: {e}")
            return "I apologize for the technical issue. Please try again."

class GreetingAgent(BaseAgent):
    """Agent responsible for initial greeting and name collection"""
    
    def __init__(self):
        super().__init__("greeting_agent", "Handles initial greeting and name collection")
    
    def process(self, user_id: str, message: str, lead_info: LeadInfo, isolated_context: str = "") -> Dict[str, Any]:
        """Process greeting and name collection with isolated context"""
        print(f"[{self.agent_name}] Processing message for user {user_id}: {message}")
        
        # If we already have a name, move to next stage
        if lead_info.name:
            return {
                "response": f"Hello {lead_info.name}! Let me help you with the next step.",
                "next_agent": "info_collection_agent",
                "collection_stage": "age",
                "lead_info": lead_info
            }
        
        system_prompt = f"""You are a friendly greeting agent for a sales system. Your ONLY job is to:
1. Greet the user warmly
2. Ask for their name if not provided
3. Be conversational and friendly

IMPORTANT: You are speaking ONLY with user {user_id}. Do not reference any other users or conversations.
Current lead info for THIS USER: name={lead_info.name}, age={lead_info.age}, country={lead_info.country}, product={lead_info.product_interest}

If the user provides their name, respond with a warm acknowledgment.
If no name is provided, politely ask for it.
Keep responses short and friendly.

CRITICAL: Focus only on greeting and name collection. Do not mention other users."""
        
        response = self.get_model_response(system_prompt, message, user_id, isolated_context)
        
        # Extract name from the message
        name = self._extract_name(message)
        if name:
            lead_info.name = name
            return {
                "response": response,
                "next_agent": "info_collection_agent",
                "collection_stage": "age",
                "lead_info": lead_info
            }
        
        return {
            "response": response,
            "next_agent": "greeting_agent",
            "collection_stage": "name",
            "lead_info": lead_info
        }
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract name from user message"""
        patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"it's (\w+)",
            r"name is (\w+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower().strip())
            if match:
                potential_name = match.group(1).title()
                # Validate it's actually a name, not a common word
                common_words = ['hello', 'hi', 'there', 'good', 'nice', 'great', 'thanks', 'yes', 'no', 'the', 'a', 'an']
                if potential_name.lower() not in common_words and len(potential_name) > 1:
                    return potential_name
        
        # Check for single word responses that might be names
        words = text.strip().split()
        if len(words) == 1 and len(words[0]) > 2:
            potential_name = words[0].title()
            common_words = ['hello', 'hi', 'there', 'good', 'nice', 'great', 'thanks', 'yes', 'no', 'the', 'and', 'but']
            if potential_name.lower() not in common_words:
                return potential_name
        
        return None

class InfoCollectionAgent(BaseAgent):
    """Agent responsible for collecting age, country, and product interest"""
    
    def __init__(self):
        super().__init__("info_collection_agent", "Collects age, country, and product interest")
    
    def process(self, user_id: str, message: str, lead_info: LeadInfo, isolated_context: str = "") -> Dict[str, Any]:
        """Process information collection with isolated context"""
        print(f"[{self.agent_name}] Processing message for user {user_id}: {message}")
        
        # Determine what information we still need
        missing_fields = lead_info.get_missing_fields()
        
        if not missing_fields:
            return {
                "response": "Great! I have all your information. Let me review it with you.",
                "next_agent": "confirmation_agent",
                "collection_stage": "confirmation",
                "lead_info": lead_info
            }
        
        # Determine current focus
        current_focus = self._get_current_focus(missing_fields)
        
        system_prompt = f"""You are an information collection agent. Your job is to collect user information in this order:
1. Age
2. Country  
3. Product interest

IMPORTANT: You are speaking ONLY with user {user_id} named {lead_info.name or 'the user'}. Do not reference other users.
Current focus: {current_focus}
Lead info for THIS USER: name={lead_info.name}, age={lead_info.age}, country={lead_info.country}, product={lead_info.product_interest}
Missing fields: {missing_fields}

Ask for the {current_focus} in a friendly, conversational way.
If the user provides the information, acknowledge it warmly.

CRITICAL: Only reference information for THIS specific user. Do not mention other conversations."""
        
        response = self.get_model_response(system_prompt, message, user_id, isolated_context)
        
        # Extract information from the message
        self._extract_info(message, lead_info, current_focus)
        
        # Determine next stage
        new_missing = lead_info.get_missing_fields()
        
        if not new_missing:
            return {
                "response": response,
                "next_agent": "confirmation_agent",
                "collection_stage": "confirmation",
                "lead_info": lead_info
            }
        
        return {
            "response": response,
            "next_agent": "info_collection_agent",
            "collection_stage": self._get_next_stage(new_missing),
            "lead_info": lead_info
        }
    
    def _get_current_focus(self, missing_fields: List[str]) -> str:
        """Determine what information to focus on collecting next"""
        if "age" in missing_fields:
            return "age"
        elif "country" in missing_fields:
            return "country"
        elif "product interest" in missing_fields:
            return "product interest"
        return missing_fields[0] if missing_fields else "none"
    
    def _get_next_stage(self, missing_fields: List[str]) -> str:
        """Determine the next collection stage"""
        if "age" in missing_fields:
            return "age"
        elif "country" in missing_fields:
            return "country"
        elif "product interest" in missing_fields:
            return "product"
        return "confirmation"
    
    def _extract_info(self, text: str, lead_info: LeadInfo, focus: str):
        """Extract information based on current focus"""
        text_lower = text.lower().strip()
        
        if focus == "age":
            age_match = re.search(r'\b(\d{1,3})\b', text)
            if age_match:
                age = age_match.group(1)
                if 10 <= int(age) <= 120:
                    lead_info.age = age
        
        elif focus == "country":
            country_patterns = [
                r"from (\w+)",
                r"in (\w+)",
                r"live in (\w+)",
                r"country is (\w+)",
                r"i'm in (\w+)"
            ]
            for pattern in country_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    lead_info.country = match.group(1).title()
                    break
            
            if not lead_info.country and len(text.split()) == 1:
                lead_info.country = text.title()
        
        elif focus == "product interest":
            interest_patterns = [
                r"interested in (.+)",
                r"looking for (.+)",
                r"want (.+)",
                r"need (.+)",
                r"buying (.+)"
            ]
            for pattern in interest_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    lead_info.product_interest = match.group(1).strip()
                    break
            
            if not lead_info.product_interest:
                lead_info.product_interest = text.strip()

class ConfirmationAgent(BaseAgent):
    """Agent responsible for confirming collected information"""
    
    def __init__(self):
        super().__init__("confirmation_agent", "Handles information confirmation")
    
    def process(self, user_id: str, message: str, lead_info: LeadInfo, isolated_context: str = "") -> Dict[str, Any]:
        """Process information confirmation with isolated context"""
        print(f"[{self.agent_name}] Processing message for user {user_id}: {message}")
        
        if not lead_info.is_complete():
            return {
                "response": "I notice some information is missing. Let me collect that first.",
                "next_agent": "info_collection_agent",
                "collection_stage": "age",
                "lead_info": lead_info
            }
        
        # Check if user is confirming
        last_msg = message.lower().strip()
        if last_msg in ['confirm', 'yes', 'correct', 'right', 'ok', 'y']:
            return {
                "response": "Perfect! Thank you for confirming your information.",
                "next_agent": "completion_agent",
                "collection_stage": "complete",
                "lead_info": lead_info,
                "confirmed": True
            }
        
        # Generate confirmation message
        system_prompt = f"""You are a confirmation agent. Present the collected information clearly and ask for confirmation.

IMPORTANT: You are speaking ONLY with user {user_id}. This is THEIR information only.

Collected information for THIS USER:
- Name: {lead_info.name}
- Age: {lead_info.age}
- Country: {lead_info.country}
- Product Interest: {lead_info.product_interest}

Format this information nicely and ask the user to confirm by typing 'confirm' or 'yes'.
Be professional and clear. Do not reference other users or conversations."""
        
        response = self.get_model_response(system_prompt, message, user_id, isolated_context)
        
        return {
            "response": response,
            "next_agent": "confirmation_agent",
            "collection_stage": "confirmation",
            "lead_info": lead_info
        }

class CompletionAgent(BaseAgent):
    """Agent responsible for final completion"""
    
    def __init__(self):
        super().__init__("completion_agent", "Handles completion")
    
    def process(self, user_id: str, message: str, lead_info: LeadInfo, isolated_context: str = "") -> Dict[str, Any]:
        """Process completion with isolated context"""
        print(f"[{self.agent_name}] Processing message for user {user_id}: {message}")
        
        system_prompt = f"""You are a completion agent. Thank user {user_id} for providing their information and let them know it has been saved successfully. Ask if there's anything else you can help them with today.

Keep the response warm, professional, and brief. Do not reference other users."""
        
        response = self.get_model_response(system_prompt, message, user_id, isolated_context)
        
        return {
            "response": response,
            "next_agent": "completion_agent",
            "collection_stage": "complete",
            "lead_info": lead_info,
            "workflow_complete": True
        }

class MultiAgentSystem:
    """Multi-agent system coordinator with proper state management"""
    
    def __init__(self):
        self.agents = {
            "greeting_agent": GreetingAgent(),
            "info_collection_agent": InfoCollectionAgent(),
            "confirmation_agent": ConfirmationAgent(),
            "completion_agent": CompletionAgent()
        }
        self.state_manager = UserStateManager()
        print("🔧 Multi-agent system initialized with isolated state management")
    
    def process_conversation(self, user_id: str, message: str) -> str:
        """Process a conversation through the multi-agent workflow with proper user isolation"""
        try:
            # Get isolated user state
            lead_info = self.state_manager.get_user_state(user_id)
            
            # Get isolated conversation context for THIS USER ONLY
            isolated_context = self.state_manager.get_user_conversation_summary(user_id)
            
            # Determine current agent based on lead info state
            current_agent_name = self._determine_current_agent(lead_info)
            current_agent = self.agents[current_agent_name]
            
            # Process with current agent using isolated context
            result = current_agent.process(user_id, message, lead_info, isolated_context)
            
            # Update user state
            self.state_manager.update_user_state(user_id, result["lead_info"])
            
            # Store conversation in user's isolated history
            self.state_manager.add_user_conversation(user_id, message, result["response"])
            
            # Also store in the global conversation memory for persistence
            conversation_memory.store_conversation(
                user_id=user_id,
                user_message=message,
                agent_response=result["response"],
                context={
                    "timestamp": datetime.now().isoformat(),
                    "current_agent": current_agent_name,
                    "collection_stage": result.get("collection_stage", "unknown"),
                    "lead_info": result["lead_info"].__dict__
                }
            )
            
            return result["response"]
            
        except Exception as e:
            print(f"Error in multi-agent processing for user {user_id}: {e}")
            return "I'm experiencing technical difficulties. Please try again later."
    
    def _determine_current_agent(self, lead_info: LeadInfo) -> str:
        """Determine which agent should handle the conversation"""
        if not lead_info.name:
            return "greeting_agent"
        elif not lead_info.is_complete():
            return "info_collection_agent"
        else:
            return "confirmation_agent"
    
    def get_lead_info(self, user_id: str) -> Dict[str, Any]:
        """Get current lead information for a user"""
        lead_info = self.state_manager.get_user_state(user_id)
        return {
            "name": lead_info.name,
            "age": lead_info.age,
            "country": lead_info.country,
            "product_interest": lead_info.product_interest,
            "status": lead_info.status,
            "is_complete": lead_info.is_complete(),
            "lead_info": lead_info.__dict__
        }
    
    def clear_user_memory(self, user_id: str):
        """Clear conversation memory for a user"""
        self.state_manager.clear_user_state(user_id)
        conversation_memory.clear_user_conversations(user_id)

class SalesAgent:
    """Enhanced sales agent using multi-agent system"""
    
    def __init__(self):
        self.multi_agent = MultiAgentSystem()
        print("🚀 Sales Agent with Multi-Agent system ready!")
    
    def process_lead_conversation(self, lead_id: str, message: str) -> str:
        """Process a lead conversation using the multi-agent system"""
        return self.multi_agent.process_conversation(lead_id, message)
    
    def get_lead_status(self, lead_id: str) -> Dict[str, Any]:
        """Get the current status of a lead"""
        return self.multi_agent.get_lead_info(lead_id)
    
    def get_lead_history(self, lead_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a lead"""
        try:
            history = conversation_memory.get_user_conversation_history(lead_id, limit=20)
            return [{
                "timestamp": conv.timestamp.isoformat(),
                "user_message": conv.user_message,
                "agent_response": conv.agent_response,
                "context": conv.context
            } for conv in history]
        except Exception as e:
            print(f"Error getting lead history: {e}")
            return []

# Legacy wrapper for backward compatibility
class LangGraphAgent:
    """Legacy wrapper for backward compatibility"""
    
    def __init__(self):
        self.sales_agent = SalesAgent()
    
    def chat(self, user_id: str, message: str, session_id: str = None) -> str:
        """Chat method for backward compatibility"""
        return self.sales_agent.process_lead_conversation(user_id, message)
    
    def clear_user_memory(self, user_id: str):
        """Clear user memory for backward compatibility"""
        self.sales_agent.multi_agent.clear_user_memory(user_id)

# Simple fallback agent using direct Groq API calls
class SimpleGroqAgent:
    """Simple agent using direct Groq API calls as fallback"""
    
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
    
    def chat(self, user_id: str, message: str, session_id: str = None) -> str:
        """Simple chat using Groq API"""
        try:
            context = conversation_memory.get_conversation_context(user_id, message, max_context_length=1000)
            
            system_prompt = f"""You are a sales assistant helping to collect lead information. 
            Your goal is to collect: name, age, country, and product interest.
            
            Be friendly, conversational, and guide the user through providing this information.
            
            {f"Previous context: {context}" if context else ""}"""
            
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(GROQ_API_URL, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"]
                
                conversation_memory.store_conversation(
                    user_id=user_id,
                    user_message=message,
                    agent_response=ai_response,
                    context={"agent_type": "simple_groq", "timestamp": datetime.now().isoformat()}
                )
                
                return ai_response
            else:
                print(f"Groq API error: {response.status_code} - {response.text}")
                return "I'm experiencing technical difficulties. Please try again."
                
        except Exception as e:
            print(f"Error in SimpleGroqAgent: {e}")
            return "I apologize for the technical issue. Please try again."

# Global instances
try:
    # Try to use the multi-agent system
    sales_agent = SalesAgent()
    langgraph_agent = LangGraphAgent()
    print("✅ Multi-agent system loaded successfully")
except Exception as e:
    print(f"⚠️  Multi-agent system failed to load: {e}")
    print("🔄 Falling back to simple agent")
    # Fallback to simple agent
    simple_agent = SimpleGroqAgent()
    sales_agent = simple_agent
    langgraph_agent = simple_agent

# Backward compatibility function
def call_agent_sync(user_id: str, message: str) -> str:
    """Backward compatibility function"""
    return sales_agent.chat(user_id, message) if hasattr(sales_agent, 'chat') else sales_agent.process_lead_conversation(user_id, message) 