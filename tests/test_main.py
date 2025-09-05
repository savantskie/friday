"""
Unit tests for the my_app module.

Uses pytest framework to validate core functionality.
"""

import pytest
from my_app.main import greet
from my_app.utils.helpers import format_greeting

def test_greet():
    """Test the greet function with various inputs."""
    assert greet("Alice") == "Hello, Alice!"
    assert greet("Bob") == "Hello, Bob!"
    assert greet("") == "Hello, !"

def test_format_greeting():
    """Test the format_greeting function with different inputs."""
    assert format_greeting("Hello, World!") == "\n============\nHello, World!\n============\n"
    assert format_greeting("Hi") == "\n=\nHi\n="