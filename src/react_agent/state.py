from dataclasses import dataclass, field
from typing import Sequence, List, Dict, Any, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from typing_extensions import Annotated

@dataclass
class InputState:
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    user_id: str = field(default="")
    message: str = field(default="")
    rag_context: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class LeadInfo:
    """Structure to hold lead information"""
    name: Optional[str] = None
    age: Optional[str] = None
    country: Optional[str] = None
    product_interest: Optional[str] = None
    status: str = "new"
    
    def is_complete(self) -> bool:
        """Check if all required fields are filled"""
        return all([self.name, self.age, self.country, self.product_interest])
    
    def get_missing_fields(self) -> List[str]:
        """Get list of missing required fields"""
        missing = []
        if not self.name:
            missing.append("name")
        if not self.age:
            missing.append("age")
        if not self.country:
            missing.append("country")
        if not self.product_interest:
            missing.append("product interest")
        return missing

@dataclass
class State(InputState):
    # Core LangGraph state
    is_last_step: IsLastStep = field(default=False)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_metrics: Dict[str, float] = field(default_factory=dict)
    current_query: str = field(default="")
    rag_response: str = field(default="")
    
    # Conversation memory fields
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    relevant_context: str = field(default="")
    
    # Multi-agent workflow fields
    current_agent: str = field(default="greeting_agent")
    next_agent: Optional[str] = field(default=None)
    workflow_complete: bool = field(default=False)
    
    # Lead collection fields
    lead_info: LeadInfo = field(default_factory=LeadInfo)
    collection_stage: str = field(default="greeting")  # greeting, name, age, country, product, confirmation
    attempts_count: int = field(default=0)
    max_attempts: int = field(default=3)
    
    # Agent communication
    agent_handoff_message: str = field(default="")
    requires_confirmation: bool = field(default=False)
    confirmation_pending: bool = field(default=False)
