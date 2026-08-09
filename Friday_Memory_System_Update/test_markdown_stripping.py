#!/usr/bin/env python3
"""
Test the new markdown stripping function with various edge cases
"""

import sys
sys.path.insert(0, "/media/nate/Friday/Friday")

# We need to mock the logger for testing
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test")

# Create a minimal test class to test the function
class MockMemorySystem:
    def __init__(self):
        pass
    
    def _strip_markdown_json_response(self, text: str) -> str:
        """
        Aggressively strip markdown formatting from JSON responses.
        Handles incomplete markdown fences and finds JSON boundaries intelligently.
        """
        if not text or not text.strip():
            return text
        
        original_text = text
        original_length = len(text)
        
        # Stage 1: Strip common markdown fence patterns (all variations)
        logger.debug(f"[MARKDOWN_STRIP] Starting cleanup of {original_length} char response")
        
        # Remove complete ```json ... ``` blocks
        if text.strip().startswith("```json") and text.strip().endswith("```"):
            text = text.strip()[7:-3].strip()
            logger.debug(f"[MARKDOWN_STRIP] Removed complete ```json fences: {original_length} -> {len(text)} chars")
            return text
        
        # Remove complete ``` ... ``` blocks (generic)
        if text.strip().startswith("```") and text.strip().endswith("```"):
            text = text.strip()[3:-3].strip()
            logger.debug(f"[MARKDOWN_STRIP] Removed complete ``` fences: {original_length} -> {len(text)} chars")
            return text
        
        # Stage 2: Handle incomplete/broken markdown (opening fence without closing, or vice versa)
        text_stripped = text.strip()
        
        # Remove opening ```json fence (even if closing is missing)
        if text_stripped.startswith("```json"):
            text = text_stripped[7:].strip()
            logger.debug(f"[MARKDOWN_STRIP] Removed opening ```json fence (incomplete)")
        # Remove opening ``` fence (even if closing is missing)
        elif text_stripped.startswith("```"):
            text = text_stripped[3:].strip()
            logger.debug(f"[MARKDOWN_STRIP] Removed opening ``` fence (incomplete)")
        
        # Remove closing ``` fence if present (handles asymmetric cases)
        if text.strip().endswith("```"):
            text = text.strip()[:-3].strip()
            logger.debug(f"[MARKDOWN_STRIP] Removed closing ``` fence")
        
        # Stage 3: Intelligent JSON boundary extraction
        text_content = text.strip()
        
        first_bracket_pos = text_content.find("[")
        first_brace_pos = text_content.find("{")
        last_bracket_pos = text_content.rfind("]")
        last_brace_pos = text_content.rfind("}")
        
        json_start = -1
        json_end = -1
        
        # Determine where JSON likely starts
        if first_bracket_pos != -1 and (first_brace_pos == -1 or first_bracket_pos < first_brace_pos):
            json_start = first_bracket_pos
        elif first_brace_pos != -1:
            json_start = first_brace_pos
        
        # Determine where JSON likely ends
        if last_bracket_pos != -1 and (last_brace_pos == -1 or last_bracket_pos > last_brace_pos):
            json_end = last_bracket_pos
        elif last_brace_pos != -1:
            json_end = last_brace_pos
        
        # If we found valid boundaries, extract the JSON
        if json_start != -1 and json_end != -1 and json_end >= json_start:
            potential_json = text_content[json_start:json_end + 1]
            
            # Sanity check: balanced brackets/braces
            bracket_open = potential_json.count("[")
            bracket_close = potential_json.count("]")
            brace_open = potential_json.count("{")
            brace_close = potential_json.count("}")
            
            if bracket_open == bracket_close and brace_open == brace_close:
                text = potential_json
                reduction = original_length - len(text)
                logger.debug(
                    f"[MARKDOWN_STRIP] Extracted JSON from boundaries: "
                    f"{original_length} -> {len(text)} chars (removed {reduction})"
                )
            else:
                logger.debug(
                    f"[MARKDOWN_STRIP] Found boundaries but brackets unbalanced. Keeping text as-is."
                )
        else:
            logger.debug(f"[MARKDOWN_STRIP] Could not identify JSON boundaries. Keeping text as-is.")
        
        final_length = len(text)
        if final_length < original_length:
            logger.debug(f"[MARKDOWN_STRIP] Complete: {original_length} -> {final_length} chars removed")
        else:
            logger.debug(f"[MARKDOWN_STRIP] No markup found, text unchanged")
        
        return text


# Test cases
test_cases = [
    # (name, input, expected_output)
    (
        "Complete ```json fences",
        '```json\n{"status": "success"}\n```',
        '{"status": "success"}'
    ),
    (
        "Incomplete opening ```json (no closing)",
        '```json\n{"status": "success"}',
        '{"status": "success"}'
    ),
    (
        "Incomplete opening ``` (no closing)",
        '```\n{"status": "success"}',
        '{"status": "success"}'
    ),
    (
        "Text before and after JSON",
        'Here is the JSON:\n{"status": "success"}\nThat is all',
        '{"status": "success"}'
    ),
    (
        "Complete ``` fences",
        '```\n{"status": "success"}\n```',
        '{"status": "success"}'
    ),
    (
        "Array in ```json fences",
        '```json\n[{"operation": "NEW"}]\n```',
        '[{"operation": "NEW"}]'
    ),
    (
        "Already clean JSON",
        '{"status": "success"}',
        '{"status": "success"}'
    ),
    (
        "Complex nested JSON",
        '```json\n{"status": "success", "data": {"nested": [1, 2, 3]}}\n```',
        '{"status": "success", "data": {"nested": [1, 2, 3]}}'
    ),
]

def run_tests():
    mock = MockMemorySystem()
    passed = 0
    failed = 0
    
    print("\n" + "="*70)
    print("Testing Markdown Stripping Function")
    print("="*70 + "\n")
    
    for name, input_text, expected in test_cases:
        result = mock._strip_markdown_json_response(input_text)
        is_pass = result == expected
        
        status = "✓ PASS" if is_pass else "✗ FAIL"
        print(f"{status}: {name}")
        if not is_pass:
            print(f"  Input:    {repr(input_text[:60])}")
            print(f"  Expected: {repr(expected)}")
            print(f"  Got:      {repr(result)}")
            failed += 1
        else:
            passed += 1
        print()
    
    print("="*70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("="*70 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
