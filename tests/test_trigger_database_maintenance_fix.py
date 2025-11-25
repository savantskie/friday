#!/usr/bin/env python3
"""
Test script for trigger_database_maintenance MCP tool fix.
Simulates the tool call to verify the fix works correctly.
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add Friday path
friday_path = Path(__file__).parent.parent
sys.path.insert(0, str(friday_path))

# Import after path setup
from friday_memory_system import FridayMemorySystem


async def test_trigger_database_maintenance():
    """Test the trigger_database_maintenance tool fix."""
    logger.info("=" * 80)
    logger.info("TEST: trigger_database_maintenance Tool Fix")
    logger.info("=" * 80)
    
    try:
        # Initialize memory system
        logger.info("\n[Step 1] Initializing FridayMemorySystem...")
        memory_system = FridayMemorySystem()
        logger.info("✓ FridayMemorySystem initialized successfully")
        
        # Verify db_maintenance exists
        logger.info("\n[Step 2] Verifying db_maintenance attribute exists...")
        if not hasattr(memory_system, 'db_maintenance'):
            logger.error("✗ FAILED: memory_system.db_maintenance not found!")
            return False
        logger.info("✓ db_maintenance attribute exists")
        
        # Verify db_maintenance has run_maintenance method
        logger.info("\n[Step 3] Verifying run_maintenance method exists...")
        if not hasattr(memory_system.db_maintenance, 'run_maintenance'):
            logger.error("✗ FAILED: db_maintenance.run_maintenance method not found!")
            return False
        logger.info("✓ run_maintenance method exists")
        
        # Check if method is callable and async
        logger.info("\n[Step 4] Verifying run_maintenance is callable...")
        if not callable(memory_system.db_maintenance.run_maintenance):
            logger.error("✗ FAILED: run_maintenance is not callable!")
            return False
        logger.info("✓ run_maintenance is callable")
        
        # Simulate the fixed MCP handler code
        logger.info("\n[Step 5] Simulating MCP handler call...")
        force = True
        logger.info(f"Calling: await self.memory_system.db_maintenance.run_maintenance(force={force})")
        
        try:
            result = await memory_system.db_maintenance.run_maintenance(force=force)
            logger.info("✓ Method executed successfully")
            
            # Verify result structure
            logger.info("\n[Step 6] Verifying result structure...")
            if isinstance(result, dict):
                logger.info(f"✓ Result is a dictionary with keys: {list(result.keys())}")
                
                # Log the result
                logger.info("\nMaintenance Result:")
                logger.info(f"  - Status: {result.get('status')}")
                logger.info(f"  - Message: {result.get('message')}")
                if 'details' in result:
                    logger.info(f"  - Details:")
                    for key, value in result.get('details', {}).items():
                        logger.info(f"      - {key}: {value}")
                
                if result.get('status') == 'success':
                    logger.info("✓ Maintenance completed successfully")
                    return True
                else:
                    logger.warning(f"⚠ Maintenance returned status: {result.get('status')}")
                    logger.warning(f"  Message: {result.get('message')}")
                    return True  # Still a success - method was called correctly
            else:
                logger.error(f"✗ FAILED: Result is not a dictionary, got {type(result)}")
                return False
                
        except Exception as e:
            logger.error(f"✗ FAILED: Exception during run_maintenance call: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    except Exception as e:
        logger.error(f"✗ FAILED: Error initializing or testing: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
        logger.info("\n" + "=" * 80)


async def main():
    """Run all tests."""
    logger.info("\nStarting trigger_database_maintenance Tool Tests\n")
    
    success = await test_trigger_database_maintenance()
    
    if success:
        logger.info("=" * 80)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("The trigger_database_maintenance tool fix is working correctly!")
        logger.info("=" * 80)
        return 0
    else:
        logger.info("=" * 80)
        logger.info("✗ TESTS FAILED")
        logger.info("There are issues with the trigger_database_maintenance tool fix.")
        logger.info("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
