"""Utility functions for the Friday memory system."""

from datetime import datetime, timezone
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

def parse_timestamp(timestamp: Union[str, int, float, None], fallback: Optional[datetime] = None) -> str:
    """
    Parse a timestamp into a consistent ISO 8601 UTC string.

    Args:
        timestamp (Union[str, int, float, None]): The input timestamp to parse.
            - ISO 8601 string (e.g., "2025-08-04T18:30:29Z")
            - Unix timestamp in seconds or milliseconds (e.g., 1628100000 or 1628100000000)
        fallback (Optional[datetime]): A fallback datetime if parsing fails.

    Returns:
        str: The parsed timestamp as an ISO 8601 string in UTC.
    """
    if timestamp is None:
        # Use fallback or current UTC time if no timestamp is provided
        fallback_time = fallback or datetime.now(timezone.utc)
        return fallback_time.isoformat()

    try:
        # Handle ISO 8601 strings
        if isinstance(timestamp, str):
            # Adjust for common quirks (e.g., "Z" for UTC)
            if "Z" in timestamp:
                timestamp = timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(timestamp).astimezone(timezone.utc).isoformat()

        # Handle Unix timestamps
        if isinstance(timestamp, (int, float)):
            # Automatically handle milliseconds vs. seconds
            if timestamp > 10**10:  # Likely milliseconds
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    except Exception as e:
        # Log the error and use fallback
        logger.warning(f"Failed to parse timestamp '{timestamp}': {e}")
        fallback_time = fallback or datetime.now(timezone.utc)
        return fallback_time.isoformat()
    
    # If all parsing attempts fail, use fallback
    fallback_time = fallback or datetime.now(timezone.utc)
    return fallback_time.isoformat()
