"""
Document card component for displaying document information.
"""

import streamlit as st
from context_bridge.database.repositories.document_repository import Document


def render_document_card(document: Document):
    """Render a document info card."""
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.subheader(f"{document.name} v{document.version}")
            st.caption(document.description or "No description")
        with col2:
            st.metric("Pages", document.total_pages)
        with col3:
            st.metric("Chunks", document.total_chunks)
