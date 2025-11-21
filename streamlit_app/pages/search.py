"""
Search page for Context Bridge Streamlit app.
"""

import streamlit as st
import asyncio
import logging
from typing import List, Optional
from context_bridge.service.search_service import ContentSearchResult
from utils.session_state import SessionState
from components.search_results import render_search_results, render_search_stats
from components.tag_selector import render_tag_selector_multiselect

logger = logging.getLogger(__name__)

st.title("🔍 Search Documentation")

# Get bridge instance
bridge = SessionState.get_bridge()

# Search form
with st.form("search_form"):
    st.subheader("Search Parameters")

    # Query input
    query = st.text_input(
        "Search Query",
        placeholder="Enter your search query...",
        help="Search across all processed documentation content",
    )

    # Document filter
    col1, col2 = st.columns(2)
    with col1:
        # Get available documents for dropdown
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            documents = loop.run_until_complete(bridge.list_documents(limit=100))
            doc_options = ["All Documents"] + [
                f"{doc.name} v{doc.version} (ID: {doc.id})" for doc in documents
            ]
            selected_doc = st.selectbox(
                "Document Filter",
                options=doc_options,
                help="Search within a specific document or all documents",
            )
        except Exception as e:
            st.error(f"Failed to load documents: {e}")
            doc_options = ["All Documents"]
            selected_doc = "All Documents"

    with col2:
        limit = st.slider(
            "Max Results",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
            help="Maximum number of search results to return",
        )

        # Page size for results display
        results_page_size = st.selectbox(
            "Results per page",
            options=[5, 10, 20, 50],
            index=1,  # Default to 10
            help="Number of results to show per page",
        )

    # Advanced options (collapsible)
    with st.expander("Advanced Search Options"):
        col3, col4 = st.columns(2)
        with col3:
            vector_weight = st.slider(
                "Vector Weight",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1,
                help="Weight for semantic vector search (0 = BM25 only, 1 = vector only)",
            )
        with col4:
            bm25_weight = st.slider(
                "BM25 Weight",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1,
                help="Weight for keyword-based BM25 search (0 = vector only, 1 = BM25 only)",
            )

        # Tag filtering
        st.markdown("**Filter by Tags** (optional)")
        try:
            tags = asyncio.run(bridge.list_tags())
            selected_tag_ids = render_tag_selector_multiselect(
                tags,
                key="search_page_tags",
                placeholder="Select tags to narrow results...",
                disabled=False,
            )
        except Exception as e:
            logger.error(f"Failed to load tags: {e}")
            selected_tag_ids = []
            st.warning("Could not load tags for filtering")

    # Search button
    submitted = st.form_submit_button("🔍 Search", type="primary", use_container_width=True)

# Search history (optional feature)
search_history = st.session_state.get("search_history", [])
if search_history:
    with st.expander("Recent Searches", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("Click to reuse a recent query:")
            for i, past_query in enumerate(search_history[:5]):  # Show last 5
                if st.button(f"🔍 {past_query}", key=f"history_{i}"):
                    # Pre-fill the query (this would need form state management)
                    st.info(f"Recent query selected: {past_query}")
        with col2:
            if st.button("Clear History", key="clear_history"):
                st.session_state.search_history = []
                st.rerun()

# Search execution and results
if submitted and query.strip():
    if not query.strip():
        st.error("Please enter a search query")
    else:
        with st.spinner("Searching documentation..."):
            try:
                # Parse document selection
                document_id = None
                if selected_doc != "All Documents":
                    # Extract document ID from selection
                    import re

                    match = re.search(r"ID: (\d+)", selected_doc)
                    if match:
                        document_id = int(match.group(1))

                # Execute search
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                if document_id is None:
                    st.warning(
                        "Searching across all documents. For better results, consider selecting a specific document."
                    )
                    # For now, we'll need to search each document individually or modify the API
                    # Let's search the first document as an example
                    if documents:
                        document_id = documents[0].id
                        st.info(f"Searching in: {documents[0].name} v{documents[0].version}")
                    else:
                        st.error("No documents available for search")
                        st.stop()

                results = loop.run_until_complete(
                    bridge.search(
                        query=query.strip(),
                        document_id=document_id,
                        limit=limit,
                        vector_weight=vector_weight,
                        bm25_weight=bm25_weight,
                    )
                )

                # Store results in session state for display
                st.session_state.search_results = results
                st.session_state.last_query = query.strip()
                st.session_state.search_document_id = document_id
                st.session_state.results_page_size = results_page_size

                # Add to search history
                if "search_history" not in st.session_state:
                    st.session_state.search_history = []
                # Avoid duplicates and keep only last 10
                if query.strip() not in st.session_state.search_history:
                    st.session_state.search_history.insert(0, query.strip())
                    st.session_state.search_history = st.session_state.search_history[:10]

            except Exception as e:
                st.error(f"Search failed: {e}")
                st.session_state.search_results = []
else:
    # Clear previous results if no search submitted
    if "search_results" not in st.session_state:
        st.session_state.search_results = []

# Display results
if st.session_state.get("search_results"):
    results = st.session_state.search_results
    query = st.session_state.get("last_query", "")

    # Get document name for display
    document_name = None
    if "search_document_id" in st.session_state:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            doc = loop.run_until_complete(
                bridge.find_documents(id=st.session_state.search_document_id)
            )
            if doc:
                document_name = f"{doc[0].name} v{doc[0].version}"
        except:
            pass

    # Render search stats
    render_search_stats(results, query, document_name)

    st.divider()

    # Render search results
    page_size = st.session_state.get("results_page_size", 10)
    render_search_results(results, query, page_size=page_size)

elif submitted:
    st.info("No results found. Try adjusting your search query or search parameters.")

# Search tips
with st.expander("Search Tips"):
    st.markdown(
        """
    **Search Tips:**
    - Use specific keywords for better results
    - Try selecting a specific document for more targeted search
    - Adjust vector/BM25 weights based on your needs:
        - Higher vector weight (0.8-1.0): Better for semantic/conceptual searches
        - Higher BM25 weight (0.8-1.0): Better for exact keyword matches
    - Increase max results if you need more comprehensive results
    """
    )
