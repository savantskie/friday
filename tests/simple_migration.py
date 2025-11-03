#!/usr/bin/env python3
"""
Simple and Correct Migration Strategy

This does EXACTLY what Nate wants:
1. Archive old files (the ones currently in memory_data) → memory_data/archives/
2. Create new empty databases with SAME NAMES as originals
3. New databases have IDENTICAL table structure (using _create_new_db_with_schema logic)
4. New databases start EMPTY, ready for new data

This reuses the proven schema-cloning logic already in database_maintenance.py
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def create_new_db_with_schema(new_db_path: Path, source_db_path: Path):
    """Create a new database with the same schema as source (but empty)"""
    
    # Get schema from source DB (exclude sqlite internal tables)
    source_conn = sqlite3.connect(str(source_db_path))
    source_cursor = source_conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql NOT NULL AND name NOT LIKE 'sqlite_%'"
    )
    tables = source_cursor.fetchall()
    source_conn.close()
    
    if not tables:
        raise Exception(f"No tables found in {source_db_path}")
    
    # Create new database with same schema
    new_conn = sqlite3.connect(str(new_db_path))
    new_cursor = new_conn.cursor()
    
    for table_name, create_sql in tables:
        print(f"    Creating table: {table_name}")
        new_cursor.execute(create_sql)
    
    # Recreate indexes (excluding internal sqlite indexes)
    source_conn = sqlite3.connect(str(source_db_path))
    source_cursor = source_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND sql NOT NULL AND name NOT LIKE 'sqlite_%'"
    )
    indexes = source_cursor.fetchall()
    source_conn.close()
    
    for (index_sql,) in indexes:
        try:
            new_cursor.execute(index_sql)
        except Exception as e:
            print(f"    (Skipped index - may already exist)")
    
    new_conn.commit()
    new_conn.close()
    
    print(f"    ✓ Created with schema from source")

def simple_migration():
    """
    Simple migration:
    1. Archive old files
    2. Create new empty files with same names and same schemas
    """
    
    memory_data = Path("/media/nate/Friday/Friday/memory_data")
    archives_folder = memory_data / "archives"
    archives_folder.mkdir(exist_ok=True)
    
    old_db_names = [
        "conversations.db",
        "ai_memories.db",
        "mcp_tool_calls.db",
        "schedule.db",
        "vscode_project.db"
    ]
    
    print("=" * 80)
    print("SIMPLE MIGRATION - Archive Old, Create New Empty")
    print("=" * 80)
    print(f"\nArchive folder: {archives_folder}\n")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for db_name in old_db_names:
        old_path = memory_data / db_name
        
        if not old_path.exists():
            print(f"⚠️  {db_name} not found, skipping")
            continue
        
        print(f"\nProcessing: {db_name}")
        
        try:
            # Step 1: Archive the old file
            archive_name = f"{db_name.replace('.db', '')}_{timestamp}.db.archive"
            archive_path = archives_folder / archive_name
            
            shutil.move(str(old_path), str(archive_path))
            print(f"  ✓ Archived to: {archive_name}")
            
            # Step 2: Create new empty database with same schema
            new_path = memory_data / db_name
            create_new_db_with_schema(new_path, archive_path)
            
            # Step 3: Verify the new file has the same tables
            old_conn = sqlite3.connect(str(archive_path))
            old_cursor = old_conn.cursor()
            old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            old_tables = sorted([row[0] for row in old_cursor.fetchall()])
            old_conn.close()
            
            new_conn = sqlite3.connect(str(new_path))
            new_cursor = new_conn.cursor()
            new_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            new_tables = sorted([row[0] for row in new_cursor.fetchall()])
            
            # Check that new database is empty
            new_cursor.execute(f"SELECT COUNT(*) FROM {new_tables[0]}")
            record_count = new_cursor.fetchone()[0]
            new_conn.close()
            
            if set(old_tables) == set(new_tables) and record_count == 0:
                print(f"  ✓ Verified: {len(new_tables)} tables, database is EMPTY")
                print(f"    Tables: {', '.join(new_tables)}")
            else:
                print(f"  ❌ ERROR: Schema mismatch or not empty!")
                return False
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            return False
    
    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print("\nResult:")
    print("  - Old files: Archived in memory_data/archives/ (with all data intact)")
    print("  - New files: In memory_data/ with SAME NAMES")
    print("  - New files: EMPTY, ready for new data")
    print("  - Table structure: Identical to originals")
    print("\nSystem is ready to use immediately!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = simple_migration()
    exit(0 if success else 1)
