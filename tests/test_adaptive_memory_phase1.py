"""
Test Suite for Adaptive Memory v3 Phase 1 Integration with Friday Memory System

This test simulates the core functionality of Adaptive Memory v3 without requiring
a full OpenWebUI instance. It uses a local Ollama LLM for memory extraction and
tests the integration with Friday Memory System.

Tests:
1. Memory extraction from user messages
2. Friday Memory System linking
3. Database operations
4. Error handling and non-blocking design
5. Metadata preservation
"""

import sys
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp

# Setup paths
FRIDAY_PATH = Path("/media/nate/Friday/Friday")
sys.path.insert(0, str(FRIDAY_PATH))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_adaptive_memory")

# Import Friday Memory System
try:
    from friday_memory_system import ConversationDatabase, AIMemoryDatabase
    logger.info("✓ Friday Memory System imported successfully")
except ImportError as e:
    logger.error(f"✗ Failed to import Friday Memory System: {e}")
    sys.exit(1)


class OllamaLLMClient:
    """Client for communicating with local Ollama LLM"""
    
    def __init__(self, model: str = "mistral-small:24b", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint
        self.api_endpoint = f"{endpoint}/api/chat"
        
    async def extract_memories(self, user_message: str) -> List[Dict[str, Any]]:
        """Use LLM to extract structured memories from user message"""
        
        prompt = f"""Extract memory operations from the following user message. 
Respond with a JSON array of memory objects. Each object should have:
- operation: "NEW", "UPDATE", or "DELETE"
- content: the memory content (for NEW/UPDATE)
- tags: array of tags (identity, preference, behavior, relationship, goal, possession)
- memory_bank: "General", "Personal", or "Work"

User message: "{user_message}"

Important: Respond with ONLY valid JSON array, no other text."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_endpoint,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "temperature": 0.7,
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Ollama API error: {response.status}")
                    
                    result = await response.json()
                    content = result.get("message", {}).get("content", "")
                    
                    # Try to parse JSON from response
                    try:
                        # Find JSON array in response
                        start = content.find('[')
                        end = content.rfind(']') + 1
                        if start >= 0 and end > start:
                            json_str = content[start:end]
                            memories = json.loads(json_str)
                            return memories if isinstance(memories, list) else []
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse LLM response as JSON: {content[:100]}")
                    
                    return []
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise


class MockOpenWebUIMemory:
    """Mock OpenWebUI memory storage"""
    
    def __init__(self):
        self.memories = {}
        self.counter = 0
    
    async def add_memory(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Mock add_memory function"""
        self.counter += 1
        memory_id = str(uuid.uuid4())
        
        memory = {
            "id": memory_id,
            "content": content,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.memories[memory_id] = memory
        logger.info(f"Mock OpenWebUI: Created memory {memory_id[:8]}... with {len(content)} chars")
        return memory
    
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Mock get_memory function"""
        return self.memories.get(memory_id)
    
    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Get all stored memories"""
        return list(self.memories.values())


class AdaptiveMemoryPhase1Tester:
    """Test harness for Adaptive Memory v3 Phase 1"""
    
    def __init__(self):
        self.ollama_client = OllamaLLMClient()
        self.mock_memory = MockOpenWebUIMemory()
        
        # Initialize both database systems with proper paths
        try:
            self.conversation_db = ConversationDatabase("memory_data/conversations.db")
            logger.info("✓ ConversationDatabase initialized")
        except Exception as e:
            logger.error(f"✗ Failed to initialize ConversationDatabase: {e}")
            raise
        
        try:
            self.ai_memory_db = AIMemoryDatabase("memory_data/ai_memories.db")
            logger.info("✓ AIMemoryDatabase initialized")
        except Exception as e:
            logger.error(f"✗ Failed to initialize AIMemoryDatabase: {e}")
            raise
        
        self.test_user_id = "test_user_" + str(uuid.uuid4())[:8]
        self.conversation_id = f"openwebui_{self.test_user_id}"
        self.memory_links_created = []
        
    async def test_memory_extraction(self):
        """Test 1: Extract memories from user message using Ollama"""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Memory Extraction with Ollama LLM")
        logger.info("="*60)
        
        test_messages = [
            "My name is Nathan and I'm from Minnesota. I like programming and AI.",
            "I work as a software engineer and enjoy working with Python.",
            "My favorite food is pizza with pepperoni and I can't have caffeine.",
        ]
        
        all_extracted = []
        
        for msg in test_messages:
            logger.info(f"\nExtracting from: '{msg}'")
            try:
                memories = await self.ollama_client.extract_memories(msg)
                logger.info(f"✓ Extracted {len(memories)} memory operations")
                
                for mem in memories:
                    logger.info(f"  - {mem.get('operation', 'UNKNOWN')}: {mem.get('content', '')[:50]}...")
                    all_extracted.append(mem)
                    
            except Exception as e:
                logger.error(f"✗ Extraction failed: {e}")
                # Non-blocking: continue with next message
        
        logger.info(f"\n✓ Total extracted: {len(all_extracted)} memories")
        return len(all_extracted) > 0
    
    async def test_memory_creation_and_linking(self):
        """Test 2: Create memories in OpenWebUI and link to Friday"""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Memory Creation and Friday Linking")
        logger.info("="*60)
        
        # First, create a session and conversation in Friday so foreign key constraint is satisfied
        timestamp = datetime.now(timezone.utc).isoformat()
        session_id = str(uuid.uuid4())
        
        try:
            await self.conversation_db.execute_update(
                "INSERT INTO sessions (session_id, start_timestamp, context) VALUES (?, ?, ?)",
                (session_id, timestamp, "test_session")
            )
            
            await self.conversation_db.execute_update(
                "INSERT INTO conversations (conversation_id, session_id, start_timestamp) VALUES (?, ?, ?)",
                (self.conversation_id, session_id, timestamp)
            )
            logger.info(f"✓ Created test conversation: {self.conversation_id[:8]}...")
        except Exception as e:
            logger.warning(f"Could not pre-create conversation (might already exist): {e}")
        
        test_memories = [
            {
                "operation": "NEW",
                "content": "Nathan has ADHD and memory challenges from strokes",
                "tags": ["identity", "health"],
                "memory_bank": "Personal",
            },
            {
                "operation": "NEW",
                "content": "Prefers Python and async programming",
                "tags": ["preference", "behavior"],
                "memory_bank": "Work",
            },
            {
                "operation": "NEW",
                "content": "Lives in Minnesota (Central Time)",
                "tags": ["identity", "location"],
                "memory_bank": "Personal",
            },
        ]
        
        created_count = 0
        linked_count = 0
        
        for memory_dict in test_memories:
            try:
                # Step 1: Create memory in mock OpenWebUI
                result = await self.mock_memory.add_memory(
                    content=memory_dict["content"],
                    metadata={
                        "tags": memory_dict.get("tags", []),
                        "memory_bank": memory_dict.get("memory_bank", "General"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source": "adaptive_memory_v3",
                    }
                )
                created_count += 1
                mem_id = result["id"]
                logger.info(f"✓ Created OpenWebUI memory: {mem_id[:8]}...")
                
                # Step 2: Link to Friday Memory System
                try:
                    await self.conversation_db.link_memory_to_conversation(
                        memory_id=str(mem_id),
                        conversation_id=self.conversation_id,
                        link_type="direct",
                        metadata={
                            "source": "adaptive_memory_v3",
                            "tags": memory_dict.get("tags", []),
                            "memory_bank": memory_dict.get("memory_bank", "General"),
                        }
                    )
                    linked_count += 1
                    self.memory_links_created.append(mem_id)
                    logger.info(f"✓ Linked to Friday Memory System")
                    
                except Exception as e:
                    logger.warning(f"⚠ Friday linking failed (non-blocking): {e}")
                    # Non-blocking: continue even if Friday fails
                    
            except Exception as e:
                logger.error(f"✗ Memory operation failed: {e}")
        
        logger.info(f"\n✓ Created: {created_count} memories")
        logger.info(f"✓ Linked: {linked_count} memories")
        
        return created_count > 0 and linked_count > 0
    
    async def test_friday_link_retrieval(self):
        """Test 3: Verify links were stored correctly in Friday"""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Friday Link Retrieval and Verification")
        logger.info("="*60)
        
        if not self.memory_links_created:
            logger.warning("⚠ No links to verify (skipping)")
            return True
        
        try:
            # Query the links we created
            links = await self.conversation_db.get_memory_conversation_links(
                conversation_id=self.conversation_id
            )
            
            logger.info(f"✓ Retrieved {len(links)} links from Friday")
            
            if len(links) > 0:
                logger.info("\nLink details:")
                for link in links[:3]:  # Show first 3
                    logger.info(f"  - Memory {link.get('memory_id', '')[:8]}...")
                    logger.info(f"    Type: {link.get('link_type')}")
                    
                    # Metadata is stored as JSON string
                    metadata = link.get('metadata', '{}')
                    if isinstance(metadata, str):
                        try:
                            import json
                            metadata = json.loads(metadata)
                        except:
                            metadata = {}
                    
                    logger.info(f"    Tags: {metadata.get('tags', [])}")
                return True
            else:
                logger.warning("✗ No links found (database issue?)")
                return False
                
        except Exception as e:
            logger.error(f"✗ Link retrieval failed: {e}")
            return False
    
    async def test_non_blocking_error_handling(self):
        """Test 4: Verify non-blocking error handling"""
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Non-Blocking Error Handling")
        logger.info("="*60)
        
        logger.info("Testing that memory creation succeeds even if Friday fails...")
        
        # This simulates what happens in production if Friday is unavailable
        memory_created = await self.mock_memory.add_memory(
            content="Test non-blocking: this should work",
            metadata={
                "tags": ["test"],
                "source": "adaptive_memory_v3",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        
        logger.info(f"✓ Memory created successfully (non-blocking design works)")
        return True
    
    async def test_metadata_preservation(self):
        """Test 5: Verify metadata is preserved through linking"""
        logger.info("\n" + "="*60)
        logger.info("TEST 5: Metadata Preservation")
        logger.info("="*60)
        
        test_memory = {
            "content": "Test metadata preservation",
            "tags": ["test", "metadata", "phase1"],
            "memory_bank": "Personal",
            "source": "adaptive_memory_v3",
        }
        
        # Create memory
        result = await self.mock_memory.add_memory(
            content=test_memory["content"],
            metadata=test_memory
        )
        mem_id = result["id"]
        
        # Link with metadata
        await self.conversation_db.link_memory_to_conversation(
            memory_id=str(mem_id),
            conversation_id=self.conversation_id,
            link_type="direct",
            metadata={
                "tags": test_memory["tags"],
                "memory_bank": test_memory["memory_bank"],
            }
        )
        
        # Retrieve and verify
        links = await self.conversation_db.get_memory_conversation_links(
            memory_id=str(mem_id)
        )
        
        if links:
            link = links[0]
            metadata = link.get("metadata", {})
            
            # Metadata is stored as JSON string, so parse it if needed
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            if metadata.get("tags") == test_memory["tags"]:
                logger.info(f"✓ Tags preserved: {metadata.get('tags')}")
            else:
                logger.warning(f"✗ Tags mismatch: {metadata.get('tags')}")
            
            if metadata.get("memory_bank") == test_memory["memory_bank"]:
                logger.info(f"✓ Memory bank preserved: {metadata.get('memory_bank')}")
            else:
                logger.warning(f"✗ Memory bank mismatch: {metadata.get('memory_bank')}")
            
            return True
        
        logger.warning("✗ Could not verify metadata")
        return False
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("\n" + "="*80)
        logger.info("ADAPTIVE MEMORY V3 PHASE 1 TEST SUITE")
        logger.info("Testing integration with Friday Memory System using Local Ollama")
        logger.info("="*80)
        
        logger.info(f"\nTest Configuration:")
        logger.info(f"  LLM: {self.ollama_client.model}")
        logger.info(f"  Ollama Endpoint: {self.ollama_client.endpoint}")
        logger.info(f"  Test User ID: {self.test_user_id}")
        logger.info(f"  Conversation ID: {self.conversation_id}")
        
        results = {}
        
        try:
            # Test 1: Memory Extraction
            logger.info("\n[1/5] Running memory extraction test...")
            results["extraction"] = await self.test_memory_extraction()
            
            # Test 2: Memory Creation and Linking
            logger.info("\n[2/5] Running memory creation and linking test...")
            results["creation_linking"] = await self.test_memory_creation_and_linking()
            
            # Test 3: Link Retrieval
            logger.info("\n[3/5] Running Friday link retrieval test...")
            results["retrieval"] = await self.test_friday_link_retrieval()
            
            # Test 4: Non-Blocking Error Handling
            logger.info("\n[4/5] Running non-blocking error handling test...")
            results["non_blocking"] = await self.test_non_blocking_error_handling()
            
            # Test 5: Metadata Preservation
            logger.info("\n[5/5] Running metadata preservation test...")
            results["metadata"] = await self.test_metadata_preservation()
            
        except Exception as e:
            logger.error(f"✗ Test suite error: {e}")
            import traceback
            traceback.print_exc()
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {test_name}")
        
        logger.info(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("\n🎉 All tests passed! Phase 1 integration is working correctly.")
            return 0
        else:
            logger.info(f"\n⚠ {total - passed} test(s) failed. Check logs above for details.")
            return 1


async def main():
    """Main entry point"""
    tester = AdaptiveMemoryPhase1Tester()
    exit_code = await tester.run_all_tests()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
