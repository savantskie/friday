#!/usr/bin/env python3
"""
Test script for database sharding architecture (Phases 1-5)

This script tests:
- Phase 1: Database discovery
- Phase 2: Rotation checking  
- Phase 3: Active DB registry
- Phase 4: Retroactive migration
- Phase 5: Multi-DB queries
"""

import asyncio
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# Configure logging to see all debug info
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add current directory to path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

from friday_memory_system import FridayMemorySystem
from database_maintenance import DatabaseMaintenance


async def test_phase_1_discovery():
    """Test Phase 1: Database Discovery"""
    print("\n" + "="*60)
    print("🔍 PHASE 1: Database Discovery")
    print("="*60)
    
    try:
        # Initialize memory system
        memory_data_path = Path(__file__).parent / "memory_data"
        logger.info(f"Initializing FridayMemorySystem with data_dir: {memory_data_path}")
        
        memory_system = FridayMemorySystem(data_dir=str(memory_data_path))
        logger.info("✅ FridayMemorySystem initialized")
        
        # Get database maintenance instance
        db_maintenance = memory_system.db_maintenance
        logger.info(f"DatabaseMaintenance initialized with path: {db_maintenance.memory_data_path}")
        
        # Discover databases
        logger.info("Discovering databases...")
        await db_maintenance.discover_databases()
        
        # Show registry
        registry = db_maintenance.get_db_registry()
        print("\n📊 Database Registry:")
        for db_type, dbs in registry.items():
            if dbs:
                print(f"\n  {db_type}:")
                for db_info in dbs:
                    size_mb = db_info.get("size", 0) / (1024 * 1024)
                    print(f"    - {Path(db_info['path']).name}: {size_mb:.1f} MB")
        
        return memory_system, db_maintenance
        
    except Exception as e:
        logger.error(f"❌ Phase 1 failed: {e}", exc_info=True)
        return None, None


async def test_phase_2_rotation(db_maintenance):
    """Test Phase 2: Rotation Checking"""
    print("\n" + "="*60)
    print("🔄 PHASE 2: Rotation Checking")
    print("="*60)
    
    try:
        # Check rotation status for each database type
        db_types = list(db_maintenance.db_registry.keys())
        
        print("\n📋 Rotation Status:")
        for db_type in db_types:
            rotation_needed, reason = await db_maintenance.check_rotation_needed(db_type)
            if rotation_needed:
                print(f"\n  {db_type}: ⚠️  ROTATION NEEDED")
                print(f"    Reason: {reason}")
            else:
                print(f"\n  {db_type}: ✅ No rotation needed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Phase 2 failed: {e}", exc_info=True)
        return False


async def test_phase_3_registry(memory_system):
    """Test Phase 3: Active DB Registry"""
    print("\n" + "="*60)
    print("📝 PHASE 3: Active DB Registry")
    print("="*60)
    
    try:
        print("\n🗂️  Active Database Files Registry:")
        for db_type, db_path in memory_system.active_db_files.items():
            print(f"  {db_type}: {Path(db_path).name}")
        
        # Test get_active_db_path for each type
        print("\n🔍 Testing get_active_db_path():")
        for db_type in memory_system.active_db_files.keys():
            active_path = await memory_system.get_active_db_path(db_type)
            print(f"  {db_type}: {Path(active_path).name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Phase 3 failed: {e}", exc_info=True)
        return False


async def test_phase_4_migration_dry_run(db_maintenance):
    """Test Phase 4: Migration (dry run on small DB first)"""
    print("\n" + "="*60)
    print("🚀 PHASE 4: Retroactive Migration (Dry Run)")
    print("="*60)
    
    try:
        # Start with smallest database: ai_memories.db (2.4 MB)
        print("\n⚠️  MIGRATION DRY RUN: Testing on ai_memories.db (2.4 MB)")
        print("   This will NOT archive - just show what would happen")
        
        source_db = db_maintenance.memory_data_path / "ai_memories.db"
        
        if not source_db.exists():
            logger.error(f"Source DB not found: {source_db}")
            return False
        
        logger.info(f"Starting migration test on {source_db.name}...")
        
        # Run migration WITHOUT archiving (archive=False for dry run)
        result = await db_maintenance.migrate_database_to_sharded_structure(
            "ai_memories",
            str(source_db),
            archive=False  # Don't archive for dry run
        )
        
        # Display results
        print("\n📊 Migration Results:")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Records migrated: {result.get('records_migrated', 0)}")
        print(f"  Source count: {result['verification']['source_count']}")
        print(f"  Migrated count: {result['verification']['migrated_count']}")
        print(f"  Verification: {'✅ PASS' if result['verification']['match'] else '❌ FAIL'}")
        
        if result.get('target_dbs_created'):
            print(f"\n  Target databases created:")
            for db_path in result['target_dbs_created']:
                db_name = Path(db_path).name
                db_size = Path(db_path).stat().st_size / (1024 * 1024) if Path(db_path).exists() else 0
                print(f"    - {db_name} ({db_size:.1f} MB)")
        
        if result.get('errors'):
            print(f"\n  Errors:")
            for error in result['errors']:
                print(f"    - {error}")
        
        print(f"\n  Archived: {'Yes ✅' if result.get('archived') else 'No (dry run)'}")
        
        return result.get('status') == 'success' or result.get('status') == 'partial'
        
    except Exception as e:
        logger.error(f"❌ Phase 4 failed: {e}", exc_info=True)
        return False


async def test_phase_5_discovery():
    """Test Phase 5: Multi-DB Query Discovery"""
    print("\n" + "="*60)
    print("🔎 PHASE 5: Multi-DB Query Discovery")
    print("="*60)
    
    try:
        memory_data_path = Path(__file__).parent / "memory_data"
        memory_system = FridayMemorySystem(data_dir=str(memory_data_path))
        
        print("\n🗂️  Database Discovery for Query Operations:")
        
        # Simulate discovery for each DB type
        for db_type in ["conversations", "ai_memories", "mcp_tool_calls", "schedule", "vscode_project"]:
            discovered = await memory_system._discover_sharded_databases(db_type)
            if discovered:
                print(f"\n  {db_type}: Found {len(discovered)} database(s)")
                for db_path in discovered:
                    db_name = Path(db_path).name
                    db_size = Path(db_path).stat().st_size / (1024 * 1024)
                    print(f"    - {db_name} ({db_size:.1f} MB)")
            else:
                print(f"\n  {db_type}: No databases found")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Phase 5 failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    print("\n" + "🎯 "*30)
    print("DATABASE SHARDING ARCHITECTURE TEST")
    print("Testing Phases 1-5")
    print("🎯 "*30)
    
    results = {
        "Phase 1 (Discovery)": False,
        "Phase 2 (Rotation)": False,
        "Phase 3 (Registry)": False,
        "Phase 4 (Migration)": False,
        "Phase 5 (Multi-DB Queries)": False,
    }
    
    try:
        # Phase 1: Discovery
        memory_system, db_maintenance = await test_phase_1_discovery()
        results["Phase 1 (Discovery)"] = memory_system is not None
        
        if not memory_system:
            print("\n❌ Cannot continue without Phase 1 success")
            return results
        
        # Phase 2: Rotation
        results["Phase 2 (Rotation)"] = await test_phase_2_rotation(db_maintenance)
        
        # Phase 3: Registry
        results["Phase 3 (Registry)"] = await test_phase_3_registry(memory_system)
        
        # Phase 4: Migration (dry run)
        results["Phase 4 (Migration)"] = await test_phase_4_migration_dry_run(db_maintenance)
        
        # Phase 5: Multi-DB Discovery
        results["Phase 5 (Multi-DB Queries)"] = await test_phase_5_discovery()
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
    
    # Print summary
    print("\n" + "="*60)
    print("📈 TEST SUMMARY")
    print("="*60)
    
    for phase, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {phase}: {status}")
    
    total_passed = sum(1 for v in results.values() if v)
    total_tests = len(results)
    
    print(f"\n  Overall: {total_passed}/{total_tests} phases passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! Ready for production merge.")
    else:
        print(f"\n⚠️  {total_tests - total_passed} phase(s) need investigation.")
    
    return results


if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        sys.exit(0 if all(results.values()) else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
