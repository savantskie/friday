"""
Persistent AI Memory - Long-Term Memory Maintenance Module

Provides LLM-powered maintenance operations for long-term (curated) memories:
- Format reformatting: Rewrites old-style memories to match current format
- Contradiction/update scanning: Detects new info superseding old memories
- Link assistance: Helps reconnect unlinked memories to source conversations

Uses the same memory format style as the short-term extraction prompt.
Never culls or deletes memories -- only appends update notes and creates links.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

# Default LLM endpoint for maintenance tasks
DEFAULT_LLM_ENDPOINT = os.getenv("AI_MEMORY_LLM_ENDPOINT", "http://localhost:8080/v1/chat/completions")
DEFAULT_LLM_MODEL = os.getenv("AI_MEMORY_LLM_MODEL", "qwen-3")

KNOWN_BANKS = {
    "General", "Personal", "Work", "Projects", "Technical",
    "Tasks", "Research", "Context", "Patterns", "Preferences",
    "Temporary", "Character", "Character_Interaction"
}

CONTRADICTION_BATCH_SIZE = 10
MAX_SCAN_PER_RUN = 200


class LongTermMemoryMaintenance:
    """
    LLM-powered maintenance operations for long-term (curated) memories.
    Designed to be called from DatabaseMaintenance.run_maintenance().
    """

    def __init__(self, memory_system, llm_endpoint: str = None, llm_model: str = None):
        self.memory_system = memory_system
        self.llm_endpoint = llm_endpoint or DEFAULT_LLM_ENDPOINT
        self.llm_model = llm_model or DEFAULT_LLM_MODEL

    async def _call_llm(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.1) -> Optional[str]:
        if httpx is None:
            logger.error("httpx not available for LLM calls")
            return None
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.llm_endpoint,
                    json={
                        "model": self.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": 1024,
                        "stream": False,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    message = data.get("choices", [{}])[0].get("message", {})
                    content = message.get("content") or message.get("reasoning_content", "")
                    if content:
                        content = re.sub(
                            r'<\s*/?\s*(?:think|thinking)\s*>.*?</\s*(?:think|thinking)\s*>\s*',
                            '', content, flags=re.DOTALL
                        )
                        return content.strip()
                logger.warning(f"LLM returned status {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _needs_reformat(self, content: str) -> bool:
        if not content:
            return False
        has_bank = bool(re.search(r'\[Memory Bank:\s*([^\]]+)\]', content))
        has_tags = bool(re.search(r'\[Tags:\s*([^\]]+)\]', content))
        return not (has_bank and has_tags)

    def _get_reformat_prompt(self) -> str:
        return (
            "You are a memory formatting assistant. Your ONLY function is to reformat existing "
            "memory text into the proper memory system format.\n\n"

            "The memory system uses this format:\n"
            '- [Tags: tag1, tag2, ...] The memory content here [Memory Bank: BankName]\n\n'

            "Content rules:\n"
            "- About the user: 'User is...', 'User prefers...', 'User mentioned...'\n"
            "- About the assistant's own experiences: 'I noticed...', 'I found that...'\n"
            "- About characters: Use appropriate character perspective\n"
            "- Keep all factual content intact. Use clear, natural language.\n"
            "- Remove confusing temporal markers like 'previously'\n\n"

            f"Memory banks: {sorted(KNOWN_BANKS)}\n"
            "- Tags: comma-separated, lowercase, descriptive\n\n"

            "Output ONLY the reformatted memory text. No JSON. No markdown. No explanations."
        )

    async def reformat_memories(self, limit: int = 100) -> Dict:
        results = {"scanned": 0, "reformatted": 0, "skipped": 0, "errors": 0}
        try:
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT memory_id, content, user_id, model_id, memory_bank, tags, timestamp_created
                   FROM curated_memories
                   ORDER BY timestamp_created ASC LIMIT ?""",
                (limit,)
            )
            if not memories:
                return results
            results["scanned"] = len(memories)

            for mem in memories:
                mem_id = mem["memory_id"]
                content = mem.get("content", "") or ""
                if not self._needs_reformat(content):
                    results["skipped"] += 1
                    continue

                bare = re.sub(r'\[Tags:\s*[^\]]*\]\s*', '', content)
                bare = re.sub(r'\[Memory Bank:\s*[^\]]*\]\s*', '', bare)
                bare = re.sub(r'\[User:\s*[^\]]*\]\s*', '', bare)
                bare = re.sub(r'\[Model:\s*[^\]]*\]\s*', '', bare)
                bare = bare.strip()

                user_prompt = (
                    f"Reformat this memory:\n\n{bare}\n\n"
                    f"Context: user_id={mem.get('user_id', 'unknown')}, "
                    f"model_id={mem.get('model_id', 'unknown')}\n"
                    f"Current tags: {mem.get('tags', 'none')}\n"
                    f"Current bank: {mem.get('memory_bank', 'General')}"
                )
                reformatted = await self._call_llm(self._get_reformat_prompt(), user_prompt)
                if reformatted and reformatted != content:
                    await self.memory_system.ai_memory_db.execute_update(
                        """UPDATE curated_memories SET content = ?, timestamp_updated = ?, updated_at = ?
                           WHERE memory_id = ?""",
                        (reformatted, datetime.now(timezone.utc).isoformat(),
                         datetime.now(timezone.utc).isoformat(), mem_id)
                    )
                    results["reformatted"] += 1
                else:
                    results["skipped"] += 1
                await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Error in memory reformatting: {e}")
            results["errors"] = results.get("errors", 0) + 1
        return results

    def _get_contradiction_prompt(self) -> str:
        return (
            "You are a memory analysis assistant. Compare memory texts and identify pairs "
            "covering the same topic with differing or updated information.\n\n"

            "For each pair determine:\n"
            "- older_index: index of the older/outdated memory\n"
            "- newer_index: index of the newer/updated memory\n"
            "- relationship_type: 'updated_by', 'complements', or 'related_to'\n"
            "- notes: brief explanation in memory format style ('User mentioned...', 'Updated detail...')\n\n"

            "Output ONLY a JSON object:\n"
            '{"pairs": [{"older_index": 0, "newer_index": 1, '
            '"relationship_type": "updated_by", "notes": "..."}, ...]}\n'
            'If no pairs: {"pairs": []}'
        )

    async def scan_for_updates(self, limit: int = MAX_SCAN_PER_RUN) -> Dict:
        results = {"scanned": 0, "pairs_found": 0, "updated": 0,
                    "linked": 0, "skipped_already_related": 0, "errors": 0}
        try:
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT memory_id, content, user_id, model_id, memory_bank,
                          tags, timestamp_created, importance_level
                   FROM curated_memories ORDER BY timestamp_created ASC LIMIT ?""",
                (limit,)
            )
            if not memories or len(memories) < 2:
                return results
            results["scanned"] = len(memories)

            existing = await self._table_exists("memory_relationships")
            existing_relations = []
            if existing:
                existing_relations = await self.memory_system.conversations_db.execute_query(
                    "SELECT DISTINCT source_memory_id, target_memory_id FROM memory_relationships", ()
                )
            already_linked = set()
            for rel in (existing_relations or []):
                already_linked.add((rel.get("source_memory_id", ""), rel.get("target_memory_id", "")))

            for batch_start in range(0, len(memories), CONTRADICTION_BATCH_SIZE):
                batch = memories[batch_start:batch_start + CONTRADICTION_BATCH_SIZE]
                batch_pairs = await self._analyze_batch(batch, already_linked)
                if not batch_pairs:
                    continue
                results["pairs_found"] += len(batch_pairs)

                for pair in batch_pairs:
                    older_mem = batch[pair["older_index"]]
                    newer_mem = batch[pair["newer_index"]]
                    rel_type = pair["relationship_type"]
                    notes = pair.get("notes", "")

                    if notes:
                        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        update_note = f" [Updated: {timestamp}: {notes}]"
                        new_content = older_mem["content"] + update_note
                        await self.memory_system.ai_memory_db.execute_update(
                            """UPDATE curated_memories SET content = ?, timestamp_updated = ?, updated_at = ?
                               WHERE memory_id = ?""",
                            (new_content, datetime.now(timezone.utc).isoformat(),
                             datetime.now(timezone.utc).isoformat(), older_mem["memory_id"])
                        )
                        results["updated"] += 1

                    await self._create_relationship(
                        source_memory_id=older_mem["memory_id"],
                        target_memory_id=newer_mem["memory_id"],
                        relationship_type=rel_type, notes=notes
                    )
                    results["linked"] += 1

                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error scanning for updates: {e}")
            results["errors"] = results.get("errors", 0) + 1
        return results

    async def _analyze_batch(self, batch: List[Dict], already_linked: set) -> List[Dict]:
        if not batch or len(batch) < 2:
            return []
        batch_text = ""
        for idx, mem in enumerate(batch):
            content = mem.get("content", "") or ""
            core = re.sub(r'\s*\[Updated:\s*[^\]]*\]\s*', '', content).strip()
            batch_text += f"[{idx}] {core[:300]}\n---\n"

        response = await self._call_llm(
            self._get_contradiction_prompt(),
            f"Analyze these memories:\n\n{batch_text}",
            temperature=0.1
        )
        if not response:
            return []
        return self._parse_pairs_json(response, already_linked)

    def _parse_pairs_json(self, text: str, already_linked: set) -> List[Dict]:
        text = re.sub(r'```json|```', '', text).strip()
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start == -1 or brace_end == -1:
            return []
        text = text[brace_start:brace_end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        pairs = data.get("pairs", [])
        if not isinstance(pairs, list):
            return []

        filtered = []
        for pair in pairs:
            older_idx = pair.get("older_index", -1)
            newer_idx = pair.get("newer_index", -1)
            if older_idx < 0 or newer_idx < 0:
                continue
            fwd = (str(older_idx), str(newer_idx))
            rev = (str(newer_idx), str(older_idx))
            if fwd in already_linked or rev in already_linked:
                continue
            filtered.append({
                "older_index": older_idx,
                "newer_index": newer_idx,
                "relationship_type": pair.get("relationship_type", "related_to"),
                "notes": pair.get("notes", "")
            })
        return filtered

    async def _create_relationship(self, source_memory_id: str, target_memory_id: str,
                                    relationship_type: str, notes: str = ""):
        rel_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        await self.memory_system.conversations_db.execute_update("""
            CREATE TABLE IF NOT EXISTS memory_relationships (
                relationship_id TEXT PRIMARY KEY,
                source_memory_id TEXT NOT NULL,
                target_memory_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """, ())
        await self.memory_system.conversations_db.execute_update(
            """INSERT OR IGNORE INTO memory_relationships
               (relationship_id, source_memory_id, target_memory_id,
                relationship_type, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rel_id, source_memory_id, target_memory_id,
             relationship_type, notes, timestamp)
        )

    async def _table_exists(self, table_name: str) -> bool:
        try:
            rows = await self.memory_system.conversations_db.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
            )
            return len(rows) > 0
        except Exception:
            return False

    async def assist_linking(self, limit: int = 50) -> Dict:
        results = {"scanned": 0, "llm_linked": 0, "no_match": 0, "errors": 0}
        try:
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT m.memory_id, m.content, m.user_id, m.model_id, m.timestamp_created
                   FROM curated_memories m
                   WHERE (m.source_conversation_id IS NULL OR m.source_conversation_id = '')
                   ORDER BY m.timestamp_created DESC LIMIT ?""",
                (limit,)
            )
            if not memories:
                return results

            linked_rows = await self.memory_system.conversations_db.execute_query(
                "SELECT DISTINCT memory_id FROM memory_conversation_links", ()
            )
            already_linked = {row["memory_id"] for row in (linked_rows or [])}

            for mem in memories:
                mem_id = mem["memory_id"]
                if mem_id in already_linked:
                    continue
                content = mem.get("content", "") or ""
                if len(content) < 20:
                    continue

                conversations = await self.memory_system.conversations_db.execute_query(
                    """SELECT c.conversation_id, c.topic_summary, m.content as msg_content
                       FROM conversations c
                       LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                       WHERE c.user_id = ? OR ? = ''
                       ORDER BY c.start_timestamp DESC LIMIT 200""",
                    (mem.get("user_id", ""), mem.get("user_id", ""))
                )
                if not conversations:
                    continue

                results["scanned"] += 1
                search_words = set(re.sub(r'\[[^\]]*\]\s*', '', content).lower().split())
                if len(search_words) < 3:
                    continue

                best_match = None
                best_score = 0.0
                for conv in conversations:
                    msg_content = conv.get("msg_content", "") or ""
                    msg_words = set(msg_content.lower().split())
                    if not msg_words:
                        continue
                    overlap = len(search_words & msg_words)
                    union = len(search_words | msg_words)
                    overlap_ratio = overlap / union if union > 0 else 0.0
                    if overlap_ratio > best_score:
                        best_score = overlap_ratio
                        best_match = conv

                if best_match and best_score >= 0.15:
                    conv_id = best_match["conversation_id"]
                    await self.memory_system.conversations_db.link_memory_to_conversation(
                        memory_id=mem_id, conversation_id=conv_id, link_type="derived"
                    )
                    results["llm_linked"] += 1
                else:
                    results["no_match"] += 1

                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in assisted linking: {e}")
            results["errors"] = results.get("errors", 0) + 1
        return results

    async def run_all(self, limit_reformat: int = 100,
                      limit_scan: int = MAX_SCAN_PER_RUN,
                      limit_link: int = 50) -> Dict:
        return {
            "reformat": await self.reformat_memories(limit_reformat),
            "updates": await self.scan_for_updates(limit_scan),
            "linking": await self.assist_linking(limit_link),
        }
