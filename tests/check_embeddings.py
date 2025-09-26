#!/usr/bin/env python3
"""Check existing embedding dimensions across all databases"""

import sqlite3
import json
import os

def check_embedding_dimensions():
    """Check embedding dimensions in all Friday databases"""
    dbs = [
        'memory_data/conversations.db', 
        'memory_data/ai_memory.db', 
        'memory_data/schedule.db', 
        'memory_data/vscode_projects.db'
    ]
    
    total_embeddings = 0
    dimension_counts = {}
    
    for db_path in dbs:
        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            continue
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            print(f"\n📊 {db_path}:")
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table_tuple in tables:
                table_name = table_tuple[0]
                try:
                    # Check if table has embedding column
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    has_embedding = any(col[1] == 'embedding' for col in columns)
                    
                    if has_embedding:
                        # Count embeddings
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE embedding IS NOT NULL")
                        count = cursor.fetchone()[0]
                        
                        if count > 0:
                            # Sample embeddings to check dimensions
                            cursor.execute(f"SELECT embedding FROM {table_name} WHERE embedding IS NOT NULL LIMIT 5")
                            sample_embeddings = cursor.fetchall()
                            
                            dimensions_found = set()
                            for embedding_blob in sample_embeddings:
                                if embedding_blob[0]:
                                    try:
                                        embedding = json.loads(embedding_blob[0])
                                        if isinstance(embedding, list):
                                            dimensions_found.add(len(embedding))
                                    except:
                                        pass
                            
                            if dimensions_found:
                                for dim in dimensions_found:
                                    dimension_counts[dim] = dimension_counts.get(dim, 0) + count
                                    
                                print(f"  • {table_name}: {count} embeddings, dimensions: {dimensions_found}")
                                total_embeddings += count
                            else:
                                print(f"  • {table_name}: {count} embeddings, invalid format")
                        
                except Exception as e:
                    print(f"  ⚠️ Error checking table {table_name}: {e}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error reading {db_path}: {e}")
    
    print(f"\n📈 Summary:")
    print(f"Total embeddings: {total_embeddings}")
    print(f"Dimension distribution:")
    for dim, count in sorted(dimension_counts.items()):
        print(f"  • {dim}D: {count} embeddings")
    
    return dimension_counts

if __name__ == "__main__":
    check_embedding_dimensions()
