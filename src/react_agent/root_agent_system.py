"""
Root Agent System with Google ADK Integration
Sequential workflow: Greeting → Name → Age → Country → Interest → Confirmation
"""

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# Try to import Google ADK, fall back to mock classes if not available
try:
    from google.generativeai import types
    from google.adk.core import Agent
    from google.adk.agents import SpecificAgent, SimpleSpecificAgent
    from google.adk.core.state import StateManager
    GOOGLE_ADK_AVAILABLE = True
except ImportError:
    print("[FALLBACK] Google ADK not available, using fallback implementations")
    GOOGLE_ADK_AVAILABLE = False
    
    # Mock classes for fallback
    class types:
        class Content:
            def __init__(self, role=None, parts=None):
                self.role = role
                self.parts = parts or []
        
        class Part:
            def __init__(self, text=""):
                self.text = text
        
        class Context:
            def __init__(self, user_id="", session_id=""):
                self.user_id = user_id
                self.session_id = session_id
    
    class Agent:
        def __init__(self):
            pass
        
        async def respond(self, content, context):
            return types.Content(parts=[types.Part(text="Fallback response")])

try:
    from enhanced_rag_system import dual_rag_system
except ImportError:
    print("[WARNING] Could not import dual_rag_system, some features will be limited")
    dual_rag_system = None

from react_agent.state import LeadInfo

class ConversationStage(Enum):
    GREETING = "greeting"
    NAME_COLLECTION = "name_collection"
    AGE_COLLECTION = "age_collection"
    COUNTRY_COLLECTION = "country_collection"
    INTEREST_COLLECTION = "interest_collection"
    CONFIRMATION = "confirmation"
    COMPLETE = "complete"

@dataclass
class UserSessionState:
    """State for each user session"""
    user_id: str
    session_id: str
    current_stage: ConversationStage = ConversationStage.GREETING
    lead_info: LeadInfo = field(default_factory=LeadInfo)
    interaction_count: int = 0
    last_message: str = ""
    context_summary: str = ""

class RootControlAgent(Agent):
    """Root controlling agent that manages the conversation flow"""
    
    def __init__(self):
        super().__init__()
        self.user_sessions: Dict[str, UserSessionState] = {}
        self.stage_agents = {
            ConversationStage.GREETING: GreetingAgent(),
            ConversationStage.NAME_COLLECTION: NameCollectionAgent(),
            ConversationStage.AGE_COLLECTION: AgeCollectionAgent(),
            ConversationStage.COUNTRY_COLLECTION: CountryCollectionAgent(),
            ConversationStage.INTEREST_COLLECTION: InterestCollectionAgent(),
            ConversationStage.CONFIRMATION: ConfirmationAgent()
        }
    
    def get_or_create_session(self, user_id: str, session_id: str) -> UserSessionState:
        """Get or create user session state"""
        session_key = f"{user_id}_{session_id}"
        if session_key not in self.user_sessions:
            self.user_sessions[session_key] = UserSessionState(
                user_id=user_id,
                session_id=session_id
            )
        return self.user_sessions[session_key]
    
    async def respond(self, content: types.Content, context: types.Context) -> types.Content:
        """Main response handler"""
        user_id = context.user_id
        session_id = context.session_id
        user_message = content.parts[0].text if content.parts else ""
        
        # Get user session
        session = self.get_or_create_session(user_id, session_id)
        session.last_message = user_message
        session.interaction_count += 1
        
        # Get user context from chat history RAG
        user_context = dual_rag_system.get_user_context(user_id, user_message)
        session.context_summary = user_context
        
        # Determine current agent based on stage
        current_agent = self.stage_agents.get(session.current_stage)
        if not current_agent:
            # Fallback to greeting if stage is unknown
            current_agent = self.stage_agents[ConversationStage.GREETING]
            session.current_stage = ConversationStage.GREETING
        
        # Process with current agent
        result = await current_agent.process(session, user_message, user_context)
        
        # Update session state
        session.current_stage = result.get("next_stage", session.current_stage)
        if "lead_info" in result:
            session.lead_info = result["lead_info"]
        
        # Store conversation in RAG system
        agent_response = result.get("response", "")
        dual_rag_system.store_user_conversation(
            user_id=user_id,
            user_message=user_message,
            agent_response=agent_response,
            stage=session.current_stage.value,
            metadata={
                "interaction_count": session.interaction_count,
                "lead_info": session.lead_info.__dict__
            }
        )
        
        # Check if we need product recommendations
        if session.current_stage == ConversationStage.COMPLETE and session.lead_info.is_complete():
            # Generate product recommendations
            recommendations = dual_rag_system.get_product_recommendations(
                user_data=session.lead_info.__dict__,
                query="product recommendation suggestions"
            )
            
            if recommendations:
                agent_response += f"\n\nBased on your interests, here are some personalized recommendations:\n{recommendations}"
        
        return types.Content(parts=[types.Part(text=agent_response)])

class BaseStageAgent:
    """Base class for stage-specific agents"""
    
    def __init__(self, stage_name: str):
        self.stage_name = stage_name
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        """Process user message for this stage"""
        raise NotImplementedError
    
    def extract_info_from_message(self, message: str, field_type: str) -> Optional[str]:
        """Extract specific information from user message"""
        import re
        
        message_lower = message.lower().strip()
        
        if field_type == "name":
            patterns = [
                r"my name is (\w+)",
                r"i'm (\w+)",
                r"i am (\w+)",
                r"call me (\w+)",
                r"it's (\w+)",
                r"name is (\w+)"
            ]
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    return match.group(1).title()
            
            # Single word response
            words = message.strip().split()
            if len(words) == 1 and len(words[0]) > 2:
                return words[0].title()
        
        elif field_type == "age":
            age_match = re.search(r'\b(\d{1,3})\b', message)
            if age_match:
                age = int(age_match.group(1))
                if 10 <= age <= 120:
                    return str(age)
        
        elif field_type == "country":
            patterns = [
                r"from (\w+)",
                r"in (\w+)",
                r"live in (\w+)",
                r"country is (\w+)",
                r"i'm in (\w+)"
            ]
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    return match.group(1).title()
            
            # Single word country response
            if len(message.split()) == 1:
                return message.title()
        
        elif field_type == "interest":
            patterns = [
                r"interested in (.+)",
                r"looking for (.+)",
                r"want (.+)",
                r"need (.+)",
                r"buying (.+)"
            ]
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    return match.group(1).strip()
            
            # Use whole message as interest if no pattern matches
            return message.strip()
        
        return None

class GreetingAgent(BaseStageAgent):
    """Agent for initial greeting"""
    
    def __init__(self):
        super().__init__("greeting")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        if session.interaction_count == 1:
            # First interaction
            response = f"Hello! Welcome to our sales assistant. I'm here to help you find the perfect products for your needs. To get started, could you please tell me your name?"
            next_stage = ConversationStage.NAME_COLLECTION
        else:
            # Subsequent interactions in greeting stage
            response = "I'd be happy to help you! Let's start by getting to know you. What's your name?"
            next_stage = ConversationStage.NAME_COLLECTION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

class NameCollectionAgent(BaseStageAgent):
    """Agent for collecting user name"""
    
    def __init__(self):
        super().__init__("name_collection")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        # Try to extract name
        name = self.extract_info_from_message(user_message, "name")
        
        if name:
            session.lead_info.name = name
            response = f"Nice to meet you, {name}! Now, could you please tell me your age?"
            next_stage = ConversationStage.AGE_COLLECTION
        else:
            response = "I'd love to know your name so I can personalize our conversation. Could you please tell me what I should call you?"
            next_stage = ConversationStage.NAME_COLLECTION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

class AgeCollectionAgent(BaseStageAgent):
    """Agent for collecting user age"""
    
    def __init__(self):
        super().__init__("age_collection")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        # Try to extract age
        age = self.extract_info_from_message(user_message, "age")
        
        if age:
            session.lead_info.age = age
            response = f"Thank you! And which country are you from, {session.lead_info.name}?"
            next_stage = ConversationStage.COUNTRY_COLLECTION
        else:
            response = "Could you please tell me your age? This helps me recommend products that are most suitable for you."
            next_stage = ConversationStage.AGE_COLLECTION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

class CountryCollectionAgent(BaseStageAgent):
    """Agent for collecting user country"""
    
    def __init__(self):
        super().__init__("country_collection")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        # Try to extract country
        country = self.extract_info_from_message(user_message, "country")
        
        if country:
            session.lead_info.country = country
            response = f"Great! Now, what kind of products are you interested in or looking to purchase?"
            next_stage = ConversationStage.INTEREST_COLLECTION
        else:
            response = "Which country are you from? This helps me understand regional preferences and availability."
            next_stage = ConversationStage.COUNTRY_COLLECTION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

class InterestCollectionAgent(BaseStageAgent):
    """Agent for collecting product interest"""
    
    def __init__(self):
        super().__init__("interest_collection")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        # Try to extract interest
        interest = self.extract_info_from_message(user_message, "interest")
        
        if interest:
            session.lead_info.product_interest = interest
            response = f"Perfect! Let me summarize your information:\n\n"
            response += f"Name: {session.lead_info.name}\n"
            response += f"Age: {session.lead_info.age}\n"
            response += f"Country: {session.lead_info.country}\n"
            response += f"Product Interest: {session.lead_info.product_interest}\n\n"
            response += "Is this information correct? Please type 'confirm' if everything looks good, or let me know what needs to be corrected."
            next_stage = ConversationStage.CONFIRMATION
        else:
            response = "What type of products are you interested in purchasing? For example: laptops, smartphones, headphones, etc."
            next_stage = ConversationStage.INTEREST_COLLECTION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

class ConfirmationAgent(BaseStageAgent):
    """Agent for confirming collected information"""
    
    def __init__(self):
        super().__init__("confirmation")
    
    async def process(self, session: UserSessionState, user_message: str, user_context: str) -> Dict[str, Any]:
        message_lower = user_message.lower().strip()
        
        if message_lower in ['confirm', 'yes', 'correct', 'right', 'ok', 'y', 'confirmed']:
            session.lead_info.status = "confirmed"
            response = f"Excellent! Thank you for confirming your information, {session.lead_info.name}. "
            response += "I'll now prepare some personalized product recommendations for you based on your interests."
            next_stage = ConversationStage.COMPLETE
        else:
            # User wants to make corrections
            response = "No problem! What would you like to correct? Please tell me the updated information and I'll make the necessary changes."
            # Stay in confirmation stage to handle corrections
            next_stage = ConversationStage.CONFIRMATION
        
        return {
            "response": response,
            "next_stage": next_stage,
            "lead_info": session.lead_info
        }

# Create root agent instance
root_agent = RootControlAgent() 