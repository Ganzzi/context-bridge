"""Caching utilities for performance optimization."""

import streamlit as st
from datetime import datetime, timedelta
from typing import Any, Callable
import hashlib
import json


class CacheManager:
    """Manager for caching data with TTL support."""

    @staticmethod
    def get_cache_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate a cache key from prefix and arguments.

        Args:
            prefix: Cache key prefix
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            Unique cache key string
        """
        # Create a stable representation of args and kwargs
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items()),
        }

        # Convert to JSON and hash
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()

        return f"{prefix}_{key_hash}"

    @staticmethod
    def set(key: str, value: Any, ttl_seconds: int = 300):
        """
        Set a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default: 5 minutes)
        """
        if "cache" not in st.session_state:
            st.session_state.cache = {}

        expiry_time = datetime.now() + timedelta(seconds=ttl_seconds)
        st.session_state.cache[key] = {
            "value": value,
            "expiry": expiry_time,
        }

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get a value from cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        if "cache" not in st.session_state:
            return default

        cache_entry = st.session_state.cache.get(key)

        if cache_entry is None:
            return default

        # Check if expired
        if datetime.now() > cache_entry["expiry"]:
            # Remove expired entry
            del st.session_state.cache[key]
            return default

        return cache_entry["value"]

    @staticmethod
    def invalidate(key: str = None, prefix: str = None):
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate (if None, invalidates all)
            prefix: Prefix to match for invalidation
        """
        if "cache" not in st.session_state:
            return

        if key:
            # Invalidate specific key
            if key in st.session_state.cache:
                del st.session_state.cache[key]
        elif prefix:
            # Invalidate all keys with prefix
            keys_to_delete = [k for k in st.session_state.cache.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del st.session_state.cache[k]
        else:
            # Invalidate all
            st.session_state.cache = {}

    @staticmethod
    def cleanup_expired():
        """Remove all expired cache entries."""
        if "cache" not in st.session_state:
            return

        now = datetime.now()
        keys_to_delete = [
            key for key, entry in st.session_state.cache.items() if now > entry["expiry"]
        ]

        for key in keys_to_delete:
            del st.session_state.cache[key]


def cached_function(ttl_seconds: int = 300, key_prefix: str = None):
    """
    Decorator to cache function results.

    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Custom cache key prefix (uses function name if None)

    Usage:
        @cached_function(ttl_seconds=600)
        async def get_documents():
            # Expensive operation
            return documents
    """

    def decorator(func: Callable):
        import functools
        import asyncio

        prefix = key_prefix or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheManager.get_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = CacheManager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            CacheManager.set(cache_key, result, ttl_seconds)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheManager.get_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = CacheManager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            CacheManager.set(cache_key, result, ttl_seconds)

            return result

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Streamlit-native caching for pure functions
@st.cache_data(ttl=300)
def cache_documents_list(documents_json: str):
    """
    Cache documents list using Streamlit's native caching.

    Args:
        documents_json: JSON string of documents

    Returns:
        Parsed documents list
    """
    import json

    return json.loads(documents_json)


@st.cache_data(ttl=60)
def cache_search_results(query: str, document_id: int, results_json: str):
    """
    Cache search results using Streamlit's native caching.

    Args:
        query: Search query
        document_id: Document ID
        results_json: JSON string of results

    Returns:
        Parsed search results
    """
    import json

    return json.loads(results_json)


def clear_all_caches():
    """Clear all Streamlit and custom caches."""
    # Clear Streamlit's cache
    st.cache_data.clear()

    # Clear custom cache
    CacheManager.invalidate()

    st.success("All caches cleared!")


def show_cache_stats():
    """Display cache statistics in the UI."""
    if "cache" not in st.session_state:
        st.info("No cache data available")
        return

    cache = st.session_state.cache
    now = datetime.now()

    total_entries = len(cache)
    expired_entries = sum(1 for entry in cache.values() if now > entry["expiry"])
    active_entries = total_entries - expired_entries

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Entries", total_entries)
    with col2:
        st.metric("Active Entries", active_entries)
    with col3:
        st.metric("Expired Entries", expired_entries)

    if st.button("🧹 Clean Up Expired"):
        CacheManager.cleanup_expired()
        st.rerun()

    if st.button("🗑️ Clear All Cache"):
        clear_all_caches()
        st.rerun()
