#!/usr/bin/env python3
"""
Friday Training Data Exporter
Exports all conversations from Friday's long-term memory databases
into HuggingFace-ready ShareGPT JSONL format for NateML training.

Handles both main conversations.db and all archive databases automatically.
Outputs chunked JSONL files to avoid massive single files.

Usage:
    python friday_export_training.py
    python friday_export_training.py --output-dir /path/to/output --chunk-size 5000
"""

import sqlite3
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional


MEMORY_DATA_PATH = "/media/nate/Friday/Friday/memory_data"
ARCHIVES_PATH    = f"{MEMORY_DATA_PATH}/archives"
DEFAULT_OUT_DIR  = "./friday_training_data"
DEFAULT_CHUNK    = 5000  # conversations per output file

ROLE_MAP = {
    "user":      "human",
    "human":     "human",
    "assistant": "gpt",
    "friday":    "gpt",
    "system":    "system",
}


def get_columns(cursor, table: str) -> List[str]:
    """Return column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def extract_conversations(db_path: str) -> List[Dict]:
    """
    Extract all conversations from a single database.
    Returns list of ShareGPT-format dicts:
        {"conversations": [{"from": "human", "value": "..."}, ...]}
    Skips conversations with fewer than 2 messages.
    Handles schema differences between main db and archives gracefully.
    """
    results = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Check what columns messages table actually has
        msg_cols = get_columns(cur, "messages")

        # Build select — only grab columns that exist
        select_cols = ["message_id", "conversation_id", "timestamp", "role", "content"]
        if "user_id"  in msg_cols: select_cols.append("user_id")
        if "model_id" in msg_cols: select_cols.append("model_id")

        col_str = ", ".join(select_cols)

        cur.execute(
            f"SELECT {col_str} FROM messages ORDER BY conversation_id, timestamp ASC"
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return []

        # Group messages by conversation_id
        convos: Dict[str, List] = {}
        for row in rows:
            cid = row["conversation_id"]
            if cid not in convos:
                convos[cid] = []
            convos[cid].append(dict(row))

        # Convert each conversation to ShareGPT format
        for cid, messages in convos.items():
            if len(messages) < 2:
                continue  # skip single-message fragments

            turns = []
            for msg in messages:
                raw_role = (msg.get("role") or "").lower().strip()
                mapped   = ROLE_MAP.get(raw_role, "human")
                content  = (msg.get("content") or "").strip()
                if not content:
                    continue
                turns.append({"from": mapped, "value": content})

            if len(turns) >= 2:
                results.append({"conversations": turns})

    except sqlite3.Error as e:
        print(f"  [WARN] DB error in {db_path}: {e}")
    except Exception as e:
        print(f"  [WARN] Unexpected error in {db_path}: {e}")

    return results


def write_chunk(conversations: List[Dict], out_path: Path):
    """Write a list of conversations to a JSONL file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for convo in conversations:
            f.write(json.dumps(convo, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Export Friday long-term memory to HuggingFace JSONL training data"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for JSONL files (default: {DEFAULT_OUT_DIR})"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=DEFAULT_CHUNK,
        help=f"Conversations per output file (default: {DEFAULT_CHUNK})"
    )
    parser.add_argument(
        "--archives-only",
        action="store_true",
        help="Skip main conversations.db, only process archives"
    )
    args = parser.parse_args()

    out_dir    = Path(args.output_dir)
    chunk_size = args.chunk_size

    # Collect all database paths
    db_paths: List[Path] = []

    if not args.archives_only:
        main_db = Path(MEMORY_DATA_PATH) / "conversations.db"
        if main_db.exists():
            db_paths.append(main_db)
        else:
            print(f"[WARN] Main db not found at {main_db}")

    archives_dir = Path(ARCHIVES_PATH)
    if archives_dir.exists():
        archive_dbs = sorted(archives_dir.glob("conversations_*.db"))
        db_paths.extend(archive_dbs)
        print(f"Found {len(archive_dbs)} archive databases")
    else:
        print(f"[WARN] Archives directory not found at {ARCHIVES_PATH}")

    if not db_paths:
        print("No databases found. Check your paths.")
        return

    print(f"Processing {len(db_paths)} databases...")
    print(f"Output directory: {out_dir}")
    print(f"Chunk size: {chunk_size} conversations per file\n")

    all_convos: List[Dict] = []
    total_dbs_processed = 0
    total_skipped = 0

    for i, db_path in enumerate(db_paths, 1):
        print(f"[{i}/{len(db_paths)}] {db_path.name}...", end=" ", flush=True)
        convos = extract_conversations(str(db_path))
        print(f"{len(convos)} conversations")
        if convos:
            all_convos.extend(convos)
            total_dbs_processed += 1
        else:
            total_skipped += 1

    if not all_convos:
        print("\nNo conversations extracted. Nothing to write.")
        return

    # Write chunked JSONL output
    total_convos = len(all_convos)
    num_chunks   = (total_convos + chunk_size - 1) // chunk_size

    print(f"\nWriting {total_convos} conversations across {num_chunks} file(s)...")

    for chunk_idx in range(num_chunks):
        start   = chunk_idx * chunk_size
        end     = min(start + chunk_size, total_convos)
        chunk   = all_convos[start:end]
        out_file = out_dir / f"friday_training_{chunk_idx + 1:04d}.jsonl"
        write_chunk(chunk, out_file)
        print(f"  Wrote {len(chunk):,} conversations -> {out_file.name}")

    # Summary
    total_turns = sum(len(c["conversations"]) for c in all_convos)
    print(f"\n{'='*60}")
    print(f"EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Databases processed : {total_dbs_processed}")
    print(f"Databases skipped   : {total_skipped} (empty)")
    print(f"Total conversations : {total_convos:,}")
    print(f"Total turns         : {total_turns:,}")
    print(f"Output files        : {num_chunks}")
    print(f"Output directory    : {out_dir.resolve()}")
    print(f"{'='*60}")
    print(f"\nFiles are ready for HuggingFace datasets.load_dataset('json', ...)")


if __name__ == "__main__":
    main()
