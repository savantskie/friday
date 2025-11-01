#!/usr/bin/env python3
"""
Test and demonstrate the OpenWebUI chat isolation and remediation service.

This script:
1. Tests the fixed import_openwebui_chat_history with user_id + model isolation
2. Tests the verify_and_remediate_chat_isolation service
3. Verifies that chats are properly isolated by user and model
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from friday_memory_system import FridayMemorySystem


async def test_isolation_service():
    """Test the chat isolation and remediation service"""
    
    print("\n" + "="*80)
    print("FRIDAY MEMORY SYSTEM - CHAT ISOLATION & REMEDIATION SERVICE TEST")
    print("="*80 + "\n")
    
    # Initialize the memory system
    print("1. Initializing Friday Memory System...")
    memory_system = FridayMemorySystem()
    print("   ✓ Memory system initialized\n")
    
    # Test 1: Import OpenWebUI chat history with proper isolation
    print("2. Testing import_openwebui_chat_history with user_id + model isolation...")
    try:
        await memory_system.import_openwebui_chat_history()
        print("   ✓ Chat history imported successfully\n")
    except Exception as e:
        print(f"   ✗ Import failed: {e}\n")
        return False
    
    # Test 2: Run verification and remediation
    print("3. Running chat isolation verification and remediation...")
    try:
        stats = await memory_system.verify_and_remediate_chat_isolation()
        
        print(f"   Total messages analyzed: {stats.get('total_messages', 0)}")
        print(f"   Already isolated: {stats.get('already_isolated', 0)}")
        print(f"   Needing remediation: {stats.get('missing_isolation', 0)}")
        print(f"   Successfully remediated: {stats.get('remediations', 0)}")
        print(f"   Errors encountered: {stats.get('errors', 0)}")
        print()
        
        # Show some remediation details if any
        if stats.get('remediations', 0) > 0:
            print("   Sample remediations:")
            for detail in stats.get('details', [])[:5]:
                if detail.get('status') == 'remediated':
                    print(f"     - Message {detail.get('message_id')[:8]}...")
                    print(f"       Old: {detail.get('previous_conv_id')}")
                    print(f"       New: {detail.get('new_conv_id')} (user: {detail.get('user_id')}, model: {detail.get('model')})")
            print()
        
        # Show errors if any
        if stats.get('errors', 0) > 0:
            print("   Errors encountered:")
            for detail in stats.get('details', []):
                if 'issue' in detail or 'error' in detail.get('status', '').lower():
                    print(f"     - {detail}")
            print()
        
    except Exception as e:
        print(f"   ✗ Verification failed: {e}\n")
        return False
    
    # Test 3: Query to verify isolation in the database
    print("4. Verifying isolation in the database...")
    try:
        # Get unique conversation_ids that were imported
        unique_convs = await memory_system.conversations_db.execute_query(
            """SELECT DISTINCT conversation_id FROM messages 
               WHERE source_type = 'openwebui' 
               ORDER BY conversation_id"""
        )
        
        if unique_convs:
            print(f"   Found {len(unique_convs)} isolated conversation buckets:")
            
            # Show first 10
            for conv in unique_convs[:10]:
                conv_id = conv.get('conversation_id')
                
                # Count messages in this conversation
                msg_count = await memory_system.conversations_db.execute_query(
                    """SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?""",
                    (conv_id,)
                )
                count = msg_count[0].get('count', 0) if msg_count else 0
                
                # Parse the conversation_id to show user and model
                parts = conv_id.split('_')
                if len(parts) >= 2:
                    user_part = parts[0]
                    model_part = '_'.join(parts[1:])  # In case model name has underscores
                    print(f"     - {conv_id}")
                    print(f"       Messages: {count}, User segment: {user_part}, Model: {model_part}")
                else:
                    print(f"     - {conv_id} ({count} messages)")
            
            if len(unique_convs) > 10:
                print(f"     ... and {len(unique_convs) - 10} more conversation buckets")
        else:
            print("   No imported OpenWebUI messages found")
        
        print()
        
    except Exception as e:
        print(f"   ✗ Verification query failed: {e}\n")
        return False
    
    # Test 4: Show sample message content from each isolation bucket
    print("5. Sample messages from each isolation bucket:")
    try:
        unique_convs = await memory_system.conversations_db.execute_query(
            """SELECT DISTINCT conversation_id FROM messages 
               WHERE source_type = 'openwebui' 
               LIMIT 5"""
        )
        
        for conv in unique_convs:
            conv_id = conv.get('conversation_id')
            sample = await memory_system.conversations_db.execute_query(
                """SELECT role, content, timestamp FROM messages 
                   WHERE conversation_id = ? AND source_type = 'openwebui'
                   LIMIT 2""",
                (conv_id,)
            )
            
            print(f"\n   Conversation: {conv_id}")
            for msg in sample:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:100]
                print(f"     [{role}] {content}...")
        
        print("\n")
        
    except Exception as e:
        print(f"   ✗ Sample query failed: {e}\n")
        return False
    
    print("="*80)
    print("ISOLATION SERVICE TEST COMPLETE")
    print("="*80 + "\n")
    
    return True


async def main():
    """Main entry point"""
    try:
        success = await test_isolation_service()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
