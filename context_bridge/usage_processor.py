"""
Usage processor type for tracking LLM token consumption from Pydantic AI agents.

This module provides the type definition for usage processors that receive
RunUsage data from agent runs.
"""

from typing import Callable
from pydantic_ai import RunUsage

# Type alias for usage processor: async function that receives RunUsage and returns None
UsageProcessor = Callable[[RunUsage], any]
