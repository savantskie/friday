#!/usr/bin/env python3
"""
Run retroactive database migration to split large databases into sharded structure.

This script will:
1. Split existing conversations into monthly files (conversations_YYYY-MM.db)
2. Split other databases by date/size
3. Archive the original files
4. Preserve all data with integrity verification

Usage:
    python3 run_migration.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the memory system
from friday_memory_system import FridayMemorySystem

async def main():
    """Run the migration"""
    
    print("\n" + "="*70)
    print("🚀 FRIDAY MEMORY SYSTEM - RETROACTIVE DATABASE MIGRATION")
    print("="*70)
    print("\nThis will split your existing databases into monthly/dated files.")
    print("Original files will be archived (never deleted).")
    print("\nDatabases to migrate:")
    print("  - conversations.db (359 MB) → conversations_YYYY-MM.db files")
    print("  - ai_memories.db (2.4 MB) → ai_memories_YYYYMM.db files")
    print("  - mcp_tool_calls.db (1.3 GB) → mcp_tool_calls_YYYYMM.db files")
    print("  - schedule.db (2.3 MB) → schedule_YYYYMM.db files")
    print("  - vscode_project.db (630 MB) → vscode_project_YYYYMM.db files")
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("❌ Migration cancelled by user")
        return False
    
    print("\n" + "="*70)
    print("Starting migration...")
    print("="*70 + "\n")
    
    try:
        # Initialize memory system
        memory_data_path = Path(__file__).parent / "memory_data"
        logger.info(f"Initializing FridayMemorySystem from {memory_data_path}")
        memory_system = FridayMemorySystem(data_dir=str(memory_data_path))
        
        # Get the maintenance manager
        db_maintenance = memory_system.db_maintenance
        
        # Run the migration
        logger.info("🔄 Starting retroactive migration...")
        results = await db_maintenance.migrate_all_large_databases()
        
        # Display results
        print("\n" + "="*70)
        print("📊 MIGRATION RESULTS")
        print("="*70)
        
        for db_type, result in results.items():
            print(f"\n{db_type.upper()}:")
            print(f"  Status: {result.get('status', 'unknown')}")
            print(f"  Records migrated: {result.get('records_migrated', 0)}")
            print(f"  Source count: {result['verification']['source_count']}")
            print(f"  Migrated count: {result['verification']['migrated_count']}")
            print(f"  Verification: {'✅ PASS' if result['verification']['match'] else '❌ FAIL'}")
            
            if result.get('target_dbs_created'):
                print(f"  New files created:")
                for db_path in result['target_dbs_created']:
                    db_name = Path(db_path).name
                    db_size = Path(db_path).stat().st_size / (1024 * 1024) if Path(db_path).exists() else 0
                    print(f"    - {db_name} ({db_size:.1f} MB)")
            
            if result.get('errors'):
                print(f"  ⚠️  Errors during migration:")
                for error in result['errors']:
                    print(f"    - {error}")
            
            if result.get('archived'):
                print(f"  ✅ Original archived and preserved")
        
        print("\n" + "="*70)
        print("✅ MIGRATION COMPLETE!")
        print("="*70)
        print("\nYour data is now organized by month/date.")
        print("Archives are preserved in memory_data/archives/")
        print("\nNext month's new conversations will automatically go to")
        print("conversations_2025-12.db when December arrives.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
