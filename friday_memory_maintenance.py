"""
Friday Memory System - Long-Term Memory Maintenance Module

Provides LLM-powered maintenance operations for long-term (curated) memories:
- Format reformatting: Rewrites old-style memories to match short-term system format
- Contradiction/update scanning: Detects new info superseding old memories
- Link assistance: Helps reconnect unlinked memories to source conversations

Uses the same memory format style as the short-term extraction prompt (first-person
for assistant observations, "User is..." phrasing, proper tags and memory banks).
Never culls or deletes memories -- only appends update notes and creates links.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import httpx

logger = logging.getLogger(__name__)

# Default LLM endpoint for maintenance tasks
DEFAULT_LLM_ENDPOINT = "http://192.168.1.50:8080/v1/chat/completions"
DEFAULT_LLM_MODEL = "Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced"

# Memory format markers used by the short-term system
KNOWN_BANKS = {
    "General", "Personal", "Work", "Projects", "Technical",
    "Tasks", "Research", "Context", "Patterns", "Preferences",
    "Temporary", "Character", "Character_Interaction", "Intimate",
    "Adult_Content"
}

# Minimum batch size for LLM overlap analysis
CONTRADICTION_BATCH_SIZE = 10
# Maximum memories to scan per maintenance run (prevents overload)
MAX_SCAN_PER_RUN = 200


class LongTermMemoryMaintenance:
    """
    LLM-powered maintenance operations for long-term (curated) memories.

    Designed to be called from DatabaseMaintenance.run_maintenance() but
    can also be instantiated independently for standalone use.
    """

    def __init__(self, memory_system, llm_endpoint: str = None, llm_model: str = None):
        self.memory_system = memory_system
        self.llm_endpoint = llm_endpoint or DEFAULT_LLM_ENDPOINT
        self.llm_model = llm_model or DEFAULT_LLM_MODEL

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.1) -> Optional[str]:
        """Call the maintenance LLM and return response text, or None on failure."""
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
                        # Strip any think tags
                        content = re.sub(
                            r'<\s*/?\s*(?:think|thinking)\s*>.*?</\s*(?:think|thinking)\s*>\s*',
                            '', content, flags=re.DOTALL
                        )
                        return content.strip()
                logger.warning(f"LLM returned status {resp.status_code}: {await resp.text()[:200]}")
                return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Format reformatting (Feature 1)
    # ------------------------------------------------------------------

    def _needs_reformat(self, content: str) -> bool:
        """Check if a memory is missing the short-term format markers and needs reformatting."""
        if not content:
            return False
        # Check for format markers the short-term system always includes
        has_bank_marker = bool(re.search(r'\[Memory Bank:\s*([^\]]+)\]', content))
        has_tags_marker = bool(re.search(r'\[Tags:\s*([^\]]+)\]', content))
        # If both markers exist, assume it's in proper format
        if has_bank_marker and has_tags_marker:
            return False
        return True

    def _get_reformat_prompt(self) -> str:
        """Build the system prompt for memory reformatting.

        Adapted from the short-term memory extraction prompt's formatting rules.
        The LLM receives raw memory text and rewrites it to match the style
        the short-term system uses (proper perspective, tags, banks).
        """
        return (
            "You are a memory formatting assistant. Your ONLY function is to reformat existing "
            "memory text into the proper memory system format used by the short-term memory system.\n\n"

            "The memory system uses this format for all memories:\n"
            '- [Tags: tag1, tag2, ...] The memory content here [Memory Bank: BankName]\n\n'

            "When reformatting, follow these content rules:\n"
            "- About the user: Use 'User is...', 'User prefers...', 'User mentioned...'\n"
            "- About the assistant's own experiences: Use first-person ('I noticed...', 'I found that...')\n"
            "- About characters in roleplay: Use appropriate character perspective\n"
            "- Keep all factual content intact -- do not add new information\n"
            "- Use clear, natural language. Avoid clinical or sterile phrasing.\n"
            "- Remove confusing temporal markers like 'previously' or 'was' that assume a past context\n\n"

            "Tag and bank assignment rules:\n"
            f"- Memory banks: One of {sorted(KNOWN_BANKS)}\n"
            "- Tags: Comma-separated, lowercase, descriptive (e.g., user, preference, technical, project)\n"
            "- Always include at minimum one tag indicating the type of information\n\n"

            "IMPORTANT:\n"
            "- Do NOT change the meaning of the memory\n"
            "- Do NOT add speculative content\n"
            "- If the memory is already in correct format, return it as-is\n"
            "- Preserve any [Importance: N] markers if present\n"
            "- Output ONLY the reformatted memory text. No JSON. No markdown. No explanations."
        )

    async def reformat_memories(self, limit: int = 100) -> Dict:
        """
        Scan curated_memories for memories missing short-term format markers
        and reformat them via LLM.

        Args:
            limit: Max memories to reformat per run

        Returns:
            Dict with scan stats
        """
        results = {"scanned": 0, "reformatted": 0, "skipped": 0, "errors": 0}

        try:
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT memory_id, content, user_id, model_id, memory_bank, tags, timestamp_created
                   FROM curated_memories
                   ORDER BY timestamp_created ASC
                   LIMIT ?""",
                (limit,)
            )
            if not memories:
                logger.info("No memories found for format reformatting")
                return results

            results["scanned"] = len(memories)

            for mem in memories:
                mem_id = mem["memory_id"]
                content = mem.get("content", "") or ""

                # Skip if already in proper format
                if not self._needs_reformat(content):
                    results["skipped"] += 1
                    continue

                # Reformat via LLM
                reformatted = await self._reformat_single_memory(content, mem)
                if reformatted and reformatted != content:
                    try:
                        await self.memory_system.ai_memory_db.execute_update(
                            """UPDATE curated_memories
                               SET content = ?, timestamp_updated = ?, updated_at = ?
                               WHERE memory_id = ?""",
                            (reformatted, datetime.now(timezone.utc).isoformat(),
                             datetime.now(timezone.utc).isoformat(), mem_id)
                        )
                        results["reformatted"] += 1
                        logger.debug(f"Reformatted memory {mem_id}")
                    except Exception as e:
                        logger.error(f"Failed to update memory {mem_id}: {e}")
                        results["errors"] += 1
                else:
                    results["skipped"] += 1

                await asyncio.sleep(0.3)  # Rate limit

        except Exception as e:
            logger.error(f"Error in memory reformatting: {e}")
            results["errors"] = results.get("errors", 0) + 1

        logger.info(f"Memory reformatting complete: {results['reformatted']} reformatted, "
                     f"{results['skipped']} skipped, {results['errors']} errors")
        return results

    async def _reformat_single_memory(self, content: str, mem: Dict) -> Optional[str]:
        """Send one memory to LLM for reformatting."""
        # Strip existing format markers to get bare content
        bare_content = re.sub(r'\[Tags:\s*[^\]]*\]\s*', '', content)
        bare_content = re.sub(r'\[Memory Bank:\s*[^\]]*\]\s*', '', bare_content)
        bare_content = re.sub(r'\[User:\s*[^\]]*\]\s*', '', bare_content)
        bare_content = re.sub(r'\[Model:\s*[^\]]*\]\s*', '', bare_content)
        bare_content = re.sub(r'\[Importance:\s*[^\]]*\]\s*', '', bare_content)
        bare_content = bare_content.strip()

        user_prompt = (
            f"Reformat the following memory text into the proper memory system format.\n\n"
            f"Memory content:\n{bare_content}\n\n"
            f"Additional context: user_id={mem.get('user_id', 'unknown')}, "
            f"model_id={mem.get('model_id', 'unknown')}\n"
            f"Current tags: {mem.get('tags', 'none')}\n"
            f"Current bank: {mem.get('memory_bank', 'General')}\n\n"
            f"Output ONLY the reformatted memory text."
        )

        response = await self._call_llm(self._get_reformat_prompt(), user_prompt)
        return response

    # ------------------------------------------------------------------
    # Contradiction/Update Scanner (Feature 2)
    # ------------------------------------------------------------------

    def _get_contradiction_prompt(self) -> str:
        """Build the system prompt for contradiction/update detection."""
        return (
            "You are a memory analysis assistant. Your job is to compare memory texts "
            "and identify pairs that cover the same topic but contain differing or updated information.\n\n"

            "For each pair you identify, determine:\n"
            "- Which memory is the OLDER one (contains outdated info or is less complete)\n"
            "- Which memory is the NEWER one (has the current/more complete info)\n"
            "- The relationship type:\n"
            "  * 'updated_by' -- newer memory supersedes or corrects the older one\n"
            "  * 'complements' -- newer memory adds detail the older one lacks\n"
            "  * 'related_to' -- same topic but neither clearly updates the other\n"
            "- A brief note explaining what changed or what was added (use memory-style phrasing)\n\n"

            "IMPORTANT RULES:\n"
            "- ONLY flag pairs that are clearly about the same topic\n"
            "- Do NOT flag pairs that are unrelated even if they share common words\n"
            "- Use 'updated_by' when the newer info contradicts or replaces old info\n"
            "- Use 'complements' when the newer info adds to but doesn't contradict\n"
            "- Use 'related_to' when they overlap but neither is clearly newer\n"
            "- Write notes in memory format style ('User mentioned...', 'Updated detail about...')\n\n"

            "Output ONLY a JSON object with this structure (no markdown, no explanation):\n"
            '{"pairs": [{"older_index": 0, "newer_index": 1, "relationship_type": "updated_by", '
            '"notes": "User updated their preference from X to Y"}, ...]}\n\n'
            "If no pairs found, output: {\"pairs\": []}"
        )

    async def scan_for_updates(self, limit: int = MAX_SCAN_PER_RUN) -> Dict:
        """
        Scan long-term memories for contradictions, updates, or complementary info.
        For each identified pair:
        - Appends an update note to the older memory content
        - Creates a memory_relationships link between them
        - Never deletes or overwrites anything

        Args:
            limit: Max memories to scan per run

        Returns:
            Dict with scan stats
        """
        results = {"scanned": 0, "pairs_found": 0, "updated": 0, "linked": 0,
                    "skipped_already_related": 0, "errors": 0}

        try:
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT memory_id, content, user_id, model_id, memory_bank,
                          tags, timestamp_created, importance_level
                   FROM curated_memories
                   ORDER BY timestamp_created ASC
                   LIMIT ?""",
                (limit,)
            )
            if not memories or len(memories) < 2:
                logger.info("Not enough memories for update scanning")
                return results

            results["scanned"] = len(memories)

            # Get existing relationships to avoid re-processing
            existing_relations = await self.memory_system.conversations_db.execute_query(
                "SELECT DISTINCT source_memory_id, target_memory_id FROM memory_relationships", ()
            ) if await self._table_exists("memory_relationships") else []
            already_linked = set()
            for rel in (existing_relations or []):
                already_linked.add((rel.get("source_memory_id", ""), rel.get("target_memory_id", "")))

            # Process in batches
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

                    # Append update note to older memory
                    if notes:
                        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        update_note = f" [Updated: {timestamp}: {notes}]"
                        new_content = older_mem["content"] + update_note
                        try:
                            await self.memory_system.ai_memory_db.execute_update(
                                """UPDATE curated_memories
                                   SET content = ?, timestamp_updated = ?, updated_at = ?
                                   WHERE memory_id = ?""",
                                (new_content, datetime.now(timezone.utc).isoformat(),
                                 datetime.now(timezone.utc).isoformat(), older_mem["memory_id"])
                            )
                            results["updated"] += 1
                        except Exception as e:
                            logger.error(f"Failed to append update note to {older_mem['memory_id']}: {e}")
                            results["errors"] += 1
                            continue

                    # Create relationship link
                    try:
                        await self._create_relationship(
                            source_memory_id=older_mem["memory_id"],
                            target_memory_id=newer_mem["memory_id"],
                            relationship_type=rel_type,
                            notes=notes
                        )
                        results["linked"] += 1
                    except Exception as e:
                        logger.error(f"Failed to create relationship: {e}")
                        results["errors"] += 1

                await asyncio.sleep(0.5)  # Rate limit between batches

        except Exception as e:
            logger.error(f"Error scanning for memory updates: {e}")
            results["errors"] = results.get("errors", 0) + 1

        logger.info(f"Update scan complete: {results['pairs_found']} pairs, "
                     f"{results['updated']} updated, {results['linked']} linked, "
                     f"{results['errors']} errors")
        return results

    async def _analyze_batch(self, batch: List[Dict],
                             already_linked: set) -> List[Dict]:
        """Send a batch of memories to the LLM for pair analysis."""
        if not batch or len(batch) < 2:
            return []

        # Build batch text for LLM
        batch_text = ""
        for idx, mem in enumerate(batch):
            content = mem.get("content", "") or ""
            # Strip update notes to compare core content
            core = re.sub(r'\s*\[Updated:\s*[^\]]*\]\s*', '', content).strip()
            batch_text += f"[{idx}] {core[:300]}\n---\n"

        user_prompt = (
            f"Analyze these memories and identify pairs that cover the same topic "
            f"with updated/complementary information.\n\n"
            f"Memories:\n{batch_text}\n\n"
            f"Output ONLY a JSON object with the pairs array."
        )

        response = await self._call_llm(self._get_contradiction_prompt(), user_prompt,
                                        temperature=0.1)
        if not response:
            return []

        # Parse JSON from response
        return self._parse_pairs_json(response, already_linked)

    def _parse_pairs_json(self, text: str, already_linked: set) -> List[Dict]:
        """Parse the LLM's JSON response into pair dicts, filtering already-linked."""
        # Strip markdown fences if present
        text = re.sub(r'```json|```', '', text).strip()
        # Find JSON boundaries
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start == -1 or brace_end == -1 or brace_end < brace_start:
            logger.warning(f"Could not find JSON in LLM response: {text[:100]}")
            return []

        text = text[brace_start:brace_end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse LLM response as JSON: {text[:100]}")
            return []

        pairs = data.get("pairs", [])
        if not isinstance(pairs, list):
            return []

        # Filter out already-linked pairs
        filtered = []
        for pair in pairs:
            older_idx = pair.get("older_index", -1)
            newer_idx = pair.get("newer_index", -1)
            if older_idx < 0 or newer_idx < 0:
                continue
            # Check if already linked (in either direction)
            pair_key_fwd = (str(older_idx), str(newer_idx))
            pair_key_rev = (str(newer_idx), str(older_idx))
            if pair_key_fwd in already_linked or pair_key_rev in already_linked:
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
        """Insert a record into the memory_relationships table."""
        rel_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Ensure table exists
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
        """Check if a table exists in the conversations database."""
        try:
            rows = await self.memory_system.conversations_db.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return len(rows) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Link assistance (tap into existing retroactive linking)
    # ------------------------------------------------------------------

    async def assist_linking(self, limit: int = 50) -> Dict:
        """
        LLM-assisted linking for memories that have no source_conversation_id
        and no entry in memory_conversation_links.
        Uses the LLM to analyze memory content and match it to likely conversations.

        Supplements the existing text-overlap matcher in
        database_maintenance._retroactively_link_memories() by handling
        cases where the simple text matcher was insufficient.
        """
        results = {"scanned": 0, "llm_linked": 0, "no_match": 0, "errors": 0}

        try:
            # Find memories without conversation links
            memories = await self.memory_system.ai_memory_db.execute_query(
                """SELECT m.memory_id, m.content, m.user_id, m.model_id, m.timestamp_created
                   FROM curated_memories m
                   WHERE (m.source_conversation_id IS NULL OR m.source_conversation_id = '')
                   ORDER BY m.timestamp_created DESC
                   LIMIT ?""",
                (limit,)
            )
            if not memories:
                return results

            # Get already-linked memory IDs
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
                    continue  # Too short to match

                # Get recent conversations for this user
                conversations = await self.memory_system.conversations_db.execute_query(
                    """SELECT c.conversation_id, c.topic_summary, m.content as msg_content
                       FROM conversations c
                       LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                       WHERE c.user_id = ? OR ? = ''
                       ORDER BY c.start_timestamp DESC
                       LIMIT 200""",
                    (mem.get("user_id", ""), mem.get("user_id", ""))
                )

                if not conversations:
                    continue

                results["scanned"] += 1

                # Try text overlap first (same as retroactive linking)
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
                    score = overlap / union if union > 0 else 0.0
                    if score > best_score:
                        best_score = score
                        best_match = conv

                # Link if score is good enough
                if best_match and best_score >= 0.15:
                    conv_id = best_match["conversation_id"]
                    await self.memory_system.conversations_db.link_memory_to_conversation(
                        memory_id=mem_id,
                        conversation_id=conv_id,
                        link_type="related",
                        link_strength=min(best_score, 1.0),
                        source_system="retroactive_link",
                        metadata={"match_score": best_score,
                                   "matched_via": "llm_assisted_maintenance"}
                    )
                    results["llm_linked"] += 1
                else:
                    results["no_match"] += 1

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in assisted linking: {e}")
            results["errors"] = results.get("errors", 0) + 1

        logger.info(f"Link assistance complete: {results['llm_linked']} linked, "
                     f"{results['no_match']} unmatched, {results['errors']} errors")
        return results

    # ------------------------------------------------------------------
    # Run all maintenance tasks
    # ------------------------------------------------------------------

    async def run_all(self, limit_reformat: int = 100,
                      limit_scan: int = MAX_SCAN_PER_RUN,
                      limit_link: int = 50) -> Dict:
        """Run all long-term memory maintenance tasks."""
        results = {
            "reformat": await self.reformat_memories(limit_reformat),
            "updates": await self.scan_for_updates(limit_scan),
            "linking": await self.assist_linking(limit_link),
        }
        return results
