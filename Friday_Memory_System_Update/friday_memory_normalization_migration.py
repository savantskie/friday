"""
Friday Memory Normalization Migration
- Scans all existing memories and normalizes model/user/bank names to lowercase
- Runs once on first startup after deployment
- Logs all changes (before/after) for audit trail and recovery
"""

import json
import logging
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from open_webui.models.memories import Memories  # type: ignore - Direct DB access

logger = logging.getLogger(__name__)


class MemoryNormalizationMigration:
    """Handles one-time normalization of existing memories to lowercase naming."""

    def __init__(self, migration_marker_path: str = "/media/nate/Friday/Friday/memory_data/.migration_completed"):
        """
        Initialize migration.
        
        Args:
            migration_marker_path: Path to file that tracks if migration has been completed
        """
        self.migration_marker_path = migration_marker_path
        self.log_path = "/media/nate/Friday/Friday/Logs/friday_migration_normalization.log"
        self._setup_logging()

    def _setup_logging(self):
        """Setup dedicated migration logger."""
        # Create a dedicated logger for migration
        self.migration_logger = logging.getLogger("migration")
        self.migration_logger.setLevel(logging.DEBUG)
        
        # Only add handler if not already present (prevents duplicate log entries on retry)
        if not self.migration_logger.handlers:
            handler = logging.FileHandler(self.log_path)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.migration_logger.addHandler(handler)

    def has_completed(self) -> bool:
        """Check if migration has already been completed."""
        return Path(self.migration_marker_path).exists()

    def mark_completed(self):
        """Mark migration as completed by creating marker file."""
        Path(self.migration_marker_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.migration_marker_path, "w") as f:
            f.write(json.dumps({"completed_at": datetime.now(timezone.utc).isoformat()}, indent=2))
        self.migration_logger.info(f"✓ Migration completed marker written to {self.migration_marker_path}")

    async def run_migration(self, query_memory_func, update_memory_func=None) -> Dict[str, Any]:
        """
        Run the migration pass on all existing memories.
        
        Args:
            query_memory_func: Async function to query all memories (from OpenWebUI memory API)
            update_memory_func: Async function to update a memory with normalized content
                               Signature: async def (memory_id: str, content: str, user_id: str) -> bool
                               (ISSUE 2 FIX)
        
        Returns:
            Migration report with counts
        """
        if self.has_completed():
            self.migration_logger.info("Migration already completed, skipping.")
            return {"status": "skipped", "reason": "Already completed"}

        self.migration_logger.info("=" * 80)
        self.migration_logger.info("Starting memory normalization migration")
        self.migration_logger.info("=" * 80)

        stats = {"migrated": 0, "failed": 0, "unchanged": 0, "timestamp": datetime.now(timezone.utc).isoformat()}
        changes_log = []

        try:
            # Query all memories directly from database (Issue 1 fix: query_memory_func expects QueryMemoryForm)
            self.migration_logger.info("Querying all memories from ai_memories database...")
            all_memories = Memories.get_memories()  # Direct DB call, synchronous

            if not all_memories:
                self.migration_logger.warning("No memories found to migrate.")
                stats["migrated"] = 0
                self.mark_completed()
                return stats

            self.migration_logger.info(f"Found {len(all_memories)} memories to scan")

            for idx, memory in enumerate(all_memories):
                if (idx + 1) % 100 == 0:
                    self.migration_logger.info(f"Progress: {idx + 1}/{len(all_memories)} memories scanned")

                # Access attributes via getattr() - Memories.get_memories() returns MemoryModel objects, not dicts
                memory_id = str(getattr(memory, "id", "unknown"))
                memory_user_id = getattr(memory, "user_id", "unknown")  # Extract user_id from memory
                content = getattr(memory, "content", "")
                needs_update = False
                original_content = content

                # Normalize [Model: X] to lowercase
                model_pattern = r"\[Model:\s*([^\]]+)\]"
                model_match = re.search(model_pattern, content)
                if model_match:
                    old_value = model_match.group(1).strip()
                    new_value = old_value.lower()
                    if old_value != new_value:
                        content = re.sub(
                            r"\[Model:\s*" + re.escape(old_value) + r"\]",
                            f"[Model: {new_value}]",
                            content
                        )
                        needs_update = True
                        self.migration_logger.debug(
                            f"Memory {memory_id}: Model normalized {old_value} → {new_value}"
                        )

                # Normalize [User: X] to lowercase
                user_pattern = r"\[User:\s*([^\]]+)\]"
                user_match = re.search(user_pattern, content)
                if user_match:
                    old_value = user_match.group(1).strip()
                    new_value = old_value.lower()
                    if old_value != new_value:
                        content = re.sub(
                            r"\[User:\s*" + re.escape(old_value) + r"\]",
                            f"[User: {new_value}]",
                            content
                        )
                        needs_update = True
                        self.migration_logger.debug(
                            f"Memory {memory_id}: User normalized {old_value} → {new_value}"
                        )

                # Normalize [Memory Bank: X] to lowercase
                bank_pattern = r"\[Memory Bank:\s*([^\]]+)\]"
                bank_match = re.search(bank_pattern, content)
                if bank_match:
                    old_value = bank_match.group(1).strip()
                    new_value = old_value.lower()
                    if old_value != new_value:
                        content = re.sub(
                            r"\[Memory Bank:\s*" + re.escape(old_value) + r"\]",
                            f"[Memory Bank: {new_value}]",
                            content
                        )
                        needs_update = True
                        self.migration_logger.debug(
                            f"Memory {memory_id}: Bank normalized {old_value} → {new_value}"
                        )

                if needs_update:
                    # ISSUE 2 FIX: Actually persist the normalized content back to database
                    if update_memory_func:
                        try:
                            await update_memory_func(memory_id=memory_id, content=content, user_id=memory_user_id)
                            self.migration_logger.info(
                                f"✓ Updated memory {memory_id} (normalized content persisted to database)"
                            )
                        except Exception as e:
                            self.migration_logger.error(
                                f"✗ Failed to persist normalized content for memory {memory_id}: {e}"
                            )
                            stats["failed"] += 1
                            continue
                    else:
                        self.migration_logger.warning(
                            f"✓ Identified update needed for memory {memory_id} but no update_memory_func provided (dry-run mode)"
                        )
                    
                    changes_log.append({
                        "memory_id": memory_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "original_content_snippet": original_content[:100],
                        "new_content_snippet": content[:100]
                    })
                    stats["migrated"] += 1
                else:
                    stats["unchanged"] += 1

        except Exception as e:
            self.migration_logger.error(f"Error during migration: {e}\n{traceback.format_exc()}")
            stats["failed"] += 1
            return stats

        # Write summary
        self.migration_logger.info("=" * 80)
        self.migration_logger.info("Migration Summary:")
        self.migration_logger.info(f"  Migrated: {stats['migrated']}")
        self.migration_logger.info(f"  Unchanged: {stats['unchanged']}")
        self.migration_logger.info(f"  Failed: {stats['failed']}")
        self.migration_logger.info(f"  Total: {stats['migrated'] + stats['unchanged'] + stats['failed']}")
        self.migration_logger.info(f"  Timestamp: {stats['timestamp']}")
        self.migration_logger.info("=" * 80)

        # Write change details to separate section
        if changes_log:
            self.migration_logger.info("\nDetailed Changes Log:")
            for change in changes_log:
                self.migration_logger.info(f"  {json.dumps(change)}")

        # Mark migration as complete
        self.mark_completed()
        return stats
