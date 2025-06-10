# 🚀 How to Run Your Enhanced Dual RAG System

## 🎯 **TL;DR - Quick Start**

1. **Set your API keys** in `config.env`:
   ```bash
   GROQ_API_KEY=your_actual_groq_api_key_here
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   ```

2. **Run the application**:
   ```powershell
   # Windows PowerShell
   python src/react_agent/app.py
   ```

3. **Open browser** to: `http://localhost:5000`

## 📝 **Step-by-Step Instructions**

### **Step 1: Edit config.env**
Open the `config.env` file and replace the placeholder values:
```bash
# Before:
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# After (with your actual keys):
GROQ_API_KEY=gsk_1234567890abcdef...
GEMINI_API_KEY=AIzaSyD1234567890abcdef...
```

### **Step 2: Run the Application**
```powershell
# Navigate to the project directory (if not already there)
cd "D:\react-agent - RAG working AF"

# Run the Flask application
python src/react_agent/app.py
```

### **Step 3: Success Indicators**
Look for these messages:
```
🔧 Loaded environment variables from: config.env
🔑 GROQ_API_KEY: ✅ Loaded
🔑 GEMINI_API_KEY: ✅ Loaded
🤖 Multi-Agent system initialized with API key: gsk_...
✅ Enhanced RAG systems ready
✅ All systems ready
* Running on http://127.0.0.1:5000
```

## 🌐 **Access Your Application**

- **Web Interface**: `http://localhost:5000`
- **Start Conversation**: Enter a lead ID and name to begin
- **API Testing**: Use curl or Postman with the endpoints

## 🧪 **Test the System**

### **Quick API Test:**
```powershell
# Test the enhanced chat endpoint
curl -X POST http://localhost:5000/api/enhanced_chat -H "Content-Type: application/json" -d '{\"user_id\": \"test123\", \"message\": \"Hello\"}'
```

### **Web Interface Test:**
1. Go to `http://localhost:5000`
2. Enter a Lead ID (e.g., `test123`)
3. Enter a Name (e.g., `John`)
4. Click "Start Conversation"
5. Follow the conversation flow

## ⚠️ **If You Don't Have API Keys Yet**

The system will still run in **fallback mode**:
- ✅ Flask app works
- ✅ API endpoints respond
- ✅ Basic conversation flow
- ❌ Limited AI responses

**To get API keys:**
- [Groq](https://console.groq.com/) - Free tier available
- [Google Gemini](https://ai.google.dev/) - Free tier available

## 🚨 **Troubleshooting**

### **"Port 5000 already in use"**
```powershell
# Find and kill the process
netstat -ano | findstr :5000
taskkill /PID <process_id> /F

# Or use a different port in app.py:
# app.run(port=5001)
```

### **"Module not found"**
```powershell
# Install requirements
pip install -r requirements.txt
```

### **API keys not loading**
- Check `config.env` exists in root directory
- Ensure no extra spaces around `=`
- No quotes around API keys

## 🎉 **You're Ready!**

Your enhanced dual RAG system with:
- ✅ **Complete user isolation**
- ✅ **AI-powered conversations**
- ✅ **Vector-based memory**
- ✅ **Product recommendations**
- ✅ **Sequential workflow**

**Happy chatting!** 🤖💬 