#!/usr/bin/env python3
"""
Phase 1 Investigation: Database Schema & State
Queries webui.db and conversations.db to understand linking strategy
"""

import sqlite3
import json
from pathlib import Path

def query_db(db_path, query, description):
    """Query a database and return results"""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"Database: {db_path}")
    print(f"Query: {query}")
    print(f"{'='*80}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            # Print header
            if rows:
                headers = list(rows[0].keys())
                print("\nColumns:", headers)
                print(f"\nResults ({len(rows)} rows):")
                for i, row in enumerate(rows[:10]):  # Limit to first 10
                    print(f"  Row {i}: {dict(row)}")
                if len(rows) > 10:
                    print(f"  ... and {len(rows) - 10} more rows")
        else:
            print("\n✓ Query returned 0 rows")
        
        conn.close()
        return rows
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return []

def get_schema(db_path, table_name):
    """Get schema for a table"""
    print(f"\n{'='*80}")
    print(f"TABLE SCHEMA: {table_name}")
    print(f"Database: {db_path}")
    print(f"{'='*80}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print(f"\nColumns in {table_name}:")
        for col in columns:
            cid, name, type_, notnull, dflt_value, pk = col
            print(f"  - {name}: {type_} (PK={bool(pk)}, NOT NULL={bool(notnull)})")
        
        conn.close()
        return columns
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return []

# Paths
webui_db = "/media/nate/Friday/OpenWebUI/data/webui.db"
fms_db = "/media/nate/Friday/Friday/data/memory/Memories/conversations.db"

print("\n" + "="*80)
print("PHASE 1 INVESTIGATION: Conversation Linking System")
print("="*80)

# ============================================================================
# 1. OPENWEBUI DATABASE INVESTIGATION
# ============================================================================

print("\n" + "█"*80)
print("█  SECTION 1: OpenWebUI Database (webui.db)")
print("█"*80)

# Get conversations table schema
get_schema(webui_db, "conversations")

# Check table list
print("\n" + "-"*80)
print("All tables in webui.db:")
print("-"*80)
query_db(webui_db, 
         "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;",
         "List all tables")

# Get sample conversations
query_db(webui_db,
         "SELECT * FROM conversations LIMIT 5;",
         "Sample conversations (first 5)")

# Get conversations count and stats
query_db(webui_db,
         "SELECT COUNT(*) as total_conversations FROM conversations;",
         "Total conversations count")

# ============================================================================
# 2. FMS DATABASE INVESTIGATION
# ============================================================================

print("\n" + "█"*80)
print("█  SECTION 2: FMS Database (conversations.db)")
print("█"*80)

# Get conversation_relationships schema
get_schema(fms_db, "conversation_relationships")

# Check if conversation_relationships has any rows
query_db(fms_db,
         "SELECT COUNT(*) as total_relationships FROM conversation_relationships;",
         "conversation_relationships row count")

# Get sample conversation_relationships
query_db(fms_db,
         "SELECT * FROM conversation_relationships LIMIT 5;",
         "Sample conversation_relationships (first 5)")

# Check conversations table
print("\n" + "-"*80)
get_schema(fms_db, "conversations")

query_db(fms_db,
         "SELECT COUNT(*) as total FROM conversations;",
         "Total conversations in FMS")

query_db(fms_db,
         "SELECT * FROM conversations LIMIT 3;",
         "Sample FMS conversations (first 3)")

# Check messages table
print("\n" + "-"*80)
get_schema(fms_db, "messages")

query_db(fms_db,
         """SELECT 
              COUNT(*) as total,
              COUNT(DISTINCT session_id) as unique_sessions,
              COUNT(DISTINCT conversation_id) as unique_conversations,
              COUNT(DISTINCT user_id) as unique_users,
              COUNT(DISTINCT model_id) as unique_models
           FROM messages;""",
         "FMS messages stats")

# Sample messages with user/model info
query_db(fms_db,
         """SELECT 
              message_id, conversation_id, session_id, 
              user_id, model_id, role, 
              substr(content, 1, 50) as content_preview
           FROM messages 
           LIMIT 5;""",
         "Sample FMS messages with user/model info")

# ============================================================================
# 3. MATCHING ANALYSIS
# ============================================================================

print("\n" + "█"*80)
print("█  SECTION 3: Matching Analysis")
print("█"*80)

# Check sessions with multiple conversations
query_db(fms_db,
         """SELECT 
              session_id, 
              COUNT(DISTINCT conversation_id) as num_conversations,
              COUNT(*) as total_messages
           FROM messages
           GROUP BY session_id
           HAVING num_conversations > 1
           LIMIT 5;""",
         "Sessions with multiple conversations (fragmentation check)")

# Check for NULL user_id or model_id
query_db(fms_db,
         """SELECT 
              user_id, model_id, COUNT(*) as message_count
           FROM messages
           WHERE user_id IS NULL OR model_id IS NULL
           GROUP BY user_id, model_id;""",
         "Messages with NULL user_id or model_id")

print("\n" + "="*80)
print("PHASE 1 INVESTIGATION COMPLETE")
print("="*80)
print("\nSee results above for:")
print("1. OpenWebUI conversation structure")
print("2. FMS conversation_relationships state")
print("3. Current data consistency issues")
