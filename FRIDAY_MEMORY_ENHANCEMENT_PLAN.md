# Friday Memory System Enhancement Plan
# Enhanced Memory Formation with LLM-Generated Memories

"""
This document outlines how to enhance Friday Memory System to use
LLM-generated memories instead of raw chat logs, inspired by the
sophisticated OpenWebUI memory formation approach.
"""

## CURRENT STATE ANALYSIS

### OpenWebUI Memory System Strengths:
- Creates semantic memories from conversations
- Uses LLM to extract key facts and relationships  
- Includes temporal context and importance ranking
- Smart consolidation prevents redundancy
- Contextual tagging and categorization

### Friday Memory System Current Limitations:
- Stores mostly raw conversation excerpts
- Limited semantic understanding
- No importance ranking system
- Minimal consolidation logic
- Basic tagging approach

## ENHANCEMENT PROPOSAL

### Phase 1: Memory Formation Engine
```python
class MemoryFormationEngine:
    def __init__(self, llm_model="llama3.1:8b"):
        self.llm_model = llm_model
        
    async def form_memories_from_conversation(self, conversation_data):
        """
        Transform raw conversation into structured memories
        Similar to OpenWebUI's approach but enhanced for Friday
        """
        prompt = f"""You are Friday's Memory Formation System. Create precise, 
        factual memories from this conversation.

        Extract key information about:
        - Facts learned about Nate
        - Important events or decisions
        - Emotional context and relationships
        - Technical knowledge or preferences
        - Future plans or commitments

        For each memory, provide:
        - Content (factual statement)
        - Importance (1-10)
        - Type (personal, technical, health, relationship, etc.)
        - Date/time context
        - Tags for categorization

        Conversation:
        {conversation_data}
        """
        # LLM processing logic here
        return structured_memories
```

### Phase 2: Enhanced Storage Schema
```python
class EnhancedMemory:
    def __init__(self):
        self.id = uuid.uuid4()
        self.content = ""           # LLM-generated memory content
        self.importance = 5         # 1-10 importance ranking
        self.memory_type = ""       # personal, technical, health, etc.
        self.created_at = datetime.now()
        self.source_conversation_id = ""
        self.tags = []             # Auto-generated tags
        self.temporal_context = "" # "last week", "during our discussion about X"
        self.consolidation_count = 0  # How many times consolidated
        self.source_type = "chat"  # chat, email, document, etc.
```

### Phase 3: Multi-Source Integration
```python
class FridayMemoryEnhancement:
    def process_chat_logs(self, chat_data):
        """Process various chat sources into memories"""
        sources = {
            "openwebui": self.process_openwebui_chats,
            "discord": self.process_discord_logs, 
            "email": self.process_email_threads,
            "documents": self.process_document_content
        }
        
    def create_temporal_timeline(self, memories):
        """Create timeline-based memory organization"""
        # Group memories by time periods
        # Create narrative connections between related memories
        # Identify patterns and trends over time
```

## INTEGRATION WITH OPENWEBUI SYSTEM

### Bi-directional Flow:
1. **OpenWebUI → Friday**: 30-day memories transfer to long-term with enhanced context
2. **Friday → OpenWebUI**: Rich historical memories inform current conversations
3. **Cross-pollination**: Friday's multi-source memories enhance OpenWebUI context

### Enhanced Consolidation:
- Use OpenWebUI's consolidation logic in Friday
- Add temporal awareness (consolidate memories from same time period)
- Include source diversity (combine chat + email + document memories)

## QUESTIONS FOR YOUR SHORT-TERM SYSTEM

I'd love to see your advanced short-term candidate to compare:

1. How does it handle memory formation vs. raw storage?
2. What ranking/importance system does it use?
3. How does it handle temporal relationships?
4. What consolidation strategies does it employ?
5. How does it integrate with different data sources?

Please share the code and I'll analyze how we can combine the best of both systems!