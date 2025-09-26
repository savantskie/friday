#!/usr/bin/env python3
"""Test embedding dimensions from different providers"""

import asyncio
import aiohttp
import json

async def test_lm_studio_dimensions():
    """Test LM Studio embedding dimensions"""
    try:
        url = 'http://192.168.1.50:1234/v1/embeddings'
        headers = {'Content-Type': 'application/json'}
        data = {
            'input': 'test text for dimension checking',
            'model': 'text-embedding-nomic-embed-text-v1.5'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    embedding = result['data'][0]['embedding']
                    print(f'✅ LM Studio embedding dimensions: {len(embedding)}')
                    print(f'✅ Model: {result.get("model", "unknown")}')
                    return len(embedding)
                else:
                    print(f'❌ LM Studio request failed: {response.status}')
                    return None
    except Exception as e:
        print(f'❌ LM Studio connection error: {e}')
        return None

async def test_ollama_dimensions():
    """Test Ollama embedding dimensions"""
    try:
        url = 'http://localhost:11434/api/embeddings'
        data = {
            'model': 'nomic-embed-text',
            'prompt': 'test text for dimension checking'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    embedding = result['embedding']
                    print(f'✅ Ollama embedding dimensions: {len(embedding)}')
                    return len(embedding)
                else:
                    print(f'❌ Ollama request failed: {response.status}')
                    return None
    except Exception as e:
        print(f'❌ Ollama connection error: {e}')
        return None

async def main():
    """Test all embedding providers"""
    print('🔍 Testing embedding dimensions from different providers...')
    
    lm_dims = await test_lm_studio_dimensions()
    ollama_dims = await test_ollama_dimensions()
    
    print(f'\n📊 Summary:')
    print(f'📊 Current database embeddings: 768 dimensions (binary format)')
    if lm_dims:
        print(f'📊 LM Studio embeddings: {lm_dims} dimensions')
    if ollama_dims:
        print(f'📊 Ollama embeddings: {ollama_dims} dimensions')
    
    # Determine compatibility
    print(f'\n🔍 Compatibility Analysis:')
    if lm_dims == 768 and ollama_dims == 768:
        print('✅ All providers use 768 dimensions - fully compatible!')
    elif lm_dims and lm_dims != 768:
        print(f'⚠️ LM Studio uses {lm_dims}D, existing embeddings are 768D - mixed dimensions!')
    elif ollama_dims and ollama_dims != 768:
        print(f'⚠️ Ollama uses {ollama_dims}D, existing embeddings are 768D - mixed dimensions!')

if __name__ == "__main__":
    asyncio.run(main())
