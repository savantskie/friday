#!/usr/bin/env python3
"""
Test to verify user_id/model_id defaults are properly applied at handler level.
"""
import asyncio
import sys
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, '/media/nate/Friday/Friday')

from friday_memory_system import FridayMemorySystem

async def test_defaults():
    """Test that get_active_reminders works with default user_id/model_id"""
    
    logger.info("=" * 80)
    logger.info("TEST: get_active_reminders uses proper defaults")
    logger.info("=" * 80)
    
    try:
        memory_system = FridayMemorySystem()
        logger.info("✓ FridayMemorySystem initialized")
        
        # Create a reminder for Nate/Friday
        logger.info("[Step 1] Creating reminder for Nate/Friday...")
        due_time = (datetime.now() + timedelta(hours=2)).isoformat()
        result = await memory_system.create_reminder(
            content="Test reminder",
            due_datetime=due_time,
            user_id="Nate",
            model_id="Friday"
        )
        logger.info(f"✓ Created: {result}")
        
        # Call get_active_reminders WITHOUT explicit user_id/model_id (should use defaults)
        logger.info("[Step 2] Calling get_active_reminders() with NO parameters...")
        result = await memory_system.get_active_reminders()
        logger.info(f"✓ Result: {result}")
        
        count = len(result.get("reminders", []))
        logger.info(f"  Reminders found: {count}")
        
        if count > 0:
            logger.info("✓ SUCCESS: Defaults are working - found reminders without explicit user_id/model_id")
            return True
        else:
            logger.error("✗ FAILED: No reminders found even though we created one for Nate/Friday")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        return False

async def main():
    success = await test_defaults()
    logger.info("\n" + "=" * 80)
    logger.info(f"Test {'PASSED ✓' if success else 'FAILED ✗'}")
    logger.info("=" * 80 + "\n")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
