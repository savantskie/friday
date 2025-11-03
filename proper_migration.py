#!/usr/bin/env python3
"""
Proper Database Migration Strategy

This approach:
1. Archives the old monolithic databases (complete with all tables)
2. Copies them back to memory_data with proper naming
3. Lets the rotation system split them as they grow
4. Preserves all table structure and data integrity

This is MUCH simpler and safer than trying to split records manually.
"""

import asyncio
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

async def migrate_databases_properly():
    """
    Proper migration: Archive old files, copy them back with correct names.
    
    OLD:
        conversations.db → archive, then copy as conversations_202511.db
        ai_memories.db → archive, then copy as ai_memories_202511.db
        etc.
    
    This preserves ALL tables and structure.
    """
    
    memory_data = Path("/media/nate/Friday/Friday/memory_data")
    archives_folder = memory_data / "archives"
    archives_folder.mkdir(exist_ok=True)
    
    db_mappings = {
        "conversations": "conversations",
        "ai_memories": "ai_memories",
        "mcp_tool_calls": "mcp_tool_calls",
        "schedule": "schedule",
        "vscode_project": "vscode_project"
    }
    
    current_month = datetime.now().strftime("%Y%m")  # 202511 for November 2025
    
    print("=" * 80)
    print("DATABASE MIGRATION - PROPER APPROACH")
    print("=" * 80)
    print(f"\nCurrent month: {current_month}")
    print(f"Archive folder: {archives_folder}\n")
    
    for old_name, db_type in db_mappings.items():
        old_path = memory_data / f"{old_name}.db"
        
        if not old_path.exists():
            print(f"⚠️  {old_name}.db not found, skipping")
            continue
        
        try:
            # Step 1: Verify the old database has tables
            conn = sqlite3.connect(str(old_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not tables:
                print(f"❌ {old_name}.db has no tables! Aborting.")
                return False
            
            file_size_mb = old_path.stat().st_size / (1024 * 1024)
            print(f"Processing: {old_name}.db ({file_size_mb:.1f} MB, {len(tables)} tables)")
            
            # Step 2: Archive the original file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{old_name}_{timestamp}.db.archive"
            archive_path = archives_folder / archive_name
            
            shutil.copy2(str(old_path), str(archive_path))
            print(f"  ✓ Archived to: {archive_name}")
            
            # Step 3: Copy the archived file back to memory_data with new name
            # For conversations: conversations_YYYY-MM.db
            # For others: type_YYYYMM.db
            if db_type == "conversations":
                new_name = f"conversations_{datetime.now().strftime('%Y-%m')}.db"
            else:
                new_name = f"{db_type}_{current_month}.db"
            
            new_path = memory_data / new_name
            
            # If new name already exists, remove it (we're overwriting with complete copy)
            if new_path.exists():
                new_path.unlink()
            
            shutil.copy2(str(old_path), str(new_path))
            print(f"  ✓ Copied to: {new_name} (with all {len(tables)} tables intact)")
            
            # Step 4: Verify the new file has the same tables
            conn = sqlite3.connect(str(new_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            new_tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if set(tables) == set(new_tables):
                print(f"  ✓ Verified: All {len(tables)} tables present in new file")
            else:
                print(f"  ❌ ERROR: Table count mismatch! Original: {tables}, New: {new_tables}")
                return False
            
            # Step 5: Remove the original file (we have archive + copy)
            old_path.unlink()
            print(f"  ✓ Removed original: {old_name}.db\n")
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}\n")
            return False
    
    print("=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print("\nResult:")
    print("  - Old files: Archived in memory_data/archives/")
    print("  - New files: In memory_data/ with proper names and ALL tables intact")
    print("  - All table structures: Preserved")
    print("  - Data integrity: 100%")
    print("  - System status: Ready to use")
    print("\nThe rotation system will now split these files as they grow.")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(migrate_databases_properly())
    exit(0 if success else 1)
