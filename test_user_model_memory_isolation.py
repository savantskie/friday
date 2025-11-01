#!/usr/bin/env python3
"""
Test script to verify user+model memory isolation in Friday Memory System
Tests that memories are properly separated by user_id and model
"""

import asyncio
import uuid
from friday_memory_system import FridayMemorySystem, ConversationDatabase

async def test_user_model_isolation():
    """Test that memories are isolated by user_id + model"""
    
    print("\n" + "="*60)
    print("Testing User + Model Memory Isolation")
    print("="*60)
    
    # Initialize systems
    memory_system = FridayMemorySystem()
    conversation_db = ConversationDatabase()
    
    # Test data
    user_alice = str(uuid.uuid4())[:8]  # "alice_" prefix
    user_bob = str(uuid.uuid4())[:8]    # "bob_" prefix
    model_friday = "friday"
    model_tara = "tara"
    
    # Create test memories
    test_memories = [
        {
            "user": user_alice,
            "model": model_friday,
            "content": f"Alice loves Friday's storytelling style",
            "memory_bank": "personal"
        },
        {
            "user": user_bob,
            "model": model_friday,
            "content": f"Bob prefers Friday to be more technical",
            "memory_bank": "personal"
        },
        {
            "user": user_alice,
            "model": model_tara,
            "content": f"Alice wants Tara to be mysterious",
            "memory_bank": "personal"
        },
        {
            "user": user_bob,
            "model": model_tara,
            "content": f"Bob wants Tara to be helpful and direct",
            "memory_bank": "personal"
        },
    ]
    
    print(f"\nTest Users:")
    print(f"  - user_alice: {user_alice}")
    print(f"  - user_bob: {user_bob}")
    print(f"\nTest Models: {model_friday}, {model_tara}")
    
    # Store memories
    memory_links = {}
    print(f"\n{'Step 1: Creating test memories':^60}")
    print("-" * 60)
    
    for mem_data in test_memories:
        user_id = mem_data["user"]
        model = mem_data["model"]
        conversation_id = f"{user_id}_{model}"
        
        # Create memory
        memory_id = await memory_system.create_memory(
            content=mem_data["content"],
            memory_type="user_preference",
            importance_level=8,
            tags=[user_id, model]
        )
        
        # Link to conversation
        link_id = await conversation_db.link_memory_to_conversation(
            memory_id=memory_id,
            conversation_id=conversation_id,
            link_type="direct",
            metadata={"user": user_id, "model": model}
        )
        
        memory_links[f"{user_id}_{model}"] = {
            "memory_id": memory_id,
            "link_id": link_id,
            "conversation_id": conversation_id
        }
        
        print(f"✓ Created memory for {user_id}_{model}")
        print(f"  - Memory ID: {memory_id}")
        print(f"  - Conversation ID: {conversation_id}")
        print()
    
    # Verify isolation
    print(f"{'Step 2: Verifying Memory Isolation':^60}")
    print("-" * 60)
    
    test_cases = [
        (user_alice, model_friday, f"{user_alice}_{model_friday}"),
        (user_bob, model_friday, f"{user_bob}_{model_friday}"),
        (user_alice, model_tara, f"{user_alice}_{model_tara}"),
        (user_bob, model_tara, f"{user_bob}_{model_tara}"),
    ]
    
    all_passed = True
    
    for user, model, conversation_id in test_cases:
        links = await conversation_db.get_memory_conversation_links(
            conversation_id=conversation_id
        )
        
        if len(links) == 1:
            link = links[0]
            expected_memory_id = memory_links[conversation_id]["memory_id"]
            
            if link["memory_id"] == expected_memory_id:
                print(f"✓ PASS: {conversation_id}")
                print(f"  - Found 1 memory link")
                print(f"  - Memory ID: {link['memory_id']}")
                print(f"  - Link type: {link['link_type']}")
            else:
                print(f"✗ FAIL: {conversation_id}")
                print(f"  - Memory ID mismatch")
                print(f"  - Expected: {expected_memory_id}")
                print(f"  - Got: {link['memory_id']}")
                all_passed = False
        else:
            print(f"✗ FAIL: {conversation_id}")
            print(f"  - Expected 1 link, found {len(links)}")
            all_passed = False
        print()
    
    # Summary
    print(f"{'Summary':^60}")
    print("-" * 60)
    
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("\nMemory isolation is working correctly:")
        print(f"  - Each user+model combination has separate memories")
        print(f"  - Memories don't leak between combinations")
        print(f"  - Conversation_id format is correct: user_id_model")
    else:
        print("✗ SOME TESTS FAILED")
        print("Please check the implementation")
    
    print("=" * 60 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(test_user_model_isolation())
    exit(0 if success else 1)
