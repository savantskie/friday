#!/usr/bin/env python3
"""
Test script to verify timezone handling is working correctly.
"""

from friday_memory_system import get_current_timestamp, get_local_timezone, datetime_to_local_isoformat
from datetime import datetime, timezone
import asyncio

def test_timezone_functions():
    """Test that timezone functions are working correctly"""
    
    print("=== Testing Friday Memory System Timezone Functions ===")
    
    # Test local timezone
    local_tz = get_local_timezone()
    print(f"Local timezone: {local_tz}")
    
    # Test current timestamp
    current_time = get_current_timestamp()
    print(f"Current timestamp (local): {current_time}")
    
    # Test UTC vs Local comparison
    utc_time = datetime.now(timezone.utc).isoformat()
    local_time = get_current_timestamp()
    
    print(f"UTC time:   {utc_time}")
    print(f"Local time: {local_time}")
    
    # Test datetime conversion
    test_dt = datetime.now()
    converted = datetime_to_local_isoformat(test_dt)
    print(f"Converted datetime to local: {converted}")
    
    print("\n=== Timezone Test Complete ===")

async def test_memory_system():
    """Test that memory system is using local timestamps"""
    
    print("\n=== Testing Memory System Timestamp Storage ===")
    
    try:
        from friday_memory_system import FridayMemorySystem
        
        # Initialize memory system
        memory = FridayMemorySystem(enable_file_monitoring=False)  # Disable monitoring for test
        
        # Store a test conversation
        result = await memory.store_conversation(
            content="Testing local timezone storage",
            role="user"
        )
        
        print(f"Stored message ID: {result['message_id']}")
        
        # Get recent context to see timestamp
        context = await memory.get_recent_context(limit=1)
        
        if context['messages']:
            timestamp = context['messages'][0]['timestamp']
            print(f"Stored timestamp: {timestamp}")
            
            # Parse the timestamp to verify it's in local timezone
            dt = datetime.fromisoformat(timestamp)
            print(f"Timezone info: {dt.tzinfo}")
            print(f"Is aware: {dt.tzinfo is not None}")
            
        print("✅ Memory system timestamp test complete")
        
    except Exception as e:
        print(f"❌ Error testing memory system: {e}")

if __name__ == "__main__":
    test_timezone_functions()
    asyncio.run(test_memory_system())
