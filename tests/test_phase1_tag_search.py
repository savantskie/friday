"""
Test Phase 1: Tag-based search with OR logic and memory_bank filtering
Uses MCP server tools to test the new tags and memory_bank parameters added to search_memories()
"""

import asyncio
import sys
from pathlib import Path

# Add Friday to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from friday_memory_mcp_server import FridayMemoryMCPServer


async def test_tag_search_or_logic(mcp_server):
    """Test that tag search uses OR logic (matches ANY tag provided)"""
    print("\n" + "="*60)
    print("TEST 1: Tag Search OR Logic (via Memory System)")
    print("="*60)
    
    try:
        # Access the memory system through the MCP server
        memory_system = mcp_server.memory_system
        
        # Create test memories with different tags
        print("\n1. Creating test memories with tags...")
        
        # Memory 1: project + goal tags
        mem1_result = await memory_system.create_memory(
            content="Work on AI integration project",
            memory_type="task",
            importance_level=8,
            tags=["project", "goal"],
            memory_bank="Work",
            user_id="nate",
            model_id="Eddie"
        )
        mem1_id = mem1_result.get('memory_id', 'unknown')
        print(f"   Created memory 1 (tags: project, goal): {mem1_id}")
        
        # Memory 2: health + reminder tags
        mem2_result = await memory_system.create_memory(
            content="Morning health check reminder",
            memory_type="reminder",
            importance_level=7,
            tags=["health", "reminder"],
            memory_bank="Personal",
            user_id="nate",
            model_id="Eddie"
        )
        mem2_id = mem2_result.get('memory_id', 'unknown')
        print(f"   Created memory 2 (tags: health, reminder): {mem2_id}")
        
        # Memory 3: project + deadline tags
        mem3_result = await memory_system.create_memory(
            content="Project deadline approaching next week",
            memory_type="alert",
            importance_level=9,
            tags=["project", "deadline"],
            memory_bank="Work",
            user_id="nate",
            model_id="Eddie"
        )
        mem3_id = mem3_result.get('memory_id', 'unknown')
        print(f"   Created memory 3 (tags: project, deadline): {mem3_id}")
        
        # Memory 4: no tags (should not be returned when tags filter is specified)
        mem4_result = await memory_system.create_memory(
            content="General note without tags",
            memory_type="note",
            importance_level=5,
            memory_bank="General",
            user_id="nate",
            model_id="Eddie"
        )
        mem4_id = mem4_result.get('memory_id', 'unknown')
        print(f"   Created memory 4 (no tags): {mem4_id}")
        
        # Give system time to process
        await asyncio.sleep(2)
        
        # Test 1a: Search for "project" tag only
        print("\n2. Searching for memories with 'project' tag (OR logic)...")
        result = await memory_system.search_memories(
            query="work",
            limit=10,
            tags=["project"],
            user_id="nate",
            model_id="Eddie"
        )
        
        print(f"   Query result status: {result.get('status')}")
        print(f"   Found {result.get('count', 0)} memories with 'project' tag")
        
        if result.get('count', 0) >= 2:
            print("   ✅ PASS: Found memories with 'project' tag (should be >= 2)")
            for mem in result.get('results', []):
                print(f"      - {mem['data']['memory_id']}: tags={mem['data'].get('tags')}")
        else:
            print(f"   ❌ FAIL: Expected >= 2 memories with 'project' tag, got {result.get('count', 0)}")
        
        # Test 1b: Search for multiple tags with OR logic
        print("\n3. Searching for 'project' OR 'health' tags...")
        result = await memory_system.search_memories(
            query="important",
            limit=10,
            tags=["project", "health"],
            user_id="nate",
            model_id="Eddie"
        )
        
        print(f"   Found {result.get('count', 0)} memories with 'project' OR 'health' tags")
        
        if result.get('count', 0) >= 3:
            print("   ✅ PASS: Found memories with 'project' OR 'health' (should be >= 3)")
            for mem in result.get('results', []):
                print(f"      - {mem['data']['memory_id']}: tags={mem['data'].get('tags')}")
        else:
            print(f"   ❌ FAIL: Expected >= 3 memories, got {result.get('count', 0)}")
        
        # Test 1c: Search with memory_bank filter
        print("\n4. Searching for 'project' tag in 'Work' memory_bank...")
        result = await memory_system.search_memories(
            query="work",
            limit=10,
            tags=["project"],
            memory_bank="Work",
            user_id="nate",
            model_id="Eddie"
        )
        
        print(f"   Found {result.get('count', 0)} memories in Work bank with 'project' tag")
        
        if result.get('count', 0) >= 2:
            print("   ✅ PASS: Found correct memories in Work bank")
            for mem in result.get('results', []):
                print(f"      - {mem['data']['memory_id']}: bank={mem['data'].get('memory_type')}")
        else:
            print(f"   ❌ FAIL: Expected >= 2 memories in Work bank, got {result.get('count', 0)}")
        
        # Test 1d: Tag filter should exclude untagged memories
        print("\n5. Verifying untagged memories are excluded when tag filter applied...")
        result = await memory_system.search_memories(
            query="note",
            limit=10,
            tags=["nonexistent"],
            user_id="nate",
            model_id="Eddie"
        )
        
        print(f"   Found {result.get('count', 0)} memories with nonexistent tag")
        
        if result.get('count', 0) == 0:
            print("   ✅ PASS: Correctly excluded memories without matching tags")
        else:
            print(f"   ❌ FAIL: Should find 0 memories with nonexistent tag, got {result.get('count', 0)}")
        
        print("\n" + "="*60)
        print("Phase 1 Tag Search Tests Completed")
        print("="*60)
        
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()


async def test_model_isolation(mcp_server):
    """Test that model_id filtering still works correctly"""
    print("\n" + "="*60)
    print("TEST 2: Model Isolation Verification")
    print("="*60)
    
    try:
        # Access the memory system through the MCP server
        memory_system = mcp_server.memory_system
        
        # Create memory for model "Eddie"
        print("\n1. Creating memory for model 'Eddie'...")
        mem_eddie = await memory_system.create_memory(
            content="This memory is for Eddie model",
            memory_type="test",
            importance_level=7,
            tags=["model_test"],
            user_id="nate",
            model_id="Eddie"
        )
        print(f"   Created: {mem_eddie.get('memory_id', 'unknown')}")
        
        # Create memory for model "OtherModel"
        print("\n2. Creating memory for model 'OtherModel'...")
        mem_other = await memory_system.create_memory(
            content="This memory is for OtherModel",
            memory_type="test",
            importance_level=7,
            tags=["model_test"],
            user_id="nate",
            model_id="OtherModel"
        )
        print(f"   Created: {mem_other.get('memory_id', 'unknown')}")
        
        await asyncio.sleep(2)
        
        # Search as Eddie model
        print("\n3. Searching as 'Eddie' model with tag filter...")
        result = await memory_system.search_memories(
            query="model test",
            limit=10,
            tags=["model_test"],
            user_id="nate",
            model_id="Eddie"
        )
        
        print(f"   Found {result.get('count', 0)} memories")
        
        # Check that we only got Eddie's memory
        found_eddie = any(mem['data']['model_id'] == 'Eddie' for mem in result.get('results', []))
        found_other = any(mem['data']['model_id'] == 'OtherModel' for mem in result.get('results', []))
        
        if found_eddie and not found_other:
            print("   ✅ PASS: Model isolation working correctly (only Eddie's memories returned)")
        else:
            print(f"   ❌ FAIL: Model isolation broken (found_eddie={found_eddie}, found_other={found_other})")
        
        print("\n" + "="*60)
        print("Model Isolation Tests Completed")
        print("="*60)
        
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("PHASE 1 TAG SEARCH IMPLEMENTATION TESTS (Using MCP Server)")
    print("="*80)
    
    # Initialize MCP server
    mcp_server = FridayMemoryMCPServer()
    
    try:
        await test_tag_search_or_logic(mcp_server)
        await test_model_isolation(mcp_server)
    finally:
        # Server cleanup if needed
        pass
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
