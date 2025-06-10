from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
import threading
from collections import defaultdict
import uuid

from models import db, Lead, Conversation, UserSession, FollowUpMessage, ProductRecommendation, SystemMetrics

@dataclass
class ConversationState:
    """Data class for conversation state"""
    lead_id: str
    session_id: str
    current_step: str = "greeting"
    collected_details: Dict[str, Any] = None
    last_activity: datetime = None
    is_active: bool = True
    pending_confirmation: bool = False
    follow_up_count: int = 0
    
    def __post_init__(self):
        if self.collected_details is None:
            self.collected_details = {'name': None, 'age': None, 'country': None, 'interest': None}
        if self.last_activity is None:
            self.last_activity = datetime.utcnow()

class StateManager:
    """Centralized state management system"""
    
    def __init__(self):
        self._conversation_states: Dict[str, ConversationState] = {}
        self._follow_up_queue: Dict[str, List[str]] = defaultdict(list)
        self._activity_tracker: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._user_counters: Dict[str, int] = defaultdict(int)
        
    def get_or_create_conversation_state(self, lead_id: str, session_id: str = None) -> ConversationState:
        """Get or create conversation state for a lead"""
        if session_id is None:
            session_id = lead_id
            
        with self._lock:
            if lead_id not in self._conversation_states:
                # Try to load from database
                session = UserSession.query.filter_by(lead_id=lead_id, session_id=session_id).first()
                if session:
                    state_data = session.session_data or {}
                    self._conversation_states[lead_id] = ConversationState(
                        lead_id=lead_id,
                        session_id=session_id,
                        current_step=state_data.get('current_step', 'greeting'),
                        collected_details=state_data.get('collected_details', {
                            'name': None, 'age': None, 'country': None, 'interest': None
                        }),
                        last_activity=session.last_activity or datetime.utcnow(),
                        is_active=session.is_active,
                        pending_confirmation=state_data.get('pending_confirmation', False),
                        follow_up_count=state_data.get('follow_up_count', 0)
                    )
                else:
                    # Create new state
                    self._conversation_states[lead_id] = ConversationState(
                        lead_id=lead_id,
                        session_id=session_id
                    )
                    self._save_session_to_db(self._conversation_states[lead_id])
            
            return self._conversation_states[lead_id]
    
    def update_conversation_state(self, lead_id: str, **kwargs):
        """Update conversation state"""
        with self._lock:
            if lead_id in self._conversation_states:
                state = self._conversation_states[lead_id]
                for key, value in kwargs.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                state.last_activity = datetime.utcnow()
                self._save_session_to_db(state)
    
    def update_collected_details(self, lead_id: str, details: Dict[str, Any]):
        """Update collected user details"""
        with self._lock:
            state = self.get_or_create_conversation_state(lead_id)
            if state.collected_details is None:
                state.collected_details = {}
            
            for key, value in details.items():
                if value:  # Only update non-empty values
                    state.collected_details[key] = value
            
            state.last_activity = datetime.utcnow()
            self._save_session_to_db(state)
            
            # Also update lead in database
            self._update_lead_in_db(lead_id, details)
    
    def get_collected_details(self, lead_id: str) -> Dict[str, Any]:
        """Get collected details for a lead"""
        state = self.get_or_create_conversation_state(lead_id)
        return state.collected_details or {}
    
    def are_details_complete(self, lead_id: str) -> bool:
        """Check if all required details are collected"""
        details = self.get_collected_details(lead_id)
        required_fields = ['name', 'age', 'country', 'interest']
        return all(details.get(field) for field in required_fields)
    
    def get_missing_details(self, lead_id: str) -> List[str]:
        """Get list of missing detail fields"""
        details = self.get_collected_details(lead_id)
        required_fields = ['name', 'age', 'country', 'interest']
        return [field for field in required_fields if not details.get(field)]
    
    def record_user_activity(self, lead_id: str):
        """Record user activity"""
        with self._lock:
            self._activity_tracker[lead_id] = datetime.utcnow()
            self._user_counters[lead_id] += 1
            self.update_conversation_state(lead_id, last_activity=datetime.utcnow())
    
    def get_inactive_users(self, threshold_minutes: int = 1) -> List[str]:
        """Get list of inactive users"""
        threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        inactive_users = []
        
        with self._lock:
            for lead_id, last_activity in self._activity_tracker.items():
                if last_activity < threshold:
                    state = self._conversation_states.get(lead_id)
                    if state and state.is_active:
                        inactive_users.append(lead_id)
        
        return inactive_users
    
    def add_follow_up_message(self, lead_id: str, message: str):
        """Add follow-up message to queue"""
        with self._lock:
            self._follow_up_queue[lead_id].append(message)
            
            # Save to database
            follow_up = FollowUpMessage(
                lead_id=lead_id,
                message=message,
                sent_at=datetime.utcnow()
            )
            db.session.add(follow_up)
            db.session.commit()
    
    def get_follow_up_messages(self, lead_id: str) -> List[str]:
        """Get and clear follow-up messages for a lead"""
        with self._lock:
            messages = self._follow_up_queue.get(lead_id, [])
            if messages:
                self._follow_up_queue[lead_id] = []
                
                # Mark as delivered in database
                FollowUpMessage.query.filter_by(
                    lead_id=lead_id, 
                    is_delivered=False
                ).update({
                    'is_delivered': True,
                    'delivery_attempted_at': datetime.utcnow()
                })
                db.session.commit()
            
            return messages
    
    def has_follow_up_messages(self, lead_id: str) -> bool:
        """Check if there are pending follow-up messages"""
        with self._lock:
            return len(self._follow_up_queue.get(lead_id, [])) > 0
    
    def save_conversation_message(self, lead_id: str, role: str, content: str, metadata: Dict = None):
        """Save conversation message to database"""
        state = self.get_or_create_conversation_state(lead_id)
        
        message = Conversation(
            lead_id=lead_id,
            session_id=state.session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow()
        )
        
        db.session.add(message)
        db.session.commit()
    
    def get_conversation_history(self, lead_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history for a lead"""
        conversations = Conversation.query.filter_by(
            lead_id=lead_id
        ).order_by(
            Conversation.timestamp.desc()
        ).limit(limit).all()
        
        return [conv.to_dict() for conv in reversed(conversations)]
    
    def save_product_recommendation(self, lead_id: str, product_name: str, 
                                  category: str = None, price: float = None, 
                                  description: str = None, score: float = None):
        """Save product recommendation"""
        recommendation = ProductRecommendation(
            lead_id=lead_id,
            product_name=product_name,
            category=category,
            price=price,
            description=description,
            recommendation_score=score,
            recommended_at=datetime.utcnow()
        )
        
        db.session.add(recommendation)
        db.session.commit()
    
    def get_user_recommendations(self, lead_id: str) -> List[Dict]:
        """Get product recommendations for a user"""
        recommendations = ProductRecommendation.query.filter_by(
            lead_id=lead_id
        ).order_by(
            ProductRecommendation.recommended_at.desc()
        ).all()
        
        return [rec.to_dict() for rec in recommendations]
    
    def record_system_metric(self, metric_name: str, value: float, data: Dict = None):
        """Record system metrics"""
        metric = SystemMetrics(
            metric_name=metric_name,
            metric_value=value,
            metric_data=data or {},
            recorded_at=datetime.utcnow()
        )
        
        db.session.add(metric)
        db.session.commit()
    
    def get_system_metrics(self, metric_name: str = None, hours: int = 24) -> List[Dict]:
        """Get system metrics"""
        query = SystemMetrics.query
        
        if metric_name:
            query = query.filter_by(metric_name=metric_name)
        
        since = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(SystemMetrics.recorded_at >= since)
        
        metrics = query.order_by(SystemMetrics.recorded_at.desc()).all()
        return [metric.to_dict() for metric in metrics]
    
    def cleanup_inactive_sessions(self, hours: int = 24):
        """Clean up inactive sessions"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            # Clean up in-memory states
            inactive_leads = []
            for lead_id, state in self._conversation_states.items():
                if state.last_activity < cutoff:
                    inactive_leads.append(lead_id)
            
            for lead_id in inactive_leads:
                del self._conversation_states[lead_id]
                if lead_id in self._activity_tracker:
                    del self._activity_tracker[lead_id]
                if lead_id in self._follow_up_queue:
                    del self._follow_up_queue[lead_id]
        
        # Update database sessions
        UserSession.query.filter(
            UserSession.last_activity < cutoff
        ).update({'is_active': False})
        db.session.commit()
    
    def _save_session_to_db(self, state: ConversationState):
        """Save session state to database"""
        session = UserSession.query.filter_by(
            session_id=state.session_id,
            lead_id=state.lead_id
        ).first()
        
        session_data = {
            'current_step': state.current_step,
            'collected_details': state.collected_details,
            'pending_confirmation': state.pending_confirmation,
            'follow_up_count': state.follow_up_count
        }
        
        if session:
            session.session_data = session_data
            session.last_activity = state.last_activity
            session.is_active = state.is_active
        else:
            session = UserSession(
                session_id=state.session_id,
                lead_id=state.lead_id,
                session_data=session_data,
                last_activity=state.last_activity,
                is_active=state.is_active
            )
            db.session.add(session)
        
        db.session.commit()
    
    def _update_lead_in_db(self, lead_id: str, details: Dict[str, Any]):
        """Update lead information in database"""
        lead = Lead.query.filter_by(lead_id=lead_id).first()
        
        if not lead:
            lead = Lead(lead_id=lead_id)
            db.session.add(lead)
        
        # Update lead fields
        if 'name' in details and details['name']:
            lead.name = details['name']
        if 'age' in details and details['age']:
            lead.age = int(details['age']) if str(details['age']).isdigit() else None
        if 'country' in details and details['country']:
            lead.country = details['country']
        if 'interest' in details and details['interest']:
            lead.interest = details['interest']
        
        lead.updated_at = datetime.utcnow()
        db.session.commit()
    
    def get_lead_statistics(self) -> Dict[str, Any]:
        """Get lead statistics"""
        total_leads = Lead.query.count()
        active_sessions = UserSession.query.filter_by(is_active=True).count()
        completed_leads = Lead.query.filter(
            Lead.name.isnot(None),
            Lead.age.isnot(None),
            Lead.country.isnot(None),
            Lead.interest.isnot(None)
        ).count()
        
        return {
            'total_leads': total_leads,
            'active_sessions': active_sessions,
            'completed_leads': completed_leads,
            'completion_rate': (completed_leads / total_leads * 100) if total_leads > 0 else 0,
            'active_conversations': len(self._conversation_states)
        }

# Global state manager instance
state_manager = StateManager() 