# Order of Operations Analysis: Adaptive Memory v3 Issues
**Date:** November 17, 2025  
**Status:** CRITICAL STRUCTURAL ISSUES IDENTIFIED

## Summary
Your modified version (`Adaptive_Memory_v3.py`) has **broken the initialization order** compared to the original (`Adaptive_Memory_v3_original.py`). This causes the plugin to fail because dependencies are initialized in the wrong sequence.

---

## CRITICAL ISSUE #1: `EmbeddingCache` and `get_nomic_embedding()` Placed Before `Filter` Class

### What Changed
**Original structure:**
```
1. Imports
2. Logging setup
3. MemoryOperation class
4. Filter class (with all nested classes and methods)
   - Valves (config)
   - UserValves
   - __init__()
   - All methods...
```

**Your modified structure:**
```
1. Imports
2. Logging setup
3. Friday Memory System integration
4. MemoryOperation class
5. EmbeddingCache class  ← NEW (WRONG LOCATION)
6. get_nomic_embedding() function  ← NEW (WRONG LOCATION)
7. Filter class  ← Now depends on things defined above
   - Valves
   - UserValves
   - __init__()
   - All methods...
```

### Why This Is a Problem
1. **Initialization dependencies are broken**: The `Filter` class now has upstream dependencies on `EmbeddingCache` and `get_nomic_embedding()` that didn't exist in the original
2. **Class properties fail**: The `embedding_model` property is modified to reference `get_nomic_embedding()` which wasn't originally there
3. **State management confusion**: The `_embedding_model` property returns `None` with a debug message, completely changing the original behavior
4. **Order matters for OpenWebUI plugin initialization**: The plugin system expects methods to be available in a specific order during the inlet/outlet lifecycle

### Evidence
- **Line 260-368 (your version):** `EmbeddingCache` class
- **Line 370-411 (your version):** `get_nomic_embedding()` function
- **Line 413+ (your version):** `Filter` class starts here

In the original, `Filter` class starts at line 209.

---

## CRITICAL ISSUE #2: Duplicate `Filter` Class Definition

The file shows TWO `class Filter:` definitions:
1. Line 413 in main Adaptive_Memory_v3.py
2. Line 221 in short term candidates/Adaptive_Memory_v3.py

This suggests a merge conflict or incomplete refactor where code wasn't properly consolidated.

---

## CRITICAL ISSUE #3: Import Order Changes

Your version adds new imports at the top:
```python
import sqlite3
import os
import pickle
```

While these are needed for `EmbeddingCache`, they should be grouped with OTHER imports, not scattered.

---

## CRITICAL ISSUE #4: Method Behavior Changed

### Original `embedding_model` property:
```python
@property
def embedding_model(self):
    if self._embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self._embedding_model = None
    return self._embedding_model
```
- **Returns:** An actual embedding model instance
- **Purpose:** Lazy-loads SentenceTransformer on first access
- **Used by:** Methods that call `self.embedding_model.encode()`

### Your modified `embedding_model` property:
```python
@property
def embedding_model(self):
    """
    Marker property for backward compatibility.
    Actual embedding calls now use async get_nomic_embedding() function.
    This property returns None since we're using async LM Studio API instead of SentenceTransformer.
    """
    logger.debug(
        "✓ Using async Nomic embeddings from LM Studio (text-embedding-nomic-embed-text-v1.5)"
    )
    return None  # Indicates async-based approach, not a local model
```
- **Returns:** Always `None`
- **Problem:** Any code that tries to use `self.embedding_model.encode()` will crash with `AttributeError: 'NoneType' object has no attribute 'encode'`
- **Breaking:** Methods like `_calculate_embedding_similarity()` and retrieval methods call this

---

## CRITICAL ISSUE #5: New Fields in Valves Not Consistent

Your version adds new valve configuration:
```python
enable_memory_promotion_task: bool = Field(default=True, ...)
memory_promotion_interval: int = Field(default=86400, ...)
```

But these are added OUT OF ORDER in the Background Task Management section. They should be grouped with other background task configs, not interspersed.

---

## Root Cause Analysis

The issue stems from **attempting to add LM Studio embedding support** by:
1. Creating an `EmbeddingCache` class before `Filter`
2. Creating an async `get_nomic_embedding()` function
3. Modifying the `embedding_model` property to return `None`
4. Not moving these INSIDE the `Filter` class as nested classes/static methods

This breaks the initialization order because:
- **Original pattern:** Filter class is self-contained; loads embedding model internally via lazy-loading property
- **Your pattern:** Filter class now depends on external classes/functions defined before it exists
- **Result:** When Filter's methods try to use `self.embedding_model`, they get `None` instead of a working model

---

## Solution Strategy

### Option A: Move EmbeddingCache and get_nomic_embedding() Inside Filter Class
```python
class Filter:
    class EmbeddingCache:
        # ... implementation ...
    
    @staticmethod
    async def get_nomic_embedding(text, lm_studio_url="..."):
        # ... implementation ...
    
    # Rest of Filter class...
```
**Pros:** Maintains original structure and initialization order  
**Cons:** Makes Filter class larger  

### Option B: Keep Them Outside But Place AFTER Complete Filter Class
```python
class MemoryOperation:
    # ...

class Filter:
    # Complete original implementation
    # ...
    # All nested classes and methods

# AFTER the Filter class is complete:
class EmbeddingCache:
    # ...

async def get_nomic_embedding():
    # ...
```
**Pros:** Clear separation of concerns  
**Cons:** Creates forward dependency issues if Filter methods reference these

### Option C: Fix the embedding_model Property to Handle Both Cases
```python
@property
def embedding_model(self):
    if self._embedding_model is None:
        # Try async LM Studio first
        try:
            return "lm_studio_async"  # Marker
        except:
            # Fall back to SentenceTransformer
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except:
                self._embedding_model = None
    return self._embedding_model
```
**Pros:** Maintains backward compatibility  
**Cons:** Requires refactoring all code that uses `embedding_model`

---

## Recommendation

**Use Option A** (move EmbeddingCache and get_nomic_embedding into Filter class):
- Maintains the original initialization order that OpenWebUI expects
- Filter class remains self-contained for plugin lifecycle management
- Preserves backward compatibility with existing method signatures
- Embedding logic stays close to where it's used

This restores the **correct order of operations** while keeping all your new LM Studio features.

---

## Files Affected
- `/media/nate/Friday/Friday/Adaptive_Memory_v3.py` (Current broken version)
- Should mirror the structure of `Adaptive_Memory_v3_original.py` with your enhancements integrated properly

## Next Steps
1. Remove EmbeddingCache and get_nomic_embedding() from top level
2. Move them inside the Filter class as static methods or nested classes
3. Update the embedding_model property to properly initialize and return the model or a marker
4. Verify all calling code can still work with the embedding model reference
5. Test with OpenWebUI to confirm plugin loads correctly
