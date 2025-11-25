#!/usr/bin/env python3
"""
Test MCP handler parameter extraction and passing.
"""
import asyncio
import sys
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/media/nate/Friday/Friday')

from friday_memory_mcp_server import FridayMemoryMCPServer

async def test_mcp_handler_defaults():
    """Test that MCP handler correctly applies defaults"""
    
    logger.info("=" * 80)
    logger.info("TEST: MCP handler parameter extraction and defaults")
    logger.info("=" * 80)
    
    try:
        # Initialize MCP server
        logger.info("[Step 1] Initializing MCP server...")
        mcp_server = FridayMemoryMCPServer()
        logger.info("✓ MCP server initialized")
        
        # Create a reminder via memory system first
        logger.info("[Step 2] Creating test reminder...")
        due_time = (datetime.now() + timedelta(hours=2)).isoformat()
        reminder_result = await mcp_server.memory_system.create_reminder(
            content="MCP test reminder",
            due_datetime=due_time,
            user_id="Nate",
            model_id="Friday"
        )
        logger.info(f"✓ Created reminder: {reminder_result['reminder_id']}")
        
        # Simulate MCP handler call with NO user_id/model_id in arguments
        # This is what happens when OpenWebUI calls the tool
        logger.info("[Step 3] Calling _execute_tool with NO user_id/model_id in arguments...")
        arguments = {"limit": 5}  # No user_id or model_id
        
        result = await mcp_server._execute_tool("get_active_reminders", arguments)
        logger.info(f"✓ Result: {result}")
        
        # Check if we got the reminder
        if "content" in str(result) and "reminders" in str(result):
            logger.info("✓ SUCCESS: MCP handler correctly applied defaults and found reminders")
            return True
        else:
            logger.error(f"✗ FAILED: Did not get expected result structure: {result}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        return False

async def main():
    success = await test_mcp_handler_defaults()
    logger.info("\n" + "=" * 80)
    logger.info(f"Test {'PASSED ✓' if success else 'FAILED ✗'}")
    logger.info("=" * 80 + "\n")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
