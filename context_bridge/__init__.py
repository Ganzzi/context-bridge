"""Context Bridge - Unified Python package for RAG documentation workflows."""

__version__ = "0.2.1"

from .config import Config, get_config, set_config
from .core import ContextBridge

__all__ = ["Config", "get_config", "set_config", "ContextBridge"]
