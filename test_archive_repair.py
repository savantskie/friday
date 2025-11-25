#!/usr/bin/env python3
"""
Test Archive Repair on Backup Copy

This script:
1. Tests the repair logic on the backup archives
2. Verifies results before applying to production
3. Reports detailed statistics
"""

import sys
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime

# Add Friday to path
sys.path.insert(0, '/media/nate/Friday/Friday')

from database_maintenance import DatabaseMaintenance
from friday_memory_system import FridayMemorySystem

async def test_repair():
    """Test repair logic on backup archives"""
    
    print("\n" + "="*70)
    print("🔧 ARCHIVE REPAIR TEST ON BACKUP")
    print("="*70)
    
    # Initialize memory system
    memory_system = FridayMemorySystem()
    
    # Create maintenance instance
    maintenance = DatabaseMaintenance(memory_system)
    
    # Scan for orphans BEFORE repair
    print("\n📊 PRE-REPAIR ORPHAN SCAN")
    print("-" * 70)
    
    backup_path = Path("/media/nate/Friday/Friday/memory_data/backups/archives_backup_20251124_110120")
    
    vscode_orphaned_before = 0
    conv_msg_orphaned_before = 0
    
    # Scan vscode_project archives
    vscode_archives = list(backup_path.glob("vscode_project_*.db"))
    for archive in vscode_archives:
        conn = sqlite3.connect(str(archive))
        cursor = conn.execute("""
            SELECT COUNT(*) FROM development_conversations dc
            WHERE dc.session_id NOT IN (SELECT session_id FROM project_sessions)
        """)
        orphaned = cursor.fetchone()[0]
        vscode_orphaned_before += orphaned
        conn.close()
    
    # Scan conversations archives (sample)
    conv_archives = list(backup_path.glob("conversations_*.db"))
    for archive in conv_archives[:50]:  # Sample first 50
        conn = sqlite3.connect(str(archive))
        cursor = conn.execute("""
            SELECT COUNT(*) FROM messages m
            WHERE m.conversation_id NOT IN (SELECT conversation_id FROM conversations)
        """)
        orphaned = cursor.fetchone()[0]
        conv_msg_orphaned_before += orphaned
        conn.close()
    
    print(f"vscode_project orphaned conversations: {vscode_orphaned_before}")
    print(f"conversations orphaned messages (sample 50): {conv_msg_orphaned_before}")
    
    # Run repair
    print("\n🔄 RUNNING REPAIR LOGIC...")
    print("-" * 70)
    
    try:
        # Temporarily point maintenance to backup archives
        original_archive_path = maintenance.memory_data_path / "archives"
        maintenance.memory_data_path = backup_path.parent  # Point to backups folder
        
        # Run repair
        results = await maintenance.repair_archive_links()
        
        # Restore original path
        maintenance.memory_data_path = original_archive_path.parent
        
        print("\n✅ REPAIR COMPLETED")
        print("-" * 70)
        print(f"vscode_project repairs:")
        print(f"   Archives repaired: {results['vscode_project']['archives_repaired']}")
        print(f"   Records migrated: {results['vscode_project']['records_migrated']}")
        print(f"   Links fixed: {results['vscode_project']['links_fixed']}")
        
        print(f"\nconversations repairs:")
        print(f"   Archives repaired: {results['conversations']['archives_repaired']}")
        print(f"   Records migrated: {results['conversations']['records_migrated']}")
        print(f"   Links fixed: {results['conversations']['links_fixed']}")
        
        # Scan for orphans AFTER repair
        print("\n📊 POST-REPAIR ORPHAN SCAN")
        print("-" * 70)
        
        vscode_orphaned_after = 0
        conv_msg_orphaned_after = 0
        
        for archive in vscode_archives:
            conn = sqlite3.connect(str(archive))
            cursor = conn.execute("""
                SELECT COUNT(*) FROM development_conversations dc
                WHERE dc.session_id NOT IN (SELECT session_id FROM project_sessions)
            """)
            orphaned = cursor.fetchone()[0]
            vscode_orphaned_after += orphaned
            conn.close()
        
        for archive in conv_archives[:50]:
            conn = sqlite3.connect(str(archive))
            cursor = conn.execute("""
                SELECT COUNT(*) FROM messages m
                WHERE m.conversation_id NOT IN (SELECT conversation_id FROM conversations)
            """)
            orphaned = cursor.fetchone()[0]
            conv_msg_orphaned_after += orphaned
            conn.close()
        
        print(f"vscode_project orphaned conversations: {vscode_orphaned_after}")
        print(f"conversations orphaned messages (sample 50): {conv_msg_orphaned_after}")
        
        # Summary
        print("\n📈 REPAIR EFFECTIVENESS")
        print("-" * 70)
        vscode_reduction = vscode_orphaned_before - vscode_orphaned_after
        conv_reduction = conv_msg_orphaned_before - conv_msg_orphaned_after
        
        print(f"vscode_project: {vscode_reduction} orphaned fixed ({vscode_reduction/max(vscode_orphaned_before,1)*100:.1f}% reduction)")
        print(f"conversations: {conv_reduction} orphaned fixed ({conv_reduction/max(conv_msg_orphaned_before,1)*100:.1f}% reduction)")
        
        if vscode_orphaned_after == 0 and conv_msg_orphaned_after == 0:
            print("\n✅ REPAIR TEST SUCCESSFUL!")
            print("   All orphaned records were successfully restored")
            print("   Safe to apply repair to production archives")
        else:
            print(f"\n⚠️  REPAIR TEST PARTIAL")
            print(f"   Still have {vscode_orphaned_after + conv_msg_orphaned_after} orphaned records")
            print(f"   May need manual investigation or multiple repair passes")
        
    except Exception as e:
        print(f"\n❌ ERROR during repair: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_repair())
    sys.exit(0 if success else 1)
