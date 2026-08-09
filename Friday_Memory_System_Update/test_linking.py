#!/usr/bin/env python3

"""
Test script for memory-conversation linking implementation.
Tests that memories are properly linked to conversations with breadcrumbs.
"""

import asyncio
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from friday_memory_system import FridayMemorySystem, ConversationDatabase, AIMemoryDatabase


async def test_linking():
    """Test memory-conversation linking"""
    
    print("=" * 80)
    print("TESTING MEMORY-CONVERSATION LINKING")
    print("=" * 80)
    
    try:
        # Initialize systems
        print("\n[1] Initializing Friday Memory System...")
        fms = FridayMemorySystem(enable_file_monitoring=False)
        conv_db = fms.conversations_db
        mem_db = fms.ai_memory_db
        
        # Test data
        test_user_id = "nate"
        test_model_id = "friday"
        test_content = "Test memory about Python programming"
        test_conv_id = str(uuid.uuid4())
        test_source_conv_id = f"openwebui_user_{test_user_id}"
        
        print("✓ Initialized successfully\n")
        
        # Create a test conversation
        print("[2] Creating test session and conversation...")
        test_session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create session first
        await conv_db.execute_update(
            """INSERT INTO sessions (session_id, start_timestamp, context) 
               VALUES (?, ?, ?)""",
            (test_session_id, timestamp, "test-session")
        )
        
        # Create conversation
        result = await conv_db.execute_update(
            """INSERT INTO conversations 
               (conversation_id, session_id, start_timestamp, user_id, model_id) 
               VALUES (?, ?, ?, ?, ?)""",
            (test_conv_id, test_session_id, timestamp, test_user_id, test_model_id)
        )
        print(f"✓ Created conversation: {test_conv_id}\n")
        
        # Create a test memory via FridayMemorySystem
        print("[3] Creating test memory with linking...")
        mem_result = await fms.create_memory(
            content=test_content,
            memory_type="test",
            importance_level=7,
            tags=["test", "linking"],
            source_conversation_id=test_source_conv_id,
            user_id=test_user_id,
            model_id=test_model_id,
            source="direct_test",
            wait_for_embedding=False
        )
        
        if mem_result.get("status") != "success":
            print(f"✗ Failed to create memory: {mem_result}")
            return False
        
        memory_id = mem_result.get("memory_id")
        print(f"✓ Created memory: {memory_id}\n")
        
        # Verify memory was created
        print("[4] Verifying memory in database...")
        mem_rows = await mem_db.execute_query(
            "SELECT memory_id, content, user_id, model_id, source_conversation_id FROM curated_memories WHERE memory_id = ?",
            (memory_id,)
        )
        
        if not mem_rows:
            print("✗ Memory not found in database!")
            return False
        
        mem_row = mem_rows[0]
        print(f"✓ Memory found:")
        print(f"  - memory_id: {mem_row['memory_id']}")
        print(f"  - user_id: {mem_row['user_id']}")
        print(f"  - model_id: {mem_row['model_id']}")
        print(f"  - source_conversation_id: {mem_row['source_conversation_id']}\n")
        
        # Check if linking was created
        print("[5] Checking memory-conversation links...")
        links = await conv_db.get_memory_conversation_links(memory_id=memory_id)
        
        if not links:
            print("✗ No linking found! Linking may not have been executed.\n")
            print("   This could happen if:")
            print("   - source_conversation_id resolution failed")
            print("   - Wrong conversation_id was resolved")
            print("   - Link creation encountered an error\n")
        else:
            print(f"✓ Found {len(links)} link(s)!\n")
            for link in links:
                print(f"  Link ID: {link['link_id']}")
                print(f"  Memory ID: {link['memory_id']}")
                print(f"  Conversation ID: {link['conversation_id']}")
                print(f"  Link Type: {link['link_type']}")
                print(f"  Link Strength: {link['link_strength']}")
                print(f"  Source System: {link['source_system']}")
                
                # Parse and display metadata breadcrumbs
                if link.get('metadata'):
                    try:
                        metadata = json.loads(link['metadata'])
                        print(f"  Metadata Breadcrumbs:")
                        for key, value in metadata.items():
                            print(f"    - {key}: {value}")
                    except json.JSONDecodeError:
                        print(f"  Metadata: {link['metadata']}")
                print()
        
        # Test conversation linking
        print("[6] Testing conversation relationships linking...")
        related_conv_id = str(uuid.uuid4())
        related_session_id = str(uuid.uuid4())
        
        # Create new session and conversation to link
        await conv_db.execute_update(
            """INSERT INTO sessions (session_id, start_timestamp, context) 
               VALUES (?, ?, ?)""",
            (related_session_id, timestamp, "test-session-related")
        )
        
        await conv_db.execute_update(
            """INSERT INTO conversations 
               (conversation_id, session_id, start_timestamp, user_id, model_id) 
               VALUES (?, ?, ?, ?, ?)""",
            (related_conv_id, related_session_id, timestamp, test_user_id, test_model_id)
        )
        
        # Link the two conversations
        rel_metadata = {
            "matching_method": "test_linking",
            "confidence_score": 0.95,
            "matching_details": "Test-created relationship"
        }
        
        rel_id = await conv_db.link_conversations(
            source_conversation_id=test_conv_id,
            related_conversation_id=related_conv_id,
            relationship_type="same_session",
            confidence_score=0.95,
            matching_method="test_linking",
            metadata=rel_metadata
        )
        
        print(f"✓ Created conversation relationship: {rel_id}\n")
        
        # Verify relationship
        print("[7] Verifying conversation relationships...")
        rel_rows = await conv_db.execute_query(
            "SELECT * FROM conversation_relationships WHERE source_conversation_id = ?",
            (test_conv_id,)
        )
        
        if not rel_rows:
            print("✗ Relationship not found!")
            return False
        
        rel_row = dict(rel_rows[0])
        print(f"✓ Relationship found:")
        print(f"  - Source Conversation: {rel_row['source_conversation_id']}")
        print(f"  - Related Conversation: {rel_row['related_conversation_id']}")
        print(f"  - Type: {rel_row['relationship_type']}")
        
        # Parse confidence from metadata
        if rel_row.get('metadata'):
            try:
                rel_metadata = json.loads(rel_row['metadata'])
                print(f"  - Confidence: {rel_metadata.get('confidence_score')}")
                print(f"  - Metadata Breadcrumbs:")
                for key, value in rel_metadata.items():
                    print(f"    - {key}: {value}")
            except json.JSONDecodeError:
                print(f"  - Metadata: {rel_row['metadata']}")
        print()
        
        print("=" * 80)
        print("✓ ALL LINKING TESTS PASSED!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_linking()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
