"""
Session state management for Context Bridge Streamlit app.
"""

import streamlit as st
import asyncio
from context_bridge import ContextBridge


class SessionState:
    """Manages Streamlit session state."""

    @staticmethod
    def init():
        """Initialize session state variables."""
        if "bridge" not in st.session_state:
            st.session_state.bridge = None
        if "selected_document" not in st.session_state:
            st.session_state.selected_document = None
        if "selected_pages" not in st.session_state:
            st.session_state.selected_pages = []
        if "cache" not in st.session_state:
            st.session_state.cache = {}

    @staticmethod
    def get_bridge() -> ContextBridge:
        """
        Get or create ContextBridge instance (synchronous wrapper).

        Returns:
            ContextBridge instance (initialized)
        """
        # Check if bridge exists and is initialized
        if "bridge" not in st.session_state or st.session_state.bridge is None:
            # Create and initialize bridge synchronously
            bridge = ContextBridge()

            # Run async initialization in event loop
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(bridge.initialize())
                loop.close()
            except Exception as e:
                st.error(f"Failed to initialize Context Bridge: {str(e)}")
                raise

            st.session_state.bridge = bridge

        return st.session_state.bridge
