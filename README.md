# 🤖 Sales Agent System - AI-Powered Customer Interaction Platform

A comprehensive, production-ready sales automation system powered by advanced AI, featuring real-time chat, intelligent lead management, and personalized product recommendations.

## ✨ Features

### 🧠 AI-Powered Conversations
- **Multi-Agent System**: Supports Google ADK, legacy agents, and fallback mechanisms
- **RAG Integration**: Retrieval-Augmented Generation for contextual responses
- **Natural Language Processing**: Intelligent extraction of customer details
- **Smart Follow-ups**: Automated, personalized follow-up messages

### 💬 Real-Time Communication
- **WebSocket Support**: Instant messaging with Socket.IO
- **Live Status Updates**: Real-time connection and typing indicators
- **Multi-Platform**: Works on desktop, tablet, and mobile devices
- **Offline Handling**: Graceful degradation when connection is lost

### 📊 Advanced State Management
- **Database-Backed**: SQLAlchemy ORM with SQLite/PostgreSQL/MySQL support
- **Session Management**: Persistent conversation states across sessions
- **Lead Tracking**: Comprehensive customer journey tracking
- **Analytics Dashboard**: Real-time metrics and conversion tracking

### 🎯 Lead Management
- **Automatic Data Extraction**: AI-powered detail collection from conversations
- **Progress Tracking**: Visual completion indicators for lead profiles
- **Status Management**: Multi-stage lead progression tracking
- **Export Capabilities**: CSV export for external CRM systems

### 🔧 Production Features
- **Database Migrations**: Flask-Migrate for schema management
- **Logging System**: Comprehensive logging with file and console output
- **Health Monitoring**: System health checks and status endpoints
- **Error Handling**: Robust error handling with fallback mechanisms
- **Security**: CSRF protection, input validation, and secure sessions

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Node.js (for frontend dependencies, optional)
- Redis (optional, for caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd react-agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp config.env.example config.env
   # Edit config.env with your API keys and settings
   ```

4. **Initialize the database**
   ```bash
   cd src/react_agent
   python -c "from app import create_app; app = create_app(); app.app_context().push(); from models import db; db.create_all()"
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

   Or use the main app file:
   ```bash
   python app.py
   ```

6. **Access the application**
   - Web Interface: http://localhost:5000
   - API Documentation: http://localhost:5000/api/system/health
   - Analytics: http://localhost:5000/api/analytics/leads

## 📁 Project Structure

```
react-agent/
├── src/react_agent/
│   ├── app.py                 # Main Flask application
│   ├── run.py                 # Standalone runner script
│   ├── models.py              # Database models
│   ├── state_manager.py       # State management system
│   ├── templates/             # HTML templates
│   │   ├── base.html         # Base template
│   │   ├── index.html        # Home page
│   │   └── conversation.html # Chat interface
│   ├── static/               # Static assets (CSS, JS, images)
│   └── logs/                 # Application logs
├── requirements.txt          # Python dependencies
├── config.env               # Environment configuration
└── README.md               # This file
```

## 🔧 Configuration

### Environment Variables

Edit `config.env` to configure the application:

```bash
# API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Database
DATABASE_URL=sqlite:///sales_agent.db

# Flask Settings
SECRET_KEY=your-super-secret-key
FLASK_ENV=development
FLASK_DEBUG=True

# Application Settings
MAX_MESSAGE_LENGTH=2000
FOLLOW_UP_THRESHOLD_MINUTES=1
MAX_FOLLOW_UPS=3
```

### Database Configuration

The system supports multiple database types:

- **SQLite** (default): `sqlite:///sales_agent.db`
- **PostgreSQL**: `postgresql://username:password@localhost/dbname`
- **MySQL**: `mysql://username:password@localhost/dbname`

## 🌐 API Endpoints

### Core Endpoints
- `GET /` - Home page with lead form
- `POST /start_conversation` - Initialize a new conversation
- `GET/POST /conversation/<lead_id>` - Conversation interface
- `POST /chat` - Send message to AI agent

### WebSocket Events
- `join_conversation` - Join a conversation room
- `send_message` - Send real-time message
- `get_user_status` - Get user details and progress
- `get_conversation_history` - Retrieve message history

### API Endpoints
- `GET /api/system/health` - System health check
- `GET /api/analytics/leads` - Lead analytics and statistics
- `GET /api/leads` - List all leads with pagination
- `GET /api/leads/<lead_id>` - Detailed lead information
- `POST /api/enhanced_chat` - Enhanced chat with RAG integration

## 🗄️ Database Schema

### Core Models
- **Lead**: Customer information and status
- **Conversation**: Chat messages and metadata
- **UserSession**: Session state management
- **FollowUpMessage**: Automated follow-up tracking
- **ProductRecommendation**: AI-generated suggestions
- **SystemMetrics**: Performance and usage analytics

## 🔌 WebSocket Integration

The system uses Socket.IO for real-time communication:

```javascript
// Connect to WebSocket
const socket = io();

// Join conversation room
socket.emit('join_conversation', { lead_id: 'your-lead-id' });

// Send message
socket.emit('send_message', { 
    lead_id: 'your-lead-id', 
    message: 'Hello!' 
});

// Listen for responses
socket.on('message_update', function(data) {
    console.log('New message:', data);
});
```

## 🤖 AI Agent Integration

### Supported Agent Types
1. **Google ADK Agent** (Primary)
2. **Enhanced RAG System** (Secondary)
3. **Legacy Agent** (Fallback)

### RAG System Features
- Document-based product recommendations
- Conversation context retention
- Personalized response generation
- Multi-modal content support

## 📊 Analytics and Monitoring

### Built-in Analytics
- Lead conversion rates
- Message volume tracking
- Session duration analysis
- Follow-up effectiveness metrics

### System Monitoring
- Database connection health
- AI agent availability
- WebSocket connection status  
- Error rate tracking

## 🔒 Security Features

- **Input Validation**: Comprehensive message and data validation
- **Session Security**: Secure session management with CSRF protection
- **API Rate Limiting**: Built-in protection against abuse
- **SQL Injection Prevention**: Parameterized queries and ORM protection
- **XSS Protection**: Output sanitization and CSP headers

## 🚀 Production Deployment

### Environment Setup
```bash
# Production configuration
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost/sales_agent_prod
SECRET_KEY=your-very-secure-production-key
```

### Docker Deployment (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
```

### Performance Tips
- Use PostgreSQL for production databases
- Enable Redis caching for sessions
- Configure reverse proxy (nginx/Apache)
- Set up SSL/TLS certificates
- Monitor with logging aggregation tools

## 🛠️ Development

### Running in Development Mode
```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
python app.py

# Run tests (if available)
python -m pytest tests/
```

### Adding New Features
1. Create database models in `models.py`
2. Add state management logic in `state_manager.py`
3. Implement API endpoints in `app.py`
4. Create frontend templates in `templates/`
5. Add WebSocket handlers for real-time features

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues
- **Database Errors**: Check DATABASE_URL configuration
- **AI Agent Failures**: Verify API keys in config.env
- **WebSocket Connection Issues**: Check firewall and port settings
- **Memory Issues**: Monitor conversation history cleanup

### Getting Help
- Check the logs in `src/react_agent/logs/`
- Visit the health endpoint: `/api/system/health`
- Review configuration in `config.env`

## 🔄 Updates and Changelog

### Version 2.0.0 (Current)
- ✅ Full state management system
- ✅ WebSocket real-time communication
- ✅ Database-backed persistence
- ✅ Analytics and monitoring
- ✅ Production-ready deployment
- ✅ Modern responsive UI
- ✅ Comprehensive error handling

### Previous Versions
- v1.0.0: Basic Flask app with AI integration
- v0.5.0: Initial prototype with CSV storage

---

**Made with ❤️ by the Sales Agent System Team**
