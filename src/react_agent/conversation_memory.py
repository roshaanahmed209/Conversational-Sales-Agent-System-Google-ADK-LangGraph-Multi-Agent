import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import re
from collections import defaultdict

@dataclass
class ConversationEntry:
    user_id: str
    timestamp: datetime
    user_message: str
    agent_response: str
    context: Dict[str, Any] = None

class SimpleVectorSearch:
    """Simple text similarity search using keyword matching and TF-IDF like scoring"""
    
    def __init__(self):
        self.documents = []
        self.index = defaultdict(list)
    
    def add_document(self, doc_id: str, text: str, metadata: dict):
        """Add a document to the search index"""
        doc = {
            'id': doc_id,
            'text': text,
            'metadata': metadata,
            'words': self._extract_words(text)
        }
        self.documents.append(doc)
        
        # Build inverted index
        for word in doc['words']:
            self.index[word].append(len(self.documents) - 1)
    
    def _extract_words(self, text: str) -> List[str]:
        """Extract words from text for indexing"""
        # Convert to lowercase and extract words
        words = re.findall(r'\b\w+\b', text.lower())
        return list(set(words))  # Remove duplicates
    
    def search(self, query: str, user_id: str = None, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        query_words = self._extract_words(query)
        
        # Score documents based on word overlap
        doc_scores = defaultdict(float)
        
        for word in query_words:
            if word in self.index:
                for doc_idx in self.index[word]:
                    doc = self.documents[doc_idx]
                    # Filter by user_id if specified
                    if user_id and doc['metadata'].get('user_id') != user_id:
                        continue
                    
                    # Simple scoring: count of matching words
                    doc_scores[doc_idx] += 1.0 / len(query_words)
        
        # Sort by score and return top k
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        
        results = []
        for doc_idx, score in sorted_docs:
            doc = self.documents[doc_idx]
            results.append({
                'content': doc['text'],
                'metadata': doc['metadata'],
                'similarity_score': score
            })
        
        return results
    
    def clear_user_documents(self, user_id: str):
        """Remove all documents for a specific user"""
        # Filter out documents for the user
        self.documents = [doc for doc in self.documents if doc['metadata'].get('user_id') != user_id]
        
        # Rebuild index
        self.index = defaultdict(list)
        for i, doc in enumerate(self.documents):
            for word in doc['words']:
                self.index[word].append(i)

class ConversationMemory:
    def __init__(self, memory_dir: str = "conversation_memory"):
        self.memory_dir = memory_dir
        self.db_path = os.path.join(memory_dir, "conversations.db")
        
        # Create directories if they don't exist
        os.makedirs(memory_dir, exist_ok=True)
        
        # Initialize simple vector search
        self.vector_search = SimpleVectorSearch()
        
        # Initialize database
        self._init_database()
        
        # Load existing conversations into vector search
        self._load_existing_conversations()
    
    def _init_database(self):
        """Initialize SQLite database for conversation storage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    agent_response TEXT NOT NULL,
                    context TEXT,
                    session_id TEXT
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON conversations(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp)
            ''')
            conn.commit()
    
    def _load_existing_conversations(self):
        """Load existing conversations into vector search"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, user_id, timestamp, user_message, agent_response, session_id
                    FROM conversations
                    ORDER BY timestamp
                ''')
                
                for row in cursor.fetchall():
                    conversation_id, user_id, timestamp, user_message, agent_response, session_id = row
                    conversation_text = f"User: {user_message}\nAgent: {agent_response}"
                    
                    self.vector_search.add_document(
                        doc_id=f"{user_id}_{conversation_id}_{timestamp}",
                        text=conversation_text,
                        metadata={
                            "user_id": user_id,
                            "timestamp": timestamp,
                            "session_id": session_id or "",
                            "conversation_id": str(conversation_id),
                            "type": "conversation"
                        }
                    )
        except Exception as e:
            print(f"Error loading existing conversations: {e}")
    
    def store_conversation(self, user_id: str, user_message: str, agent_response: str, 
                          context: Dict[str, Any] = None, session_id: str = None):
        """Store a conversation in both database and vector store"""
        timestamp = datetime.now().isoformat()
        
        # Store in SQLite database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (user_id, timestamp, user_message, agent_response, context, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, timestamp, user_message, agent_response, 
                  json.dumps(context) if context else None, session_id))
            conversation_id = cursor.lastrowid
            conn.commit()
        
        # Add to vector search
        conversation_text = f"User: {user_message}\nAgent: {agent_response}"
        
        self.vector_search.add_document(
            doc_id=f"{user_id}_{conversation_id}_{timestamp}",
            text=conversation_text,
            metadata={
                "user_id": user_id,
                "timestamp": timestamp,
                "session_id": session_id or "",
                "conversation_id": str(conversation_id),
                "type": "conversation"
            }
        )
        
        print(f"[MEMORY] Stored conversation for user {user_id}")
    
    def retrieve_relevant_conversations(self, user_id: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant conversations for a user based on similarity search"""
        try:
            return self.vector_search.search(query, user_id=user_id, k=k)
        except Exception as e:
            print(f"Error retrieving conversations: {e}")
            return []
    
    def get_user_conversation_history(self, user_id: str, limit: int = 10, 
                                    session_id: str = None) -> List[ConversationEntry]:
        """Get recent conversation history for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute('''
                    SELECT user_id, timestamp, user_message, agent_response, context
                    FROM conversations 
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, session_id, limit))
            else:
                cursor.execute('''
                    SELECT user_id, timestamp, user_message, agent_response, context
                    FROM conversations 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, limit))
            
            rows = cursor.fetchall()
            
            conversations = []
            for row in rows:
                context = json.loads(row[4]) if row[4] else None
                conversations.append(ConversationEntry(
                    user_id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    user_message=row[2],
                    agent_response=row[3],
                    context=context
                ))
            
            return list(reversed(conversations))  # Return in chronological order
    
    def get_conversation_context(self, user_id: str, current_query: str, max_context_length: int = 2000) -> str:
        """Get relevant conversation context for the current query"""
        # Get relevant conversations
        relevant_conversations = self.retrieve_relevant_conversations(user_id, current_query, k=3)
        
        # Get recent conversation history
        recent_conversations = self.get_user_conversation_history(user_id, limit=5)
        
        # Build context string
        context_parts = []
        
        if recent_conversations:
            context_parts.append("Recent conversation history:")
            for conv in recent_conversations[-3:]:  # Last 3 conversations
                context_parts.append(f"User: {conv.user_message}")
                context_parts.append(f"Agent: {conv.agent_response}")
                context_parts.append("")
        
        if relevant_conversations:
            context_parts.append("Relevant past conversations:")
            for conv in relevant_conversations:
                context_parts.append(conv["content"])
                context_parts.append("")
        
        context = "\n".join(context_parts)
        
        # Truncate if too long
        if len(context) > max_context_length:
            context = context[:max_context_length] + "..."
        
        return context
    
    def clear_user_conversations(self, user_id: str):
        """Clear all conversations for a specific user"""
        # Get count before deletion for reporting
        count = self.get_user_conversation_count(user_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
            conn.commit()
        
        # Clear from vector search
        self.vector_search.clear_user_documents(user_id)
        
        print(f"🧹 Cleared {count} conversations for user: {user_id}")
        return count
    
    def get_user_conversation_count(self, user_id: str) -> int:
        """Get the number of conversations for a specific user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
            return cursor.fetchone()[0]
    
    def get_all_users_with_conversations(self) -> List[Dict[str, Any]]:
        """Get list of all users who have conversations stored"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, 
                       COUNT(*) as conversation_count,
                       MIN(timestamp) as first_conversation,
                       MAX(timestamp) as last_conversation
                FROM conversations 
                GROUP BY user_id
                ORDER BY last_conversation DESC
            ''')
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    "user_id": row[0],
                    "conversation_count": row[1],
                    "first_conversation": row[2],
                    "last_conversation": row[3]
                })
            
            return users
    
    def cleanup_confirmed_users(self, confirmed_user_ids: List[str]) -> int:
        """Bulk cleanup for multiple confirmed users"""
        total_cleaned = 0
        for user_id in confirmed_user_ids:
            count = self.clear_user_conversations(user_id)
            total_cleaned += count
        
        print(f"🧹 Bulk cleanup completed: {total_cleaned} conversations cleared for {len(confirmed_user_ids)} users")
        return total_cleaned

# Global instance
conversation_memory = ConversationMemory() 