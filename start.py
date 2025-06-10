#!/usr/bin/env python3
"""
Sales Agent System - Quick Start Script
Run this script to quickly start the Sales Agent System with all features.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_config_file():
    """Check if configuration file exists"""
    config_file = Path("config.env")
    if not config_file.exists():
        print("⚠️  config.env not found, creating from template...")
        try:
            # Create basic config file
            with open("config.env", "w") as f:
                f.write("""# Sales Agent System Configuration
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=sqlite:///sales_agent.db
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=development
FLASK_DEBUG=True
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
""")
            print("✅ Created config.env file")
            print("   Please edit config.env with your API keys before running again")
            return False
        except Exception as e:
            print(f"❌ Could not create config.env: {e}")
            return False
    
    print("✅ Configuration file found")
    return True

def install_requirements():
    """Install required packages"""
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    try:
        print("📦 Installing requirements...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Requirements installed successfully")
            return True
        else:
            print(f"❌ Failed to install requirements: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def setup_database():
    """Setup database"""
    try:
        print("🗄️  Setting up database...")
        
        # Change to the app directory
        app_dir = Path("src/react_agent")
        if app_dir.exists():
            os.chdir(app_dir)
            
            # Run database migration
            result = subprocess.run([
                sys.executable, "migrate_db.py"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Database setup completed")
                return True
            else:
                print(f"⚠️  Database setup had issues: {result.stderr}")
                # Continue anyway, as the app might still work
                return True
        else:
            print("❌ Application directory not found")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def start_application():
    """Start the application"""
    try:
        print("🚀 Starting Sales Agent System...")
        
        app_dir = Path("src/react_agent")
        if app_dir.exists():
            os.chdir(app_dir)
            
            # Start the application
            subprocess.run([sys.executable, "run.py"])
        else:
            print("❌ Application directory not found")
            return False
            
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        return False

def main():
    """Main startup function"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    SALES AGENT SYSTEM                        ║
    ║                    Quick Start Script                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check configuration
    if not check_config_file():
        print("\n❌ Setup incomplete. Please configure your API keys and run again.")
        sys.exit(1)
    
    # Ask user if they want to install requirements
    install_deps = input("\n📦 Install/update requirements? (y/n): ").lower().strip()
    if install_deps in ['y', 'yes', '']:
        if not install_requirements():
            print("⚠️  Could not install requirements. Continuing anyway...")
    
    # Setup database
    setup_db = input("🗄️  Setup/migrate database? (y/n): ").lower().strip()
    if setup_db in ['y', 'yes', '']:
        if not setup_database():
            print("⚠️  Database setup had issues. Continuing anyway...")
    
    print("\n" + "="*50)
    print("🎯 STARTING APPLICATION")
    print("="*50)
    print("📋 Once started, you can access:")
    print("   🌐 Web Interface: http://localhost:5000")
    print("   📊 System Health: http://localhost:5000/api/system/health")
    print("   📈 Analytics: http://localhost:5000/api/analytics/leads")
    print("="*50)
    
    # Start the application
    start_application()

if __name__ == '__main__':
    main() 