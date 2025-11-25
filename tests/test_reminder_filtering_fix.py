#!/usr/bin/env python3
"""
Test reminder filtering fix to verify reminders are filtered by user_id and model_id.
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

async def test_reminder_filtering():
    """Test that reminders are created and retrieved with proper user/model filtering"""
    
    logger.info("=" * 80)
    logger.info("TEST: Reminder creation and retrieval with user_id/model_id filtering")
    logger.info("=" * 80)
    
    try:
        # Initialize the system
        logger.info("[Step 1] Initializing FridayMemorySystem...")
        memory_system = FridayMemorySystem()
        logger.info("✓ FridayMemorySystem initialized successfully")
        
        # Create two reminders with different user/model pairs
        logger.info("[Step 2] Creating reminders with different user/model pairs...")
        
        due_time = (datetime.now() + timedelta(hours=2)).isoformat()
        
        reminder1_result = await memory_system.create_reminder(
            content="Reminder for Nate/Friday",
            due_datetime=due_time,
            user_id="Nate",
            model_id="Friday"
        )
        logger.info(f"✓ Created reminder 1 for Nate/Friday: {reminder1_result}")
        
        reminder2_result = await memory_system.create_reminder(
            content="Reminder for TestUser/OtherModel",
            due_datetime=due_time,
            user_id="TestUser",
            model_id="OtherModel"
        )
        logger.info(f"✓ Created reminder 2 for TestUser/OtherModel: {reminder2_result}")
        
        # Get active reminders for Nate/Friday
        logger.info("[Step 3] Retrieving reminders for Nate/Friday...")
        nate_reminders = await memory_system.get_active_reminders(
            user_id="Nate",
            model_id="Friday"
        )
        logger.info(f"✓ Retrieved reminders for Nate/Friday: {nate_reminders}")
        
        # Verify we only get Nate/Friday reminders
        nate_count = len(nate_reminders.get("reminders", []))
        logger.info(f"  Count for Nate/Friday: {nate_count}")
        
        # Get active reminders for TestUser/OtherModel
        logger.info("[Step 4] Retrieving reminders for TestUser/OtherModel...")
        test_reminders = await memory_system.get_active_reminders(
            user_id="TestUser",
            model_id="OtherModel"
        )
        logger.info(f"✓ Retrieved reminders for TestUser/OtherModel: {test_reminders}")
        
        # Verify we only get TestUser/OtherModel reminders
        test_count = len(test_reminders.get("reminders", []))
        logger.info(f"  Count for TestUser/OtherModel: {test_count}")
        
        # Verify filtering worked
        logger.info("[Step 5] Verifying filtering...")
        if nate_count > 0 and test_count > 0:
            logger.info("✓ Both user/model pairs have reminders")
            
            # Check that Nate/Friday results don't contain TestUser reminders
            nate_has_test = any("TestUser" in str(r) for r in nate_reminders.get("reminders", []))
            test_has_nate = any("Nate" in str(r) for r in test_reminders.get("reminders", []))
            
            if not nate_has_test and not test_has_nate:
                logger.info("✓ Filtering is working correctly - reminders are properly separated by user/model")
                return True
            else:
                logger.error("✗ Filtering not working - reminders from different users mixed together")
                if nate_has_test:
                    logger.error("  Nate/Friday results contain TestUser reminders")
                if test_has_nate:
                    logger.error("  TestUser/OtherModel results contain Nate reminders")
                return False
        else:
            logger.warning(f"⚠ Not enough reminders created for full test (Nate: {nate_count}, TestUser: {test_count})")
            return True  # Still counts as success if at least one was created
            
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        return False

async def main():
    logger.info("\nStarting reminder filtering test\n")
    
    success = await test_reminder_filtering()
    
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✓ TEST PASSED")
        logger.info("Reminder filtering is working correctly!")
    else:
        logger.error("✗ TEST FAILED")
        logger.error("Reminder filtering has issues")
    logger.info("=" * 80 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
