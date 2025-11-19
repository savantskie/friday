#!/usr/bin/env python3
"""
Test script for POST /api/memories/promote endpoint

This tests the new HTTP API endpoint that promotes memories from short-term
(OpenWebUI) to long-term (Friday Memory System) storage.

Usage:
    python test_promote_endpoint.py

Prerequisites:
    - MCP server running with HTTP API enabled: python friday_memory_mcp_server.py
    - FastAPI and uvicorn installed
    - requests library installed
"""

import asyncio
import requests
import json
import time
from pathlib import Path
import os

# Configuration
API_BASE = "http://127.0.0.1:21434"

# Load API key from mcpo_api_key.txt file (same as MCP server)
API_KEY = None
try:
    key_file = Path(__file__).parent.parent / "keys" / "mcpo_api_key.txt"
    if key_file.exists():
        with open(key_file, 'r') as f:
            API_KEY = f.read().strip()
except Exception as e:
    print(f"⚠️  Error loading API key: {e}")

if not API_KEY:
    print("❌ Could not load API key from keys/mcpo_api_key.txt")
    exit(1)

PROMOTE_ENDPOINT = f"{API_BASE}/api/memories/promote"
HEALTH_ENDPOINT = f"{API_BASE}/api/health"

# Test data
TEST_MEMORIES = [
    {
        "content": "I enjoy drinking coffee every morning",
        "memory_type": "preference",
        "tags": ["habits", "morning", "test"],  # Mark as test memory
        "source_conversation_id": "test_session_001"
    },
    {
        "content": "My primary LLM is Qwen 7B installed in LM Studio at 192.168.1.50:1234",
        "memory_type": "technical_config",
        "tags": ["llm", "infrastructure", "test"],  # Mark as test memory
        "source_conversation_id": "test_session_001"
    },
    {
        "content": "I have ADHD and memory challenges from four strokes since 2016",
        "memory_type": "personal_medical",
        "tags": ["health", "context", "test"],  # Mark as test memory
        "source_conversation_id": "test_session_001"
    },
]

def check_health():
    """Check if HTTP API server is running and healthy"""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            print("✅ HTTP API server is healthy")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ HTTP API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to HTTP API server")
        print(f"   Make sure MCP server is running: python friday_memory_mcp_server.py")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def promote_memory(content, memory_type=None, tags=None, source_conversation_id=None):
    """
    Test promoting a memory to long-term storage
    
    Args:
        content: Memory content (required)
        memory_type: Optional memory type
        tags: Optional list of tags
        source_conversation_id: Optional source conversation ID
    
    Returns:
        tuple: (success: bool, response_data: dict, status_code: int)
    """
    
    payload = {
        "content": content,
    }
    
    if memory_type:
        payload["memory_type"] = memory_type
    if tags:
        payload["tags"] = tags
    if source_conversation_id:
        payload["source_conversation_id"] = source_conversation_id
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(PROMOTE_ENDPOINT, json=payload, headers=headers, timeout=10)
        
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw": response.text}
        
        success = response.status_code == 200
        return success, response_data, response.status_code
        
    except requests.exceptions.Timeout:
        return False, {"error": "Request timeout"}, None
    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot connect to API"}, None
    except Exception as e:
        return False, {"error": str(e)}, None


def test_promote_single_memory():
    """Test promoting a single memory"""
    print("\n" + "="*70)
    print("TEST 1: Promote Single Memory")
    print("="*70)
    
    test_memory = TEST_MEMORIES[0]
    print(f"\nPromoting memory: {test_memory['content'][:50]}...")
    
    success, response, status = promote_memory(
        content=test_memory["content"],
        memory_type=test_memory.get("memory_type"),
        tags=test_memory.get("tags"),
        source_conversation_id=test_memory.get("source_conversation_id")
    )
    
    if success:
        print(f"✅ SUCCESS (HTTP {status})")
        print(f"   Memory ID: {response.get('memory_id')}")
        print(f"   Importance Level: {response.get('importance_level')}")
        print(f"   Status: {response.get('status')}")
        print(f"   Message: {response.get('message')}")
        return response.get('memory_id')
    else:
        print(f"❌ FAILED (HTTP {status})")
        print(f"   Error: {response}")
        return None


def test_promote_multiple_memories():
    """Test promoting multiple memories"""
    print("\n" + "="*70)
    print("TEST 2: Promote Multiple Memories")
    print("="*70)
    
    promoted_ids = []
    
    for i, test_memory in enumerate(TEST_MEMORIES, 1):
        print(f"\n[{i}/{len(TEST_MEMORIES)}] Promoting: {test_memory['content'][:50]}...")
        
        success, response, status = promote_memory(
            content=test_memory["content"],
            memory_type=test_memory.get("memory_type"),
            tags=test_memory.get("tags"),
            source_conversation_id=test_memory.get("source_conversation_id")
        )
        
        if success:
            print(f"   ✅ Promoted with ID: {response.get('memory_id')}")
            promoted_ids.append(response.get('memory_id'))
        else:
            print(f"   ❌ Failed: {response}")
        
        # Small delay between requests
        time.sleep(0.5)
    
    print(f"\n📊 Summary: {len(promoted_ids)}/{len(TEST_MEMORIES)} memories promoted successfully")
    return promoted_ids


def test_missing_api_key():
    """Test that API key is required"""
    print("\n" + "="*70)
    print("TEST 3: Verify API Key Requirement")
    print("="*70)
    
    payload = {
        "content": "This memory should fail - no API key"
    }
    
    headers = {
        "Content-Type": "application/json"
        # Intentionally missing X-API-Key
    }
    
    try:
        response = requests.post(PROMOTE_ENDPOINT, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 403:
            print(f"✅ API key validation working (HTTP 403)")
            print(f"   Response: {response.json().get('detail', response.text)}")
            return True
        else:
            print(f"❌ Expected 403, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_missing_content():
    """Test that content is required"""
    print("\n" + "="*70)
    print("TEST 4: Verify Content is Required")
    print("="*70)
    
    payload = {
        "memory_type": "test",
        # Intentionally missing content
    }
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(PROMOTE_ENDPOINT, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 400:
            print(f"✅ Content validation working (HTTP 400)")
            print(f"   Response: {response.json().get('detail', response.text)}")
            return True
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            print(f"   Response: {response.json()}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def cleanup_test_memories():
    """Clean up all test memories created during testing"""
    print("\n" + "="*70)
    print("CLEANUP: Removing Test Memories")
    print("="*70)
    
    cleanup_endpoint = f"{API_BASE}/api/memories/cleanup"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # First, do a dry run to see how many memories will be deleted
        response = requests.delete(
            cleanup_endpoint,
            params={"tag": "test", "dry_run": "true"},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get("deleted_count", 0)
            print(f"DRY RUN: Found {count} test memories to clean up")
            
            if count > 0:
                # Actually delete them
                print(f"🧹 Deleting {count} test memories...")
                response = requests.delete(
                    cleanup_endpoint,
                    params={"tag": "test", "dry_run": "false"},
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deleted = data.get("deleted_count", 0)
                    print(f"✅ Cleaned up {deleted} test memories")
                    return True
                else:
                    print(f"❌ Cleanup failed (HTTP {response.status_code})")
                    print(f"   Response: {response.json()}")
                    return False
            else:
                print("ℹ️  No test memories to clean up")
                return True
        else:
            print(f"❌ Cleanup check failed (HTTP {response.status_code})")
            print(f"   Response: {response.json()}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Cannot connect to cleanup endpoint")
        return False
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("FRIDAY MEMORY API - PROMOTE ENDPOINT TESTS")
    print("="*70)
    
    # Check if API is running
    if not check_health():
        print("\n⚠️  Tests cannot run - API server not responding")
        print("Start the MCP server first: python friday_memory_mcp_server.py")
        return False
    
    # Run tests
    results = {
        "health_check": True,
        "single_memory": False,
        "multiple_memories": False,
        "api_key_validation": False,
        "content_validation": False,
    }
    
    # Test single memory promotion
    memory_id = test_promote_single_memory()
    results["single_memory"] = memory_id is not None
    
    # Test multiple promotions
    promoted_ids = test_promote_multiple_memories()
    results["multiple_memories"] = len(promoted_ids) > 0
    
    # Test security - API key required
    results["api_key_validation"] = test_missing_api_key()
    
    # Test validation - content required
    results["content_validation"] = test_missing_content()
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n📊 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The promote endpoint is working correctly.")
        print("\nCleaning up test memories...")
        cleanup_success = cleanup_test_memories()
        
        if cleanup_success:
            print("\n✅ Test cleanup complete!")
        else:
            print("\n⚠️  Test cleanup had issues (see above)")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. See details above.")
        print("\nNote: Test memories will remain in database for manual review.")
        print("To clean up: curl -X DELETE http://127.0.0.1:21434/api/memories/cleanup -H 'X-API-Key: 0d4b94f58f5a401ea88b149a17f09fc9'?tag=test")
        return False


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⛔ Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
