#!/usr/bin/env python3
"""
Test script to query LM Studio /v1/models endpoint
to see what metadata is available about running models
"""

import aiohttp
import asyncio
import json
from typing import Dict, Any

async def test_lm_studio_models(api_endpoint: str = "http://192.168.1.50:1234") -> None:
    """Query LM Studio /v1/models endpoint and inspect response."""
    
    models_url = f"{api_endpoint}/v1/models"
    
    print(f"\n{'='*70}")
    print(f"Testing LM Studio /v1/models endpoint")
    print(f"URL: {models_url}")
    print(f"{'='*70}\n")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(models_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ SUCCESS - Response received\n")
                    print("Full Response:")
                    print(json.dumps(data, indent=2))
                    
                    # Parse and analyze
                    if "data" in data:
                        print(f"\n{'='*70}")
                        print("ANALYSIS:")
                        print(f"{'='*70}")
                        print(f"Number of models: {len(data['data'])}\n")
                        
                        for idx, model in enumerate(data["data"], 1):
                            print(f"Model {idx}:")
                            print(f"  ID: {model.get('id', 'N/A')}")
                            print(f"  Object type: {model.get('object', 'N/A')}")
                            print(f"  Owned by: {model.get('owned_by', 'N/A')}")
                            
                            # Check for additional fields
                            other_fields = {k: v for k, v in model.items() 
                                          if k not in ['id', 'object', 'owned_by']}
                            if other_fields:
                                print(f"  Other fields: {json.dumps(other_fields, indent=4)}")
                            print()
                        
                        # Check for embedding model designation
                        print(f"{'='*70}")
                        print("EMBEDDING MODEL DETECTION:")
                        print(f"{'='*70}")
                        for model in data["data"]:
                            model_id = model.get('id', '')
                            model_obj = model.get('object', '')
                            
                            is_embedding = (
                                'embedding' in model_id.lower() or
                                'embed' in model_id.lower() or
                                model_obj == 'embedding'
                            )
                            
                            if is_embedding:
                                print(f"✅ EMBEDDING MODEL DETECTED: {model_id}")
                                print(f"   Object type: {model_obj}")
                            else:
                                print(f"❌ Not an embedding model: {model_id}")
                                print(f"   Object type: {model_obj}")
                            print()
                    
                else:
                    print(f"❌ ERROR - Status code: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    
        except asyncio.TimeoutError:
            print(f"❌ TIMEOUT - Could not reach LM Studio at {api_endpoint}")
            print("Make sure LM Studio is running and accessible")
        except ConnectionError as e:
            print(f"❌ CONNECTION ERROR: {e}")
            print("Make sure LM Studio is running and accessible")
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")

async def test_embeddings_endpoint(api_endpoint: str = "http://192.168.1.50:1234") -> None:
    """Test the /v1/embeddings endpoint to see response structure."""
    
    embeddings_url = f"{api_endpoint}/v1/embeddings"
    
    print(f"\n{'='*70}")
    print(f"Testing LM Studio /v1/embeddings endpoint")
    print(f"URL: {embeddings_url}")
    print(f"{'='*70}\n")
    
    payload = {
        "model": "text-embedding-nomic-embed-text-v1.5",
        "input": "test embedding query"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                embeddings_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ SUCCESS - Embeddings endpoint responded\n")
                    
                    # Show structure without full embedding vectors
                    data_copy = json.loads(json.dumps(data))
                    if "data" in data_copy and isinstance(data_copy["data"], list):
                        for item in data_copy["data"]:
                            if "embedding" in item and isinstance(item["embedding"], list):
                                item["embedding"] = f"<vector of length {len(item['embedding'])}>"
                    
                    print("Response Structure:")
                    print(json.dumps(data_copy, indent=2))
                    
                else:
                    print(f"❌ ERROR - Status code: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    
        except asyncio.TimeoutError:
            print(f"❌ TIMEOUT - Embedding request took too long")
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")

async def main():
    """Run all tests."""
    api_endpoint = "http://192.168.1.50:1234"
    
    await test_lm_studio_models(api_endpoint)
    await test_embeddings_endpoint(api_endpoint)
    
    print(f"\n{'='*70}")
    print("Test Complete")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(main())
