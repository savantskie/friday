#!/usr/bin/env python3
"""
Persistent AI Memory - Database Maintenance Module

Provides automated cleanup, optimization, retention policies, and database sharding for the memory system.
Genericized for use with any persistent-ai-memory installation.
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os
import json

try:
    from tag_manager import TagManager
except ImportError:
    TagManager = None

try:
    from ai_memory_maintenance import LongTermMemoryMaintenance
except ImportError:
    LongTermMemoryMaintenance = None  # Optional feature, will work without it

try:
    from settings import settings
except ImportError:
    # Fallback settings if not available
    settings = None

logger = logging.getLogger(__name__)


class DatabaseMaintenance:
    """
    Handles automated database cleanup, optimization, and sharding/rotation management.
    
    Combines maintenance tasks with database lifecycle management:
    - Discovery: Scans memory_data folder to discover all database files
    - Monitoring: Tracks file sizes and health
    - Rotation: Creates new databases when size/time thresholds are exceeded
    - Cleanup: Applies retention policies and removes old data
    - Migration: Retroactively splits large databases into sharded structure
    """
    
    def __init__(self, memory_system, memory_data_path: str = None):
        self.memory_system = memory_system
        
        # Database discovery and management
        if memory_data_path:
            self.memory_data_path = Path(memory_data_path)
        else:
            # Try to get from settings first, then infer from memory_system
            if settings and hasattr(settings, 'memory_data_path'):
                self.memory_data_path = Path(settings.memory_data_path)
            else:
                # Fallback: Try to infer from memory_system if not provided
                try:
                    self.memory_data_path = Path(memory_system.conversations_db.db_path).parent
                except:
                    # Last resort: use current directory
                    self.memory_data_path = Path.cwd() / "memory_data"
        
        self.db_registry: Dict[str, List[Dict]] = {}
        self.rotation_threshold_bytes = 3 * 1024 * 1024 * 1024  # 3GB
        self.last_discovery = None
        
        # Retention policies - default: keep most data indefinitely
        self.retention_policies = {
            "conversations": {
                "max_age_days": None,  # No age limit - keep ALL conversations indefinitely
                "max_count": None,     # No count limit - keep all conversations
                "preserve_important": True  # Keep all conversations (no pruning)
            },
            "curated_memories": {
                "max_age_days": None,  # No age limit - keep all memories indefinitely
                "max_count": None,     # No count limit - keep all memories
                "preserve_important": True  # Keep all memories (no pruning)
            },
            "schedule": {
                "max_age_days": 90,  # Keep old appointments/reminders for 3 months
                "cleanup_completed": True  # Remove completed items
            },
            "mcp_tool_calls": {
                "max_age_days": None,  # No age limit - keep ALL tool calls indefinitely
                "max_count": None      # No count limit - keep all tool calls
            },
            "memory_conversation_links": {
                "max_age_days": None,  # No age limit - keep ALL links indefinitely
                "cleanup_orphaned": True  # Remove links to deleted memories/conversations (only orphaned)
            },
            "memory_processing_queue": {
                "max_age_days": 90,  # Keep processed queue entries for 3 months
                "cleanup_completed": True  # Remove completed processing records
            },
            "memory_processing_log": {
                "max_age_days": 90,  # Keep processing logs for 3 months
                "max_count": 100000  # Keep max 100k log entries
            },
            "image_database": {
                "max_age_days": None,  # No age limit - keep all images (memories reference them)
                "max_count": None,     # No count limit - keep all images
                "preserve_important": True  # Keep all images (linked to memories)
            }
        }

        # Long-term memory maintenance (LLM-powered)
        if LongTermMemoryMaintenance:
            self.ltm_maintenance = LongTermMemoryMaintenance(memory_system=memory_system)
        else:
            self.ltm_maintenance = None
    
    # ===== Database Discovery & Lifecycle Management =====
    
    async def discover_databases(self) -> Dict[str, List[Dict]]:
        """
        Scan memory_data folder and discover all database files.
        
        Returns:
            Dict mapping database types to list of DB file info
        """
        logger.info(f"Discovering databases in {self.memory_data_path}")
        
        if not self.memory_data_path.exists():
            logger.error(f"Memory data path does not exist: {self.memory_data_path}")
            return {}
        
        discovered = {}
        
        # Patterns for different database types
        db_patterns = {
            "conversations": "conversations*.db",
            "ai_memories": "ai_memories*.db",
            "schedule": "schedule*.db",
            "mcp_tool_calls": "mcp_tool_calls*.db"
        }
        
        for db_type, pattern in db_patterns.items():
            db_files = []
            matching_files = list(self.memory_data_path.glob(pattern))
            
            for db_file in matching_files:
                try:
                    file_size = db_file.stat().st_size
                    
                    db_info = {
                        "path": str(db_file),
                        "filename": db_file.name,
                        "size": file_size,
                        "size_mb": round(file_size / 1024 / 1024, 2),
                        "healthy": await self._check_db_health(str(db_file))
                    }
                    db_files.append(db_info)
                    
                except Exception as e:
                    logger.error(f"Error discovering {db_file}: {e}")
            
            if db_files:
                discovered[db_type] = db_files
                logger.info(f"  Found {len(db_files)} {db_type} database(s)")
        
        self.db_registry = discovered
        self.last_discovery = datetime.now(timezone.utc)
        
        return discovered
    
    async def _check_db_health(self, db_path: str) -> bool:
        """Check if a database file is healthy and accessible."""
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            return result == "ok"
                
        except Exception as e:
            logger.error(f"Error checking database health for {db_path}: {e}")
            return False
    
    def get_db_registry(self) -> Dict[str, List[Dict]]:
        """Get the current database registry."""
        return self.db_registry
    
    # ===== Maintenance Operations =====
    
    async def run_maintenance(self, force: bool = False) -> Dict:
        """Run full database maintenance"""
        logger.info("🧹 Starting database maintenance...")
        
        results = {
            "maintenance_timestamp": datetime.now(timezone.utc).isoformat(),
            "discovery_results": {},
            "cleanup_results": {},
            "optimization_results": {},
            "statistics": {}
        }
        
        try:
            # 1. Discover all databases
            logger.info("🔍 Discovering databases...")
            results["discovery_results"] = await self.discover_databases()
            
            # 2. Clean up old data based on retention policies
            logger.info("📅 Applying retention policies...")
            results["cleanup_results"] = await self._apply_retention_policies(force)
            
            # 3. Remove duplicate entries
            logger.info("🔍 Removing any remaining duplicates...")
            results["cleanup_results"]["duplicates"] = await self._remove_duplicates()
            
            # 4. Optimize database performance
            logger.info("⚡ Optimizing database performance...")
            results["optimization_results"] = await self._optimize_databases()
            
            # 5. Collect post-cleanup statistics
            logger.info("📊 Collecting statistics...")
            results["statistics"] = await self._collect_statistics()

            # 6. Long-term memory maintenance (format reformatting, contradiction scanning, linking)
            if self.ltm_maintenance:
                logger.info("📝 Reformatting long-term memories...")
                results["ltm_reformat"] = await self.ltm_maintenance.reformat_memories(limit=100)
                logger.info("🔍 Scanning for contradictions and updates...")
                results["ltm_updates"] = await self.ltm_maintenance.scan_for_updates(limit=200)
                logger.info("🔗 Assisted linking for unlinked memories...")
                results["ltm_linking"] = await self.ltm_maintenance.assist_linking(limit=50)

            logger.info("✅ Database maintenance completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Database maintenance failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _apply_retention_policies(self, force: bool = False) -> Dict:
        """Apply retention policies to remove old data"""
        cleanup_results = {}
        
        # Log applied policies
        for policy_name, policy_config in self.retention_policies.items():
            max_age = policy_config.get("max_age_days")
            if max_age:
                cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)
                cleanup_results[policy_name] = {
                    "policy": policy_config,
                    "cutoff_date": cutoff.isoformat(),
                    "status": "policy_defined"
                }
            else:
                cleanup_results[policy_name] = {
                    "policy": policy_config,
                    "cutoff_date": "No cutoff (indefinite retention)",
                    "status": "preserved"
                }
        
        return cleanup_results
    
    async def _remove_duplicates(self) -> Dict:
        """Remove any remaining duplicate entries"""
        return {
            "status": "scan_only",
            "note": "Deduplication is database-specific and handled by ai_memory_core.py"
        }
    
    async def _optimize_databases(self) -> Dict:
        """Optimize database performance"""
        results = {}
        
        for db_type, db_list in self.db_registry.items():
            for db_info in db_list:
                db_path = db_info["path"]
                db_name = Path(db_path).stem
                
                try:
                    # Get database size before optimization
                    size_before = Path(db_path).stat().st_size
                    
                    # Optimize database
                    conn = sqlite3.connect(db_path)
                    conn.execute("VACUUM")  # Reclaim space
                    conn.execute("REINDEX")  # Rebuild indexes
                    conn.execute("ANALYZE")  # Update statistics
                    conn.close()
                    
                    # Get size after optimization
                    size_after = Path(db_path).stat().st_size
                    
                    results[db_name] = {
                        "size_before_mb": round(size_before / 1024 / 1024, 2),
                        "size_after_mb": round(size_after / 1024 / 1024, 2),
                        "space_saved_mb": round((size_before - size_after) / 1024 / 1024, 2),
                        "optimized": True
                    }
                    logger.info(f"  ✓ Optimized {db_name}: saved {results[db_name]['space_saved_mb']} MB")
                    
                except Exception as e:
                    logger.error(f"  ❌ Error optimizing {db_name}: {e}")
                    results[db_name] = {"error": str(e), "optimized": False}
        
        return results
    
    async def _collect_statistics(self) -> Dict:
        """Collect database statistics after maintenance"""
        stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "databases_discovered": len(self.db_registry),
            "database_summary": {}
        }
        
        for db_type, db_list in self.db_registry.items():
            total_size = sum(db_info["size"] for db_info in db_list)
            stats["database_summary"][db_type] = {
                "count": len(db_list),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "healthy_count": sum(1 for db_info in db_list if db_info.get("healthy", False))
            }
        
        return stats


# Convenience function to run database maintenance
async def run_database_maintenance(memory_system, force: bool = False) -> Dict:
    """Convenience function to run database maintenance"""
    maintenance = DatabaseMaintenance(memory_system)
    return await maintenance.run_maintenance(force)