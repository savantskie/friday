#!/usr/bin/env python3
"""
Friday Memory HTTP API Server

Provides a REST API interface for GUI clients to interact with the Friday Memory System.
Runs alongside the MCP server without interfering with its operation.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from uvicorn import Config, Server
from pydantic import BaseModel

# Import the memory system
from friday_memory_system import FridayMemorySystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Friday Memory API", version="1.0.0")

# Request/Response models
class MemoryQuery(BaseModel):
    query: str
    limit: Optional[int] = 10
    database_filter: Optional[str] = "all"
    min_importance: Optional[int] = None
    max_importance: Optional[int] = None
    memory_type: Optional[str] = None

class ConversationStore(BaseModel):
    content: str
    role: str
    session_id: Optional[str] = None
    metadata: Optional[Dict] = None

class MemoryCreate(BaseModel):
    content: str
    memory_type: Optional[str] = None
    importance_level: Optional[int] = 5
    tags: Optional[list[str]] = None
    source_conversation_id: Optional[str] = None

class AppointmentCreate(BaseModel):
    title: str
    scheduled_datetime: str
    description: Optional[str] = None
    location: Optional[str] = None

class ReminderCreate(BaseModel):
    content: str
    due_datetime: str
    priority_level: Optional[int] = 5

# Initialize memory system
memory_system = FridayMemorySystem()

@app.get("/")
async def root():
    return {"status": "ok", "service": "Friday Memory API"}

@app.post("/memories/search")
async def search_memories(query: MemoryQuery):
    try:
        result = await memory_system.search_memories(
            query=query.query,
            limit=query.limit,
            database_filter=query.database_filter,
            min_importance=query.min_importance,
            max_importance=query.max_importance,
            memory_type=query.memory_type
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversations")
async def store_conversation(data: ConversationStore):
    try:
        result = await memory_system.store_conversation(
            content=data.content,
            role=data.role,
            session_id=data.session_id,
            metadata=data.metadata
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memories")
async def create_memory(data: MemoryCreate):
    try:
        result = await memory_system.create_memory(
            content=data.content,
            memory_type=data.memory_type,
            importance_level=data.importance_level,
            tags=data.tags,
            source_conversation_id=data.source_conversation_id
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/appointments")
async def create_appointment(data: AppointmentCreate):
    try:
        result = await memory_system.create_appointment(
            title=data.title,
            scheduled_datetime=data.scheduled_datetime,
            description=data.description,
            location=data.location
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reminders")
async def create_reminder(data: ReminderCreate):
    try:
        result = await memory_system.create_reminder(
            content=data.content,
            due_datetime=data.due_datetime,
            priority_level=data.priority_level
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/context/recent")
async def get_recent_context(limit: int = 5, session_id: Optional[str] = None):
    try:
        result = await memory_system.get_recent_context(limit, session_id)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/health")
async def get_system_health():
    try:
        result = await memory_system.get_system_health()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def main():
    """Start the HTTP API server"""
    config = Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
    server = Server(config)

    logger.info("Starting Friday Memory API server on http://127.0.0.1:8000")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
