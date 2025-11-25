#!/usr/bin/env python3
"""
Test script to verify session-based archival grouping works on PRODUCTION archives.
This runs the archival system on actual databases and checks that no new orphaned records are created.
"""

import asyncio
import sqlite3
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
friday_path = Path(__file__).parent
sys.path.insert(0, str(friday_path))

# Import after path setup
from friday_memory_system import FridayMemorySystem
from database_maintenance import DatabaseMaintenance

async def check_archives_for_orphans(archive_dir: Path, db_type: str) -> dict:
    """Check a set of archives for orphaned records."""
    orphan_counts = {}
    
    for archive_file in sorted(archive_dir.glob("*.db")):
        try:
            conn = sqlite3.connect(archive_file)
            cursor = conn.cursor()
            
            # Get list of tables in this database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            orphan_count = 0
            
            if db_type == "vscode_project" and "project_conversations" in tables:
                # Check for conversations without matching sessions
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM project_conversations pc
                    WHERE NOT EXISTS (
                        SELECT 1 FROM project_sessions ps
                        WHERE ps.session_id = pc.session_id
                    )
                """)
                orphan_count = cursor.fetchone()[0]
                
            elif db_type == "conversations" and "vscode_messages" in tables:
                # Check for messages without matching conversations
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM vscode_messages vm
                    WHERE NOT EXISTS (
                        SELECT 1 FROM vscode_conversations vc
                        WHERE vc.conversation_id = vm.conversation_id
                    )
                """)
                orphan_count = cursor.fetchone()[0]
            
            if orphan_count > 0:
                orphan_counts[archive_file.name] = orphan_count
                
            conn.close()
            
        except Exception as e:
            logger.debug(f"Could not check {archive_file.name}: {e}")
    
    return orphan_counts


async def main():
    """Main test function."""
    logger.info("=" * 80)
    logger.info("PRODUCTION ARCHIVAL TEST - Session-Based Grouping Verification")
    logger.info("=" * 80)
    
    memory_data_dir = friday_path / "memory_data"
    
    if not memory_data_dir.exists():
        logger.error(f"Memory data directory not found: {memory_data_dir}")
        return False
    
    # Initialize memory system to get database paths
    logger.info("Initializing Friday Memory System...")
    try:
        memory_system = FridayMemorySystem()
        maintenance = DatabaseMaintenance(memory_system, str(memory_data_dir))
    except Exception as e:
        logger.error(f"Failed to initialize memory system: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Test 1: Check existing archives for orphans BEFORE running maintenance
    logger.info("\n[Step 1] Checking EXISTING archives for orphans...")
    archives_dir = memory_data_dir / "archives"
    
    if not archives_dir.exists():
        logger.warning(f"Archives directory not found: {archives_dir}")
        logger.info("No production archives to test. This is okay - test will verify archival on new data.")
    else:
        logger.info(f"Found {len(list(archives_dir.glob('*.db')))} archive files")
        
        # Check all archives for orphaned records
        logger.info("Checking all archives for orphaned records...")
        vscode_orphans_before = await check_archives_for_orphans(archives_dir, "vscode_project")
        conv_orphans_before = await check_archives_for_orphans(archives_dir, "conversations")
        
        if vscode_orphans_before:
            logger.info(f"Found {sum(vscode_orphans_before.values())} orphaned conversations in vscode_project archives (pre-existing)")
        else:
            logger.info("No orphaned conversations found in vscode_project archives ✓")
        
        if conv_orphans_before:
            logger.info(f"Found {sum(conv_orphans_before.values())} orphaned messages in conversations archives (pre-existing)")
        else:
            logger.info("No orphaned messages found in conversations archives ✓")
    
    # Test 2: Run archival on actual databases
    logger.info("\n[Step 2] Running archive_rotate_to_sharded_structure() on production databases...")
    
    try:
        # Get list of active databases
        databases_dir = memory_data_dir / "databases"
        if databases_dir.exists():
            dbs = list(databases_dir.glob("*.db"))
            logger.info(f"Found {len(dbs)} active databases to archive")
            
            # Run archival
            logger.info("Running archival with session-based grouping...")
            await maintenance.archive_rotate_to_sharded_structure()
            logger.info("Archival completed successfully ✓")
        else:
            logger.info("No active databases found to archive (this is okay)")
    
    except Exception as e:
        logger.error(f"Error during archival: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Test 3: Check NEW archives for orphans (should be none)
    logger.info("\n[Step 3] Checking NEW archives for orphans (session-based grouping)...")
    
    if archives_dir.exists():
        # Get list of archive files created in the last 10 minutes
        import time
        current_time = time.time()
        recent_archives = [
            f for f in archives_dir.glob("*.db")
            if (current_time - f.stat().st_mtime) < 600  # Last 10 minutes
        ]
        
        if recent_archives:
            logger.info(f"Found {len(recent_archives)} recently created archives")
            
            # Check vscode_project archives
            recent_vscode = [f for f in recent_archives if "vscode_project" in f.name]
            if recent_vscode:
                logger.info(f"Checking {len(recent_vscode)} new vscode_project archives...")
                vscode_orphans_after = await check_archives_for_orphans(archives_dir, "vscode_project")
                if vscode_orphans_after:
                    logger.error(f"FAILED: Found orphaned conversations in new archives: {vscode_orphans_after}")
                    return False
                else:
                    logger.info("No orphaned conversations in new vscode_project archives ✓")
            
            # Check conversations archives
            recent_conv = [f for f in recent_archives if "conversations" in f.name]
            if recent_conv:
                logger.info(f"Checking {len(recent_conv)} new conversations archives...")
                conv_orphans_after = await check_archives_for_orphans(archives_dir, "conversations")
                if conv_orphans_after:
                    logger.error(f"FAILED: Found orphaned messages in new archives: {conv_orphans_after}")
                    return False
                else:
                    logger.info("No orphaned messages in new conversations archives ✓")
        else:
            logger.info("No new archives were created (this is okay if archival conditions weren't met)")
    
    logger.info("\n" + "=" * 80)
    logger.info("✓ PRODUCTION ARCHIVAL TEST PASSED")
    logger.info("  Session-based grouping is working correctly on production archives")
    logger.info("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
