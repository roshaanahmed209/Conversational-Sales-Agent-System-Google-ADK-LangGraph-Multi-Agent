#!/usr/bin/env python3
"""
Utility script to manage conversation memory
"""

import pandas as pd
from conversation_memory import conversation_memory
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config.env')

def show_memory_stats():
    """Show current memory statistics"""
    print("📊 Conversation Memory Statistics")
    print("=" * 50)
    
    users = conversation_memory.get_all_users_with_conversations()
    
    if not users:
        print("No users with conversation history found.")
        return
    
    total_conversations = sum(user['conversation_count'] for user in users)
    
    print(f"Total users in memory: {len(users)}")
    print(f"Total conversations stored: {total_conversations}")
    print()
    
    print("User breakdown:")
    for user in users[:10]:  # Show top 10
        print(f"  {user['user_id']}: {user['conversation_count']} conversations")
        print(f"    First: {user['first_conversation']}")
        print(f"    Last:  {user['last_conversation']}")
        print()

def cleanup_confirmed_users():
    """Clean up memory for users who are already confirmed"""
    try:
        # Read CSV to get confirmed users
        df = pd.read_csv("leads.csv")
        confirmed_users = df[df['status'] == 'confirmed']['lead_id'].tolist()
        
        if not confirmed_users:
            print("No confirmed users found in CSV.")
            return
        
        print(f"Found {len(confirmed_users)} confirmed users in CSV:")
        for user in confirmed_users:
            print(f"  - {user}")
        
        # Check which ones have memory
        users_with_memory = conversation_memory.get_all_users_with_conversations()
        user_ids_with_memory = [user['user_id'] for user in users_with_memory]
        
        confirmed_with_memory = [user for user in confirmed_users if user in user_ids_with_memory]
        
        if not confirmed_with_memory:
            print("None of the confirmed users have conversation memory to clean.")
            return
        
        print(f"\nCleaning memory for {len(confirmed_with_memory)} confirmed users:")
        for user in confirmed_with_memory:
            print(f"  - {user}")
        
        # Confirm with user
        response = input(f"\nProceed with cleanup? (y/N): ").strip().lower()
        if response == 'y':
            total_cleaned = conversation_memory.cleanup_confirmed_users(confirmed_with_memory)
            print(f"✅ Cleanup completed: {total_cleaned} conversations cleared!")
        else:
            print("Cleanup cancelled.")
            
    except Exception as e:
        print(f"Error during cleanup: {e}")

def cleanup_specific_user():
    """Clean up memory for a specific user"""
    user_id = input("Enter user ID to clean up: ").strip()
    
    if not user_id:
        print("No user ID provided.")
        return
    
    count = conversation_memory.get_user_conversation_count(user_id)
    
    if count == 0:
        print(f"No conversations found for user: {user_id}")
        return
    
    print(f"User '{user_id}' has {count} conversations.")
    response = input(f"Delete all conversations for this user? (y/N): ").strip().lower()
    
    if response == 'y':
        cleared = conversation_memory.clear_user_conversations(user_id)
        print(f"✅ Cleared {cleared} conversations for user: {user_id}")
    else:
        print("Cleanup cancelled.")

def main():
    """Main menu"""
    while True:
        print("\n🧹 Conversation Memory Manager")
        print("=" * 40)
        print("1. Show memory statistics")
        print("2. Cleanup confirmed users")
        print("3. Cleanup specific user")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            show_memory_stats()
        elif choice == '2':
            cleanup_confirmed_users()
        elif choice == '3':
            cleanup_specific_user()
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 