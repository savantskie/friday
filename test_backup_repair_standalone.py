#!/usr/bin/env python3
"""
Standalone Archive Repair Script for Backup

Directly repairs the backup archives without needing memory_system initialization
"""

import sqlite3
import asyncio
from pathlib import Path
from collections import defaultdict

async def insert_records_batch(db_path: str, records: list, table_name: str):
    """Insert records into a database table"""
    if not records:
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get column names from first record
    if isinstance(records[0], dict):
        columns = list(records[0].keys())
    else:
        columns = [d[0] for d in records[0].keys()]
    
    placeholders = ','.join(['?' for _ in columns])
    col_names = ','.join(columns)
    
    try:
        cursor = conn.cursor()
        for record in records:
            if isinstance(record, dict):
                values = tuple(record.get(col) for col in columns)
            else:
                values = tuple(record[col] for col in columns)
            
            cursor.execute(f"INSERT OR IGNORE INTO {table_name} ({col_names}) VALUES ({placeholders})", values)
        
        conn.commit()
    except Exception as e:
        print(f"Error inserting records: {e}")
    finally:
        conn.close()

async def repair_vscode_archives(backup_path: Path) -> dict:
    """Repair vscode_project archives"""
    print("\n🔧 Repairing vscode_project archives...")
    
    results = {
        "archives_repaired": 0,
        "records_migrated": 0,
        "links_fixed": 0,
        "details": []
    }
    
    vscode_archives = list(backup_path.glob("vscode_project_*.db"))
    print(f"  Found {len(vscode_archives)} vscode_project archives")
    
    # Process each archive
    for archive_idx, archive_path in enumerate(sorted(vscode_archives), 1):
        print(f"\n  [{archive_idx}/{len(vscode_archives)}] Processing {archive_path.name}...")
        
        conn = sqlite3.connect(str(archive_path))
        conn.row_factory = sqlite3.Row
        
        # Find orphaned conversations (missing sessions in same archive)
        cursor = conn.execute("""
            SELECT dc.* FROM development_conversations dc
            WHERE dc.session_id NOT IN (SELECT session_id FROM project_sessions)
        """)
        orphaned_convs = cursor.fetchall()
        
        if not orphaned_convs:
            print(f"     No orphaned conversations")
            conn.close()
            results["archives_repaired"] += 1
            continue
        
        print(f"     Found {len(orphaned_convs)} orphaned conversations")
        
        # Get missing session IDs
        missing_session_ids = set(c['session_id'] for c in orphaned_convs if c['session_id'])
        print(f"     Looking for {len(missing_session_ids)} missing sessions...")
        
        sessions_to_add = []
        sessions_found = 0
        
        # Search in other vscode archives
        for other_archive in vscode_archives:
            if other_archive == archive_path:
                continue
            
            try:
                other_conn = sqlite3.connect(str(other_archive))
                other_conn.row_factory = sqlite3.Row
                
                # Query in batches to avoid SQL length limits
                for session_id in list(missing_session_ids):
                    cursor = other_conn.execute(
                        "SELECT * FROM project_sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    session = cursor.fetchone()
                    if session:
                        sessions_to_add.append(dict(session))
                        sessions_found += 1
                        missing_session_ids.discard(session_id)
                
                other_conn.close()
                
                if not missing_session_ids:
                    break
            except Exception as e:
                print(f"     Error searching {other_archive.name}: {e}")
        
        # Insert missing sessions
        if sessions_to_add:
            print(f"     Adding {sessions_found} restored sessions...")
            await insert_records_batch(str(archive_path), sessions_to_add, "project_sessions")
            results["records_migrated"] += len(sessions_to_add)
            results["links_fixed"] += len(orphaned_convs)
            results["details"].append({
                "archive": archive_path.name,
                "orphaned_conversations": len(orphaned_convs),
                "sessions_restored": sessions_found
            })
        
        conn.close()
        results["archives_repaired"] += 1
    
    return results

async def main():
    print("="*70)
    print("🔧 BACKUP ARCHIVE REPAIR TEST")
    print("="*70)
    
    backup_path = Path("/media/nate/Friday/Friday/memory_data/backups/archives_backup_20251124_110120")
    
    if not backup_path.exists():
        print(f"❌ Backup not found at {backup_path}")
        return False
    
    # Pre-repair scan
    print("\n📊 PRE-REPAIR SCAN")
    print("-"*70)
    
    vscode_orphaned_before = 0
    vscode_archives = list(backup_path.glob("vscode_project_*.db"))
    
    for archive in vscode_archives:
        conn = sqlite3.connect(str(archive))
        cursor = conn.execute("""
            SELECT COUNT(*) FROM development_conversations dc
            WHERE dc.session_id NOT IN (SELECT session_id FROM project_sessions)
        """)
        orphaned = cursor.fetchone()[0]
        vscode_orphaned_before += orphaned
        if orphaned > 0:
            print(f"  {archive.name}: {orphaned} orphaned conversations")
        conn.close()
    
    print(f"\n  TOTAL vscode_project orphaned: {vscode_orphaned_before}")
    
    # Run repair
    print("\n🔄 RUNNING REPAIR...")
    print("-"*70)
    
    results = await repair_vscode_archives(backup_path)
    
    print(f"\n✅ Repair completed:")
    print(f"   Archives processed: {results['archives_repaired']}")
    print(f"   Sessions restored: {results['records_migrated']}")
    print(f"   Links fixed: {results['links_fixed']}")
    
    # Post-repair scan
    print("\n📊 POST-REPAIR SCAN")
    print("-"*70)
    
    vscode_orphaned_after = 0
    for archive in vscode_archives:
        conn = sqlite3.connect(str(archive))
        cursor = conn.execute("""
            SELECT COUNT(*) FROM development_conversations dc
            WHERE dc.session_id NOT IN (SELECT session_id FROM project_sessions)
        """)
        orphaned = cursor.fetchone()[0]
        vscode_orphaned_after += orphaned
        if orphaned > 0:
            print(f"  {archive.name}: {orphaned} orphaned conversations remaining")
        conn.close()
    
    print(f"\n  TOTAL vscode_project orphaned: {vscode_orphaned_after}")
    
    # Summary
    print("\n📈 REPAIR EFFECTIVENESS")
    print("-"*70)
    
    fixed = vscode_orphaned_before - vscode_orphaned_after
    pct = (fixed / vscode_orphaned_before * 100) if vscode_orphaned_before > 0 else 0
    
    print(f"  Orphaned records fixed: {fixed} ({pct:.1f}%)")
    print(f"  Remaining orphaned: {vscode_orphaned_after}")
    
    if vscode_orphaned_after == 0:
        print("\n✅ SUCCESS! All orphaned records repaired!")
        return True
    else:
        print(f"\n⚠️  INCOMPLETE - {vscode_orphaned_after} records still orphaned")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
