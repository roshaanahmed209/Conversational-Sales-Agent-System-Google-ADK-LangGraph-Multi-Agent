from datetime import datetime, timezone
from typing import Dict, List, Literal, cast, Optional
import re
import json

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from react_agent.configuration import Configuration
from react_agent.state import InputState, State, LeadInfo
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model, log_step
from react_agent.conversation_memory import conversation_memory

# Load environment variables
load_dotenv()

# === SPECIALIZED AGENT CLASSES ===

class BaseAgent:
    """Base agent class with common functionality"""
    
    def __init__(self, agent_name: str, description: str):
        self.agent_name = agent_name
        self.description = description
        self.configuration = Configuration.from_context()
    
    async def get_model_response(self, system_prompt: str, messages: List[BaseMessage], user_id: str = None, rag_context: str = "") -> AIMessage:
        """Get response from the language model"""
        model = load_chat_model(self.configuration.model)
        
        # Add RAG context if available
        if rag_context:
            system_prompt += f"\n\nRelevant Knowledge Base Information:\n{rag_context}"
        
        # Add conversation context if available
        if user_id:
            context = conversation_memory.get_conversation_context(user_id, messages[-1].content if messages else "", max_context_length=1000)
            if context:
                system_prompt += f"\n\nPrevious conversation context:\n{context}"
        
        system_msg = SystemMessage(content=system_prompt)
        all_messages = [system_msg] + list(messages)
        
        response = cast(AIMessage, await model.ainvoke(all_messages))
        return response

class GreetingAgent(BaseAgent):
    """Agent responsible for initial greeting and name collection"""
    
    def __init__(self):
        super().__init__("greeting_agent", "Handles initial greeting and name collection")
    
    async def process(self, state: State) -> dict:
        """Process greeting and name collection"""
        log_step(state, f"{self.agent_name}")
        
        # If we already have a name, move to next stage
        if state.lead_info.name:
            return {
                "next_agent": "info_collection_agent",
                "collection_stage": "age",
                "agent_handoff_message": f"Name already collected: {state.lead_info.name}. Moving to age collection."
            }
        
        system_prompt = f"""You are a friendly greeting agent for a sales system. Your ONLY job is to:
1. Greet the user warmly
2. Ask for their name if not provided
3. Extract the name from their response

Current stage: {state.collection_stage}
Lead info so far: {state.lead_info.__dict__}

If the user provides their name, respond with a warm acknowledgment and ask for their age.
If no name is provided, politely ask for it.
Keep responses short and friendly.

IMPORTANT: You should extract and remember any name mentioned in the conversation."""
        
        response = await self.get_model_response(system_prompt, state.messages, state.user_id, state.relevant_context)
        
        # Extract name from the latest human message
        human_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
        if human_messages:
            last_msg = human_messages[-1].content
            name = self._extract_name(last_msg)
            if name:
                state.lead_info.name = name
                return {
                    "messages": [response],
                    "next_agent": "info_collection_agent",
                    "collection_stage": "age",
                    "lead_info": state.lead_info,
                    "agent_handoff_message": f"Name collected: {name}. Moving to age collection."
                }
        
        return {
            "messages": [response],
            "collection_stage": "name"
        }
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract name from user message"""
        # Simple name extraction patterns
        patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"it's (\w+)",
            r"^(\w+)$"  # Single word response
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower().strip())
            if match:
                return match.group(1).title()
        
        return None

class InfoCollectionAgent(BaseAgent):
    """Agent responsible for collecting age, country, and product interest"""
    
    def __init__(self):
        super().__init__("info_collection_agent", "Collects age, country, and product interest")
    
    async def process(self, state: State) -> dict:
        """Process information collection"""
        log_step(state, f"{self.agent_name}")
        
        # Determine what information we still need
        missing_fields = state.lead_info.get_missing_fields()
        
        if not missing_fields:
            return {
                "next_agent": "confirmation_agent",
                "collection_stage": "confirmation",
                "agent_handoff_message": "All information collected. Moving to confirmation."
            }
        
        # Determine current focus based on collection stage
        current_focus = self._get_current_focus(state.collection_stage, missing_fields)
        
        system_prompt = f"""You are an information collection agent. Your job is to collect user information in this order:
1. Age
2. Country
3. Product interest

Current focus: {current_focus}
Collection stage: {state.collection_stage}
Lead info so far: {state.lead_info.__dict__}
Missing fields: {missing_fields}

Ask for the {current_focus} in a friendly, conversational way.
If the user provides the information, acknowledge it and move to the next field.
Extract any relevant information from their response.

Keep responses short and focused on collecting the specific information needed."""
        
        response = await self.get_model_response(system_prompt, state.messages, state.user_id, state.relevant_context)
        
        # Extract information from the latest human message
        human_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
        if human_messages:
            last_msg = human_messages[-1].content
            self._extract_info(last_msg, state.lead_info, current_focus)
        
        # Determine next stage
        new_missing = state.lead_info.get_missing_fields()
        next_stage = self._get_next_stage(new_missing)
        
        # Check if ready for confirmation
        if not new_missing:
            return {
                "messages": [response],
                "next_agent": "confirmation_agent",
                "collection_stage": "confirmation",
                "lead_info": state.lead_info,
                "agent_handoff_message": "All information collected. Moving to confirmation."
            }
        
        return {
            "messages": [response],
            "collection_stage": next_stage,
            "lead_info": state.lead_info
        }
    
    def _get_current_focus(self, stage: str, missing_fields: List[str]) -> str:
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
                if 10 <= int(age) <= 120:  # Reasonable age range
                    lead_info.age = age
        
        elif focus == "country":
            # Simple country extraction - could be enhanced with a country list
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
            
            # Single word country response
            if not lead_info.country and len(text.split()) == 1:
                lead_info.country = text.title()
        
        elif focus == "product interest":
            # Extract product interest
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
            
            # If no pattern matches, use the whole response as product interest
            if not lead_info.product_interest:
                lead_info.product_interest = text.strip()

class ConfirmationAgent(BaseAgent):
    """Agent responsible for confirming collected information"""
    
    def __init__(self):
        super().__init__("confirmation_agent", "Handles information confirmation")
    
    async def process(self, state: State) -> dict:
        """Process information confirmation"""
        log_step(state, f"{self.agent_name}")
        
        if not state.lead_info.is_complete():
            return {
                "next_agent": "info_collection_agent",
                "collection_stage": "age",
                "agent_handoff_message": "Information incomplete. Returning to collection."
            }
        
        # Check if user is confirming
        human_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
        if human_messages:
            last_msg = human_messages[-1].content.lower().strip()
            if last_msg in ['confirm', 'yes', 'correct', 'right', 'ok']:
                return {
                    "next_agent": "completion_agent",
                    "collection_stage": "complete",
                    "requires_confirmation": True,
                    "lead_info": state.lead_info,
                    "agent_handoff_message": "Information confirmed by user."
                }
        
        # Generate confirmation message
        system_prompt = f"""You are a confirmation agent. Present the collected information clearly and ask for confirmation.

Collected information:
- Name: {state.lead_info.name}
- Age: {state.lead_info.age}
- Country: {state.lead_info.country}
- Product Interest: {state.lead_info.product_interest}

Format this information nicely and ask the user to confirm by typing 'confirm' or 'yes'.
Be professional and clear."""
        
        response = await self.get_model_response(system_prompt, state.messages, state.user_id, state.relevant_context)
        
        return {
            "messages": [response],
            "confirmation_pending": True,
            "collection_stage": "confirmation"
        }

class CompletionAgent(BaseAgent):
    """Agent responsible for final completion and cleanup"""
    
    def __init__(self):
        super().__init__("completion_agent", "Handles completion and cleanup")
    
    async def process(self, state: State) -> dict:
        """Process completion and cleanup"""
        log_step(state, f"{self.agent_name}")
        
        system_prompt = """You are a completion agent. Thank the user for providing their information and let them know it has been saved successfully. Ask if there's anything else you can help them with today.

Keep the response warm, professional, and brief."""
        
        response = await self.get_model_response(system_prompt, state.messages, state.user_id, state.relevant_context)
        
        return {
            "messages": [response],
            "workflow_complete": True,
            "collection_stage": "complete",
            "lead_info": state.lead_info
        }

# === AGENT INSTANCES ===
greeting_agent = GreetingAgent()
info_collection_agent = InfoCollectionAgent()
confirmation_agent = ConfirmationAgent()
completion_agent = CompletionAgent()

# === LANGGRAPH NODES ===

async def initialize_state(input_state: InputState) -> dict:
    """Initialize the graph state from input state with RAG context"""
    from langchain_core.messages import HumanMessage
    
    # Convert InputState to State dict
    state_dict = {
        "user_id": input_state.user_id,
        "current_query": input_state.message,
        "retrieved_documents": input_state.rag_context,
        "messages": [HumanMessage(content=input_state.message)] if input_state.message else [],
    }
    
    # Add RAG context to relevant_context if available
    if input_state.rag_context:
        rag_text = "\n".join([doc.get('content', '') for doc in input_state.rag_context])
        state_dict["relevant_context"] = f"Relevant information from knowledge base:\n{rag_text}\n\n"
        print(f"[GRAPH] Added RAG context with {len(input_state.rag_context)} documents")
    
    return state_dict

async def load_conversation_context(state: State) -> dict:
    """Load relevant conversation history for the user"""
    log_step(state, "load_conversation_context")
    
    if not state.user_id:
        return {"relevant_context": ""}
    
    try:
        context = conversation_memory.get_conversation_context(
            user_id=state.user_id,
            current_query=state.current_query,
            max_context_length=1000
        )
        return {"relevant_context": context}
    except Exception as e:
        print(f"[GRAPH] Error loading conversation context: {e}")
        return {"relevant_context": ""}

async def greeting_node(state: State) -> dict:
    """Greeting agent node"""
    result = await greeting_agent.process(state)
    result["current_agent"] = "greeting_agent"
    return result

async def info_collection_node(state: State) -> dict:
    """Information collection agent node"""
    result = await info_collection_agent.process(state)
    result["current_agent"] = "info_collection_agent"
    return result

async def confirmation_node(state: State) -> dict:
    """Confirmation agent node"""
    result = await confirmation_agent.process(state)
    result["current_agent"] = "confirmation_agent"
    return result

async def completion_node(state: State) -> dict:
    """Completion agent node"""
    result = await completion_agent.process(state)
    result["current_agent"] = "completion_agent"
    return result

async def store_conversation(state: State) -> dict:
    """Store the conversation in memory"""
    log_step(state, "store_conversation")
    
    if not state.user_id:
        return {}
    
    try:
        human_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in state.messages if isinstance(msg, AIMessage)]
        
        if human_messages and ai_messages:
            last_human_msg = human_messages[-1].content
            last_ai_msg = ai_messages[-1].content
            
            conversation_memory.store_conversation(
                user_id=state.user_id,
                user_message=last_human_msg,
                agent_response=last_ai_msg,
                context={
                    "timestamp": datetime.now().isoformat(),
                    "current_agent": state.current_agent,
                    "collection_stage": state.collection_stage,
                    "lead_info": state.lead_info.__dict__
                }
            )
    except Exception as e:
        print(f"[GRAPH] Error storing conversation: {e}")
    
    return {}

# === ROUTING FUNCTIONS ===

def route_workflow(state: State) -> Literal["greeting_node", "info_collection_node", "confirmation_node", "completion_node", "__end__"]:
    """Route to appropriate agent based on current state"""
    
    if state.workflow_complete:
        return "__end__"
    
    # Route based on next_agent if specified
    if state.next_agent:
        agent_map = {
            "greeting_agent": "greeting_node",
            "info_collection_agent": "info_collection_node", 
            "confirmation_agent": "confirmation_node",
            "completion_agent": "completion_node"
        }
        return agent_map.get(state.next_agent, "greeting_node")
    
    # Route based on collection stage
    if state.collection_stage in ["greeting", "name"]:
        return "greeting_node"
    elif state.collection_stage in ["age", "country", "product"]:
        return "info_collection_node"
    elif state.collection_stage == "confirmation":
        return "confirmation_node"
    elif state.collection_stage == "complete":
        return "completion_node"
    
    return "greeting_node"

def route_after_agent(state: State) -> Literal["store_conversation", "__end__"]:
    """Route after agent processing"""
    if state.workflow_complete:
        return "__end__"
    return "store_conversation"

def route_after_store(state: State) -> Literal["greeting_node", "info_collection_node", "confirmation_node", "completion_node", "__end__"]:
    """Route after storing conversation"""
    return route_workflow(state)

# === GRAPH CONSTRUCTION ===

def create_graph():
    """Create the multi-agent workflow graph"""
    
    workflow = StateGraph(State, input=InputState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_state)
    workflow.add_node("load_context", load_conversation_context)
    workflow.add_node("greeting_node", greeting_node)
    workflow.add_node("info_collection_node", info_collection_node)
    workflow.add_node("confirmation_node", confirmation_node)
    workflow.add_node("completion_node", completion_node)
    workflow.add_node("store_conversation", store_conversation)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    # Add edges
    workflow.add_edge("initialize", "load_context")
    workflow.add_edge("load_context", "greeting_node")
    
    # Conditional routing from greeting node
    workflow.add_conditional_edges(
        "greeting_node",
        lambda state: "info_collection_node" if state.next_agent == "info_collection_agent" else "store_conversation",
        {
            "info_collection_node": "info_collection_node",
            "store_conversation": "store_conversation"
        }
    )
    
    # Conditional routing from info collection node
    workflow.add_conditional_edges(
        "info_collection_node", 
        lambda state: "confirmation_node" if state.next_agent == "confirmation_agent" else "store_conversation",
        {
            "confirmation_node": "confirmation_node",
            "store_conversation": "store_conversation"
        }
    )
    
    # Conditional routing from confirmation node
    workflow.add_conditional_edges(
        "confirmation_node",
        lambda state: "completion_node" if state.next_agent == "completion_agent" else "store_conversation",
        {
            "completion_node": "completion_node",
            "store_conversation": "store_conversation"
        }
    )
    
    # Completion node always goes to store and end
    workflow.add_edge("completion_node", "store_conversation")
    
    # Store conversation always ends
    workflow.add_edge("store_conversation", END)
    
    return workflow

# Create the compiled graph
graph = create_graph() 