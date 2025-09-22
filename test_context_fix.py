#!/usr/bin/env python3

"""
Test script to verify get_recent_context returns clean data without embeddings
"""

import asyncio
import json
import sys
import os

# Add the Friday directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from friday_memory_system import FridayMemorySystem

async def test_recent_context():
    """Test that get_recent_context returns clean data without embeddings"""
    
    print("Testing get_recent_context function...")
    
    # Initialize memory system
    memory_system = FridayMemorySystem()
    
    try:
        # Get recent context
        result = await memory_system.get_recent_context(limit=3, days_back=30)
        
        print(f"Status: {result['status']}")
        print(f"Count: {result['count']}")
        print(f"Days back: {result['days_back']}")
        
        if result['messages']:
            print("\nMessages:")
            for i, msg in enumerate(result['messages'], 1):
                print(f"\n--- Message {i} ---")
                print(f"Message ID: {msg['message_id']}")
                print(f"Role: {msg['role']}")
                print(f"Timestamp: {msg['timestamp']}")
                print(f"Content length: {len(msg['content'])} characters")
                print(f"Content preview: {msg['content'][:100]}...")
                
                # Check if embedding data is present (it shouldn't be)
                if 'embedding' in msg:
                    print("❌ ERROR: Embedding data found in message!")
                    return False
                else:
                    print("✅ No embedding data found (good)")
                    
                # Show available keys
                print(f"Available keys: {list(msg.keys())}")
        else:
            print("No messages found in recent context")
            
        print("\n✅ Test passed - get_recent_context returned clean data without embeddings")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_search_functionality():
    """Test that search_memories actually works for semantic search"""
    
    print("\n" + "="*60)
    print("Testing search_memories semantic search functionality...")
    
    memory_system = FridayMemorySystem()
    
    try:
        # Test semantic search
        search_query = "Friday memory system"
        result = await memory_system.search_memories(search_query, limit=3)
        
        print(f"Search query: '{search_query}'")
        print(f"Status: {result['status']}")
        print(f"Count: {result['count']}")
        
        if result['results']:
            print("\nSearch Results:")
            for i, item in enumerate(result['results'], 1):
                print(f"\n--- Result {i} ---")
                print(f"Type: {item['type']}")
                print(f"Similarity Score: {item['similarity_score']:.4f}")
                
                if 'data' in item:
                    data = item['data']
                    if 'content' in data:
                        print(f"Content preview: {data['content'][:100]}...")
                    elif 'title' in data:
                        print(f"Title: {data['title']}")
                        
        print("\n✅ Search functionality test completed")
        return True
        
    except Exception as e:
        print(f"❌ Search test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    async def main():
        print("Friday Memory System - Recent Context Test")
        print("=" * 60)
        
        success1 = await test_recent_context()
        success2 = await test_search_functionality()
        
        if success1 and success2:
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)
    
    asyncio.run(main())