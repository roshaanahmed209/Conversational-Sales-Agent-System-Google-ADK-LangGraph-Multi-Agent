#!/usr/bin/env python3
"""
Sales Agent System - Main Runner
This script initializes and runs the complete sales agent system with all features.
"""

import os
import sys
import logging
from pathlib import Path

# Setup paths
current_dir = Path(__file__).parent.absolute()
root_dir = current_dir.parent.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(root_dir))

# Import the application
from app import create_app, socketio

def setup_logging():
    """Setup application logging"""
    log_dir = current_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "sales_agent.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_requirements():
    """Check if all required dependencies are installed"""
    required_packages = [
        'flask', 'flask_sqlalchemy', 'flask_migrate', 'flask_socketio',
        'python_dotenv', 'pandas', 'requests'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Please install them using: pip install -r requirements.txt")
        return False
    
    return True

def print_startup_banner():
    """Print startup banner with system information"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    SALES AGENT SYSTEM                        ║
    ║                Intelligent Sales Automation                  ║
    ╚══════════════════════════════════════════════════════════════╝
    
    🚀 Starting application...
    📍 Working Directory: {}
    🐍 Python Version: {}.{}.{}
    📦 Flask Environment: {}
    
    """.format(
        current_dir,
        sys.version_info.major,
        sys.version_info.minor, 
        sys.version_info.micro,
        os.getenv('FLASK_ENV', 'development')
    )
    print(banner)

def main():
    """Main application entry point"""
    try:
        # Print startup information
        print_startup_banner()
        
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Check requirements
        if not check_requirements():
            sys.exit(1)
        
        # Create the application
        logger.info("Initializing Sales Agent System...")
        app = create_app()
        
        # Get configuration
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
        
        # Print final startup information
        print(f"🌐 Server starting on http://{host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        print(f"📊 Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
        print(f"🔐 Secret key: {'✅ Set' if app.config.get('SECRET_KEY') != 'your-secret-key-here' else '⚠️  Using default'}")
        print("="*70)
        print("🎯 Ready to accept connections!")
        print("   - Web Interface: http://localhost:5000")
        print("   - API Health: http://localhost:5000/api/system/health")
        print("   - Analytics: http://localhost:5000/api/analytics/leads")
        print("="*70 + "\n")
        
        # Start the application with SocketIO
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,  # Disable reloader to prevent duplicate processes
            log_output=True
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        logger.info("Application stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error starting application: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main() 