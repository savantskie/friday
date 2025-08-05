#!/usr/bin/env python3
"""Quick script to run database maintenance"""

import asyncio
from friday_memory_system import FridayMemorySystem
from database_maintenance import DatabaseMaintenance

async def main():
    print("Starting database maintenance...")
    try:
        memory = FridayMemorySystem()
        maintenance = DatabaseMaintenance(memory)
        results = await maintenance.run_maintenance()
        print("\nResults:")
        print(f"- Timestamp: {results.get('maintenance_timestamp')}")
        print(f"- Schema upgrades: {results.get('schema_upgrades', [])}")
        print(f"- Cleanup results: {results.get('cleanup_results', {})}")
        print(f"- Optimization results: {results.get('optimization_results', {})}")
        print(f"- Statistics: {results.get('statistics', {})}")
    except Exception as e:
        print(f"Error running maintenance: {e}")

if __name__ == "__main__":
    asyncio.run(main())
