#!/usr/bin/env python3
"""
Database Migration Script for Sales Agent System
This script handles database initialization and migrations.
"""

import os
import sys
from pathlib import Path

# Setup paths
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

from dotenv import load_dotenv
load_dotenv('config.env')

from app import app, db
from models import Lead, Conversation, UserSession, FollowUpMessage, ProductRecommendation, SystemMetrics
import pandas as pd

def init_database():
    """Initialize the database with all tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database tables created successfully!")

def migrate_csv_data():
    """Migrate existing CSV data to database"""
    csv_file = "leads.csv"
    
    if not os.path.exists(csv_file):
        print("⚠️  No existing CSV file found - skipping CSV migration")
        return
    
    with app.app_context():
        try:
            # Read CSV data
            df = pd.read_csv(csv_file)
            migrated_count = 0
            
            print(f"Found {len(df)} records in CSV file")
            
            for _, row in df.iterrows():
                # Check if lead already exists
                existing_lead = Lead.query.filter_by(lead_id=row['lead_id']).first()
                if existing_lead:
                    continue
                
                # Create new lead
                lead = Lead(
                    lead_id=row['lead_id'],
                    name=row.get('name') if pd.notna(row.get('name')) else None,
                    age=int(row['age']) if pd.notna(row.get('age')) and str(row['age']).isdigit() else None,
                    country=row.get('country') if pd.notna(row.get('country')) else None,
                    interest=row.get('interest') if pd.notna(row.get('interest')) else None,
                    status=row.get('status', 'migrated')
                )
                
                db.session.add(lead)
                migrated_count += 1
            
            db.session.commit()
            print(f"✅ Migrated {migrated_count} leads from CSV to database")
            
        except Exception as e:
            print(f"❌ Error migrating CSV data: {e}")
            db.session.rollback()

def create_sample_data():
    """Create sample data for testing"""
    with app.app_context():
        try:
            # Check if sample data already exists
            if Lead.query.count() > 0:
                print("⚠️  Data already exists - skipping sample data creation")
                return
            
            # Create sample leads
            sample_leads = [
                {
                    'lead_id': 'sample_001',
                    'name': 'John Doe',
                    'age': 30,
                    'country': 'United States',
                    'interest': 'Technology',
                    'status': 'confirmed'
                },
                {
                    'lead_id': 'sample_002', 
                    'name': 'Jane Smith',
                    'age': 25,
                    'country': 'Canada',
                    'interest': 'Fashion',
                    'status': 'started'
                },
                {
                    'lead_id': 'sample_003',
                    'name': 'Mike Johnson',
                    'age': 35,
                    'country': 'United Kingdom',
                    'interest': 'Home & Living',
                    'status': 'confirmed'
                }
            ]
            
            for lead_data in sample_leads:
                lead = Lead(**lead_data)
                db.session.add(lead)
            
            db.session.commit()
            print(f"✅ Created {len(sample_leads)} sample leads")
            
        except Exception as e:
            print(f"❌ Error creating sample data: {e}")
            db.session.rollback()

def check_database_status():
    """Check database connection and table status"""
    with app.app_context():
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            print("✅ Database connection successful")
            
            # Check tables
            tables = [Lead, Conversation, UserSession, FollowUpMessage, ProductRecommendation, SystemMetrics]
            table_status = {}
            
            for table in tables:
                try:
                    count = table.query.count()
                    table_status[table.__tablename__] = count
                    print(f"📊 {table.__tablename__}: {count} records")
                except Exception as e:
                    table_status[table.__tablename__] = f"Error: {e}"
                    print(f"❌ {table.__tablename__}: Error - {e}")
            
            return table_status
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return None

def cleanup_old_data():
    """Clean up old data and sessions"""
    with app.app_context():
        try:
            from datetime import datetime, timedelta
            
            # Clean up old sessions (older than 7 days)
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            old_sessions = UserSession.query.filter(
                UserSession.last_activity < cutoff_date
            ).count()
            
            if old_sessions > 0:
                UserSession.query.filter(
                    UserSession.last_activity < cutoff_date
                ).delete()
                
                db.session.commit()
                print(f"🧹 Cleaned up {old_sessions} old sessions")
            else:
                print("✅ No old sessions to clean up")
                
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            db.session.rollback()

def main():
    """Main migration function"""
    print("\n" + "="*50)
    print("🔧 SALES AGENT SYSTEM - DATABASE MIGRATION")
    print("="*50)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_database()
    
    # Migrate CSV data
    print("\n2. Migrating CSV data...")
    migrate_csv_data()
    
    # Create sample data
    print("\n3. Creating sample data...")
    create_sample_data()
    
    # Check status
    print("\n4. Checking database status...")
    status = check_database_status()
    
    # Cleanup
    print("\n5. Cleaning up old data...")
    cleanup_old_data()
    
    print("\n" + "="*50)
    print("✅ DATABASE MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*50)
    
    if status:
        print("\n📊 Final Database Status:")
        for table, count in status.items():
            print(f"   {table}: {count}")
    
    print(f"\n🌐 You can now start the application:")
    print(f"   python run.py")
    print(f"   or")
    print(f"   python app.py")

if __name__ == '__main__':
    main() 