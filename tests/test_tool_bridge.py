#!/usr/bin/env python3
"""
Friday Tool Bridge Test

Test the conversation monitoring and automatic tool execution.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

# Get base path dynamically
def get_base_path():
    """Get the base Friday path, works on both Windows and Linux"""
    current_file = Path(__file__).resolve()
    # Go up from tests/ to Friday/ directory
    return current_file.parent.parent

# Create test conversation directory
base_path = get_base_path()
test_dir = base_path / "test_conversations"
test_dir.mkdir(exist_ok=True)

# Create a test conversation file
test_conversation = {
    "messages": [
        {
            "role": "user",
            "content": "Hey Friday, do you remember our conversation about the new graphics card?",
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "user", 
            "content": "Please remember this: I'm getting an AMD Radeon RX 6800 XT on August 10th, 2025",
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "user",
            "content": "Can you check your system health and database stats?",
            "timestamp": datetime.now().isoformat()
        }
    ]
}

# Write test file
test_file = test_dir / "test_chat.json"
test_file.write_text(json.dumps(test_conversation, indent=2))

print(f"✅ Created test conversation file: {test_file}")
print("🔧 Start the tool bridge with: python friday_conversation_tool_bridge.py")
print("📝 The bridge should automatically detect and process these messages")
print("💡 You can also test by creating new conversation files in:")
print(f"   {test_dir}")
