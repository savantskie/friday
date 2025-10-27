#!/usr/bin/env python3

"""
Comprehensive test to verify all search functions work properly with embeddings
"""

import asyncio
import json
import sys
import os

# Add the Friday directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from friday_memory_system import FridayMemorySystem

async def test_comprehensive_search():
    """Test all search functionality to ensure embeddings are being used properly"""
    
    print("=== COMPREHENSIVE SEARCH FUNCTIONALITY TEST ===")
    memory_system = FridayMemorySystem()
    
    test_results = []
    
    # Test 1: Basic semantic search
    print("\n1. Testing basic semantic search...")
    try:
        result = await memory_system.search_memories("Friday AI assistant", limit=3)
        success = result['status'] == 'success' and result['count'] > 0
        print(f"   Status: {result['status']}, Count: {result['count']}")
        if success and result['results']:
            print(f"   Top result similarity: {result['results'][0]['similarity_score']:.4f}")
        test_results.append(("Basic semantic search", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("Basic semantic search", False))
    
    # Test 2: Search with database filter - conversations only
    print("\n2. Testing conversation-only search...")
    try:
        result = await memory_system.search_memories("programming", limit=3, database_filter="conversations")
        success = result['status'] == 'success'
        print(f"   Status: {result['status']}, Count: {result['count']}")
        if result['results']:
            conv_types = [r['type'] for r in result['results']]
            print(f"   Result types: {conv_types}")
            success = success and all(t == 'conversation' for t in conv_types)
        test_results.append(("Conversation-only search", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("Conversation-only search", False))
    
    # Test 3: Search with database filter - AI memories only
    print("\n3. Testing AI memories-only search...")
    try:
        result = await memory_system.search_memories("system", limit=3, database_filter="ai_memories")
        success = result['status'] == 'success'
        print(f"   Status: {result['status']}, Count: {result['count']}")
        if result['results']:
            memory_types = [r['type'] for r in result['results']]
            print(f"   Result types: {memory_types}")
            success = success and all(t == 'ai_memory' for t in memory_types)
        test_results.append(("AI memories-only search", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("AI memories-only search", False))
    
    # Test 4: Search with importance filtering
    print("\n4. Testing importance-filtered search...")
    try:
        result = await memory_system.search_memories("Friday", limit=5, min_importance=7)
        success = result['status'] == 'success'
        print(f"   Status: {result['status']}, Count: {result['count']}")
        if result['results']:
            for r in result['results']:
                if r['type'] == 'ai_memory' and 'importance_level' in r['data']:
                    print(f"   Importance level: {r['data']['importance_level']}")
        test_results.append(("Importance-filtered search", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("Importance-filtered search", False))
    
    # Test 5: Verify recent context doesn't contain embeddings
    print("\n5. Testing get_recent_context (should NOT contain embeddings)...")
    try:
        result = await memory_system.get_recent_context(limit=2)
        success = result['status'] == 'success'
        has_embeddings = False
        
        if result['messages']:
            for msg in result['messages']:
                if 'embedding' in msg:
                    has_embeddings = True
                    break
        
        success = success and not has_embeddings
        print(f"   Status: {result['status']}, Count: {result['count']}")
        print(f"   Contains embeddings: {has_embeddings} (should be False)")
        test_results.append(("Recent context clean", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("Recent context clean", False))
    
    # Test 6: Test embedding generation is working
    print("\n6. Testing embedding generation...")
    try:
        embedding = await memory_system.embedding_service.generate_embedding("test query")
        success = embedding is not None and len(embedding) > 0
        print(f"   Embedding generated: {success}")
        if embedding:
            print(f"   Embedding dimensions: {len(embedding)}")
        test_results.append(("Embedding generation", success))
    except Exception as e:
        print(f"   ERROR: {e}")
        test_results.append(("Embedding generation", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY:")
    print("="*60)
    
    passed = 0
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(test_results)}")
    
    if passed == len(test_results):
        print("\n🎉 ALL TESTS PASSED! Search functionality is working correctly.")
        return True
    else:
        print(f"\n❌ {len(test_results) - passed} tests failed")
        return False

if __name__ == "__main__":
    async def main():
        success = await test_comprehensive_search()
        sys.exit(0 if success else 1)
    
    asyncio.run(main())