# 🧠 AI Sales Agent using Google ADK, LangGraph, and Groq (LLaMA-7B)

A fully functional conversational Sales Agent built with **Google's Agent Development Kit (ADK)** and powered by **Groq's LLaMA-7B**, orchestrated using **LangGraph** and **LangChain**. This project mimics a human-like sales assistant that collects leads through structured form-style conversations, manages follow-ups, and stores confirmed data.

## 📽️ Demo Video

https://drive.google.com/file/d/1wXNgDpLL5MF0-oYVgyex36RzNA9mUs5W/view?usp=sharing

---

## 🚀 Features

✅ Integrated with **Groq's blazing-fast LLaMA-7B** as the root agent  
✅ Orchestration with **LangGraph** and **LangChain**  
✅ Built using **Flask** for web routing and interaction  
✅ Structured form-filling flow: Name, Age, Country, Interest  
✅ Natural, human-like conversation — feels like chatting with a real sales rep  
✅ Intelligent **follow-up messages** for inactive users  
✅ Session-based conversation memory using `InMemorySessionService`  
✅ Data confirmation before storage  
✅ Exit command handling for session reset  
✅ Lead data stored in a local CSV file (`leads.csv`)  
✅ Easily extendable and scalable architecture

---

## 🛠️ Tech Stack

- **LLM**: Groq LLaMA-7B
- **Agent Framework**: Google ADK
- **Orchestration**: LangGraph, LangChain
- **Backend**: Python 3.10+, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Data Storage**: pandas + CSV
- **Session Handling**: InMemorySessionService

---

## 📁 Project Structure

sales_agent_app/
├── templates/ # HTML templates
├── static/ # CSS/JS files
├── app.py # Main Flask app
├── agent_config.py # ADK root agent configuration
├── utils.py # Core logic and helper functions
├── leads.csv # Stores confirmed leads
├── requirements.txt # Python dependencies
└── README.md # This file



---

## 💡 How It Works

1. The user initiates a conversation through the web interface.
2. The root agent (LLaMA-7B via Groq) starts a step-by-step conversation to collect:
   - Name
   - Age
   - Country
   - Interest
3. The agent summarizes the inputs and asks for confirmation.
4. If confirmed, the data is stored in `leads.csv`.
5. If the user is inactive for a simulated time, a follow-up message is triggered.
6. Recognizes exit commands like `exit`, `quit`, etc., and resets the session.

---

## 🧪 Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/roshaanahmed209/Sales-Agent-with-Google-ADK.git
cd Sales-Agent-with-Google-ADK
```

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


pip install -r requirements.txt

python app.py

