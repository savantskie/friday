#!/bin/bash
# Archive Backup and Repair Testing Script
# Creates backup copy of archives before running repair logic

set -e

ARCHIVE_SOURCE="/media/nate/Friday/Friday/memory_data/archives"
BACKUP_ROOT="/media/nate/Friday/Friday/memory_data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/archives_backup_$TIMESTAMP"

echo "🔄 Archive Backup and Repair Testing"
echo "===================================="
echo ""

# Check if archives exist
if [ ! -d "$ARCHIVE_SOURCE" ]; then
    echo "❌ ERROR: Archive folder not found at $ARCHIVE_SOURCE"
    exit 1
fi

# Create backup root if needed
mkdir -p "$BACKUP_ROOT"

# Count existing archives
ARCHIVE_COUNT=$(find "$ARCHIVE_SOURCE" -name "*.db" | wc -l)
echo "📊 Found $ARCHIVE_COUNT archive files"

# Create backup
echo ""
echo "📦 Creating backup..."
echo "  Source: $ARCHIVE_SOURCE"
echo "  Destination: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"
cp -r "$ARCHIVE_SOURCE"/* "$BACKUP_DIR/"

# Verify backup
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.db" | wc -l)
if [ "$BACKUP_COUNT" -eq "$ARCHIVE_COUNT" ]; then
    echo "✅ Backup complete! ($BACKUP_COUNT files)"
    echo "   Path: $BACKUP_DIR"
    echo ""
    echo "📋 Backup details:"
    du -sh "$BACKUP_DIR"
    echo ""
    echo "Next steps:"
    echo "1. Run repair logic on this backup"
    echo "2. Verify results don't cause issues"
    echo "3. If successful, backup becomes production-safe template"
    echo "4. Original archives remain untouched for now"
else
    echo "❌ ERROR: Backup verification failed"
    echo "   Expected $ARCHIVE_COUNT files, found $BACKUP_COUNT"
    exit 1
fi
