import sqlite3
import json
from datetime import datetime

def check_conversations_db():
    print("Checking conversations database...")
    try:
        conn = sqlite3.connect('memory_data/conversations.db')
        cursor = conn.cursor()
        
        # Get table structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nTables found:", [t[0] for t in tables])
        
        # Get messages table structure
        cursor.execute("PRAGMA table_info(messages)")
        columns = cursor.fetchall()
        print("\nMessages table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
            
        # Get recent messages
        cursor.execute("""
            SELECT role, content, source_type, timestamp 
            FROM messages 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        
        print("\nMost recent messages:")
        print("-" * 80)
        for row in cursor.fetchall():
            print(f"\nRole: {row[0]}")
            print(f"Source: {row[2]}")
            print(f"Time: {row[3]}")
            print(f"Content (first 200 chars): {row[1][:200]}...")
            print("-" * 80)
            
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_conversations_db()
