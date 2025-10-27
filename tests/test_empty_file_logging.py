#!/usr/bin/env python3
"""
Test script to verify empty file logging functionality
"""
import os
import tempfile
import asyncio
from friday_memory_system import ConversationFileMonitor, FridayMemorySystem

async def test_empty_file_logging():
    """Test that empty files are logged and tracked properly"""

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a FridayMemorySystem instance (minimal setup)
        memory_system = FridayMemorySystem(
            data_dir=temp_dir,
            enable_file_monitoring=False  # Disable monitoring for this test
        )

        # Override the conversations_db path to use temp directory
        memory_system.conversations_db.db_path = os.path.join(temp_dir, "conversations.db")

        # Create a ConversationFileMonitor
        monitor = ConversationFileMonitor(memory_system, [temp_dir])

        # Create a temp directory structure that matches conversation file patterns
        chatsessions_dir = os.path.join(temp_dir, "chatsessions")
        os.makedirs(chatsessions_dir, exist_ok=True)

        # Create an empty file that will be recognized as a VS Code chat session file
        empty_file = os.path.join(chatsessions_dir, "empty_test.json")
        with open(empty_file, 'w') as f:
            f.write("")  # Empty file

        print("Testing empty file detection...")

        # Test empty file processing
        print(f"Processing empty file: {empty_file}")
        
        # Check file content before processing
        with open(empty_file, 'rb') as f:
            content = f.read()
            print(f"File content length: {len(content)}")
        
        try:
            await monitor._process_file_change(empty_file)
            print("File processing completed without exception")
        except Exception as e:
            print(f"Exception during file processing: {e}")

        # Check debug log
        debug_log_path = os.path.join(temp_dir, "db_debug_log.txt")
        if os.path.exists(debug_log_path):
            with open(debug_log_path, 'r') as f:
                log_content = f.read()
                if "Empty file detected" in log_content and "empty_test.json" in log_content:
                    print("✅ Empty file detection and logging works!")
                else:
                    print("❌ Empty file logging failed")
                    print(f"Log content: {log_content}")
        else:
            print("❌ Debug log was not created")

        # Check if empty file is tracked
        if empty_file in monitor.empty_files:
            print("✅ Empty file tracking works!")
        else:
            print("❌ Empty file tracking failed")

        # Now add content to the empty file and test that it's processed
        print("Adding content to empty file and reprocessing...")
        # Use valid VS Code chat session format
        valid_chat_content = {
            "version": 1,
            "requesterUsername": "testuser",
            "responderUsername": "assistant",
            "requests": [
                {
                    "requestId": "test-request-1",
                    "timestamp": "2025-01-01T12:00:00.000Z",
                    "message": {
                        "text": "Hello"
                    },
                    "response": {
                        "value": "Hi there!"
                    }
                }
            ]
        }
        import json
        with open(empty_file, 'w') as f:
            json.dump(valid_chat_content, f)
        
        # Check file content before reprocessing
        with open(empty_file, 'r') as f:
            content = f.read()
            print(f"File content before reprocessing: {content[:100]}...")
        
        # Check file content in binary mode
        with open(empty_file, 'rb') as f:
            binary_content = f.read()
            print(f"File binary content length: {len(binary_content)}")
            print(f"File binary content preview: {binary_content[:100]}")

        # Reset processed files to allow reprocessing
        monitor.processed_files.clear()
        monitor.file_hashes.clear()

        print(f"Empty files set before reprocessing: {monitor.empty_files}")
        print(f"Is conversation file: {monitor._is_conversation_file(empty_file)}")
        await monitor._process_file_change(empty_file)
        print(f"Empty files set after reprocessing: {monitor.empty_files}")

        # Check if file was removed from empty_files set
        if empty_file not in monitor.empty_files:
            print("✅ Previously empty file processing works!")
        else:
            print("❌ Previously empty file processing failed")

        print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_empty_file_logging())