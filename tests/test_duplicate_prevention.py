#!/usr/bin/env python3
"""Test the duplicate prevention fix for file monitoring"""

import asyncio
import json
import tempfile
import os
from friday_memory_system import FridayMemorySystem

async def test_duplicate_prevention():
    print("🧪 Testing Duplicate Prevention in File Monitoring...")
    
    memory = FridayMemorySystem()
    
    # Test 1: Direct duplicate detection
    print("\n1️⃣ Testing direct message duplicate detection...")
    
    session_id = "test_session_123"
    
    # Store first message
    result1 = await memory.conversations_db.store_message(
        content="This is a test message",
        role="user", 
        session_id=session_id
    )
    print(f"   First message: {result1['message_id'][:8]}... (duplicate: {result1.get('duplicate', False)})")
    
    # Try to store exact duplicate
    result2 = await memory.conversations_db.store_message(
        content="This is a test message",
        role="user",
        session_id=session_id
    )
    print(f"   Duplicate attempt: {result2['message_id'][:8]}... (duplicate: {result2.get('duplicate', False)})")
    
    # Store different message
    result3 = await memory.conversations_db.store_message(
        content="This is a different message", 
        role="user",
        session_id=session_id
    )
    print(f"   Different message: {result3['message_id'][:8]}... (duplicate: {result3.get('duplicate', False)})")
    
    # Test 2: File monitoring duplicate prevention
    print("\n2️⃣ Testing file monitoring with VS Code format...")
    
    # Create a test VS Code chat file
    test_data = {
        "version": "1.0",
        "requesterUsername": "test_user",
        "responderUsername": "copilot",
        "requests": [
            {
                "requestId": "test_req_1",
                "message": {"text": "Hello, this is a test question"},
                "response": {"result": {"markdown": "Hello! This is a test response"}}
            },
            {
                "requestId": "test_req_2", 
                "message": {"text": "Another test question"},
                "response": {"result": {"markdown": "Another test response"}}
            }
        ]
    }
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='_chatSessions.json', delete=False) as f:
        json.dump(test_data, f, indent=2)
        temp_file = f.name
    
    try:
        # Import file first time
        print(f"   Importing test file first time...")
        await memory.file_monitor._import_vscode_chat_session(temp_file, json.dumps(test_data))
        
        # Import same file again (should detect duplicates)
        print(f"   Importing same file again (should detect duplicates)...")
        await memory.file_monitor._import_vscode_chat_session(temp_file, json.dumps(test_data))
        
        # Check message count
        health = await memory.get_system_health()
        message_count = health['databases']['conversations']['message_count']
        print(f"   Total messages in database: {message_count}")
        
    finally:
        os.unlink(temp_file)
    
    print("\n✅ Duplicate prevention test completed!")
    print("   If working correctly:")
    print("   - Second direct duplicate should be marked as duplicate=True")
    print("   - File re-import should not increase message count significantly")

if __name__ == "__main__":
    asyncio.run(test_duplicate_prevention())
