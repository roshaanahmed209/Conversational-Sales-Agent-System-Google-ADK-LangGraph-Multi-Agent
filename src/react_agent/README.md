# React Agent with LangGraph and Conversation Memory

A powerful sales assistant application built with LangGraph, featuring conversation memory using vector embeddings. The system remembers user conversations and can reference previous interactions to provide contextual responses.

## Features

### 🧠 Conversation Memory
- **Vector-based storage**: User conversations are stored in vector embeddings using FAISS
- **User-specific memory**: Each user ID has isolated conversation history
- **Contextual retrieval**: Previous conversations are retrieved based on semantic similarity
- **Persistent storage**: Conversations are stored in SQLite database with vector search capabilities

### 🔄 LangGraph Integration
- **State management**: Robust conversation state handling
- **Multi-step processing**: Load context → Generate response → Store conversation
- **RAG integration**: Retrieval-Augmented Generation for document-based responses
- **Tool calling**: Support for external tool integration

### 💼 Sales Assistant
- **Lead information collection**: Name, age, country, product interest
- **Conversation continuity**: Resumes conversations where they left off
- **Smart follow-ups**: Automatic follow-up messages for inactive users
- **CSV export**: Lead data saved to CSV format

## Architecture

### Core Components

1. **ConversationMemory** (`conversation_memory.py`)
   - Vector storage using FAISS and HuggingFace embeddings
   - SQLite database for structured conversation data
   - Semantic search for relevant conversation retrieval

2. **LangGraph Agent** (`agent.py`)
   - LangGraph-based conversation processing
   - Async and sync chat interfaces
   - Memory-aware response generation

3. **Graph Nodes** (`graph.py`)
   - `load_conversation_context`: Retrieves relevant past conversations
   - `call_model`: Generates responses with conversation context
   - `store_conversation`: Saves conversations to memory
   - RAG nodes for document-based responses

4. **Flask API** (`app.py`)
   - Web interface for sales conversations
   - REST API endpoints for conversation management
   - Real-time conversation handling

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd react-agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file with:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here  # Optional
   ANTHROPIC_API_KEY=your_anthropic_api_key_here  # Optional
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

## Usage

### Web Interface

1. **Start a conversation**: Navigate to `http://localhost:5000`
2. **Enter lead details**: Provide name and lead ID
3. **Chat with memory**: The agent remembers previous conversations
4. **Lead data collection**: Agent collects required information systematically

### API Endpoints

#### Chat with Memory
```bash
POST /api/chat_with_memory
Content-Type: application/json

{
  "user_id": "lead_123",
  "message": "Hello, I'm interested in your products",
  "session_id": "optional_session_id"
}
```

#### Get Conversation History
```bash
GET /api/conversation_history/lead_123?limit=10
```

#### Clear User Memory
```bash
DELETE /api/clear_conversation_history/lead_123
```

#### List Users with History
```bash
GET /api/users_with_history
```

### Programmatic Usage

```python
from agent import langgraph_agent, sales_agent

# Direct agent usage
response = langgraph_agent.chat(
    user_id="user_123",
    message="What products do you offer?",
    session_id="session_abc"
)

# Sales-specific functionality
response = sales_agent.process_lead_conversation(
    lead_id="lead_456",
    message="I'm interested in laptops"
)

# Get conversation history
history = sales_agent.get_lead_history("lead_456")
```

## Configuration

### Model Configuration
Update `configuration.py` to change:
- LLM model (default: `groq/llama-3.3-70b-versatile`)
- RAG settings
- Evaluation parameters

### Memory Configuration
Modify `conversation_memory.py` for:
- Vector store settings
- Embedding model selection
- Database location
- Chunk size and overlap settings

### System Prompts
Edit `prompts.py` to customize:
- Agent behavior
- Sales conversation flow
- Information collection requirements

## How Conversation Memory Works

### 1. Storage Process
- User messages and agent responses are stored in SQLite database
- Conversations are converted to vector embeddings using sentence-transformers
- Embeddings are stored in FAISS vector database for fast similarity search

### 2. Retrieval Process
- When a user sends a message, system searches for similar past conversations
- Recent conversation history is also retrieved for context
- Both semantic similarity and recency are considered

### 3. Context Integration
- Retrieved conversations are formatted as context
- Context is injected into the system prompt
- Agent generates responses aware of conversation history

### 4. Data Structure
```sql
-- SQLite Database Schema
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    context TEXT,
    session_id TEXT
);
```

## Benefits

### For Users
- **Seamless experience**: No need to repeat information
- **Contextual responses**: Agent understands conversation history
- **Natural conversations**: Feel like talking to someone who remembers

### For Business
- **Better lead qualification**: Continuous conversation threads
- **Improved conversion**: Personalized interactions based on history
- **Data insights**: Rich conversation analytics and history

### For Developers
- **Modular architecture**: Easy to extend and customize
- **Scalable storage**: Vector database handles large conversation volumes
- **API-first design**: Easy integration with other systems

## Troubleshooting

### Common Issues

1. **Memory not working**
   - Check if `conversation_memory` directory is writable
   - Verify HuggingFace transformers installation
   - Check FAISS installation for your system

2. **Model errors**
   - Verify API keys are set correctly
   - Check model availability (Groq, OpenAI, etc.)
   - Review network connectivity

3. **Performance issues**
   - Consider using GPU for embeddings if available
   - Adjust chunk sizes in conversation memory
   - Monitor vector store size

### Logs
- Conversation storage/retrieval logs: Look for `[GRAPH]` prefixed messages
- Memory operations: Check `conversation_memory.py` output
- Agent processing: Monitor `agent.py` logs

## Future Enhancements

- [ ] Multi-modal conversation support (images, files)
- [ ] Advanced conversation analytics and insights
- [ ] Integration with CRM systems
- [ ] Conversation export/import functionality
- [ ] Real-time conversation monitoring dashboard
- [ ] A/B testing for different conversation strategies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Submit a pull request

## License

[Your license here] 