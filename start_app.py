#!/usr/bin/env python3
"""
Simple startup script for the Sales Agent Application
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv('config.env')

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

def main():
    try:
        print("🚀 Starting Sales Agent Application...")
        print("="*50)
        
        # Import Flask app
        from react_agent.app import app, db, socketio
        
        # Create database tables
        print("📊 Initializing database...")
        with app.app_context():
            db.create_all()
            print("✅ Database initialized successfully")
        
        # Start the application
        print("🌐 Starting web server...")
        print("📱 Application will be available at: http://localhost:5000")
        print("="*50)
        
        # Run with SocketIO
        socketio.run(
            app,
            debug=True,
            host='0.0.0.0',
            port=5000,
            use_reloader=False  # Avoid duplicate processes
        )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Please make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main() 