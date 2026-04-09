"""
Search results component for Context Bridge Streamlit app.
"""

import streamlit as st
from typing import List
from context_bridge.service.search_service import ContentSearchResult


def render_search_results(results: List[ContentSearchResult], query: str = "", page_size: int = 10):
    """
    Render search results in an organized display with pagination.

    Args:
        results: List of ContentSearchResult objects
        query: Original search query for highlighting
        page_size: Number of results per page
    """
    if not results:
        st.info("No search results found.")
        return

    # Pagination logic
    total_results = len(results)
    total_pages = (total_results + page_size - 1) // page_size  # Ceiling division

    # Get current page from session state
    if "search_page" not in st.session_state:
        st.session_state.search_page = 1

    current_page = st.session_state.search_page

    # Ensure current page is valid
    if current_page > total_pages:
        current_page = total_pages
        st.session_state.search_page = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state.search_page = current_page

    # Pagination controls
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if st.button("⬅️ Previous", disabled=current_page <= 1, key="prev_page"):
                st.session_state.search_page = current_page - 1
                st.rerun()

        with col2:
            st.markdown(
                f"<center>Page {current_page} of {total_pages} ({total_results} total results)</center>",
                unsafe_allow_html=True,
            )

        with col3:
            if st.button("Next ➡️", disabled=current_page >= total_pages, key="next_page"):
                st.session_state.search_page = current_page + 1
                st.rerun()

    # Get results for current page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_results)
    page_results = results[start_idx:end_idx]

    st.success(f"Showing {len(page_results)} results (page {current_page} of {total_pages})")

    # Display results for current page
    for result in page_results:
        _render_single_result(result, query)


def _render_single_result(result: ContentSearchResult, query: str):
    """
    Render a single search result.

    Args:
        result: ContentSearchResult object
        query: Original search query for highlighting
    """
    # Create expander header with rank, document info, and score
    header = f"#{result.rank} - {result.document_name} v{result.document_version}"

    with st.expander(header, expanded=result.rank <= 3):  # Expand top 3 results
        # Score badge
        score_color = _get_score_color(result.score)
        st.markdown(
            f"<span style='color: {score_color}; font-weight: bold;'>Score: {result.score:.3f}</span>",
            unsafe_allow_html=True,
        )

        # Content with highlighting
        highlighted_content = _highlight_query_terms(result.chunk.content, query)
        st.markdown(highlighted_content)

        # Metadata row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            page_url = result.document_source_url or "N/A"
            if page_url != "N/A":
                st.caption(f"📄 **Source:** [{page_url}]({page_url})")
            else:
                st.caption("📄 **Source:** N/A")

        with col2:
            st.caption(f"🆔 **Chunk ID:** {result.chunk.id}")

        with col3:
            st.caption(f"📅 **Created:** {result.chunk.created_at.strftime('%Y-%m-%d')}")

        with col4:
            # View source button
            if st.button("🔗 View Source", key=f"view_source_{result.chunk.id}"):
                _view_source(result)


def _view_source(result: ContentSearchResult):
    """
    Open the document source URL in a new tab.

    Args:
        result: Search result containing document source URL
    """
    import streamlit as st

    source_url = result.document_source_url
    if source_url:
        st.markdown(
            f'<a href="{source_url}" target="_blank">🔗 Click here to view source</a>',
            unsafe_allow_html=True,
        )
        st.info(f"Source URL: {source_url}")
    else:
        st.warning("No source URL available for this document")


def _highlight_query_terms(content: str, query: str) -> str:
    """
    Highlight query terms in content.

    Args:
        content: Original content text
        query: Search query

    Returns:
        Content with query terms highlighted using markdown bold
    """
    if not query:
        return content

    highlighted = content
    query_terms = query.lower().split()

    for term in query_terms:
        if len(term) > 2:  # Only highlight terms longer than 2 characters
            # Highlight different cases
            for text_case in [term, term.upper(), term.capitalize()]:
                highlighted = highlighted.replace(text_case, f"**{text_case}**")

    return highlighted


def _get_score_color(score: float) -> str:
    """
    Get color for score display based on score value.

    Args:
        score: Relevance score

    Returns:
        Color name or hex code
    """
    if score >= 0.8:
        return "green"
    elif score >= 0.6:
        return "orange"
    else:
        return "red"


def _view_full_page(result: ContentSearchResult):
    """
    Handle viewing full page for a search result.

    Args:
        result: ContentSearchResult object
    """
    # For now, just show the page URL
    # In the future, this could open a page viewer or link to external content
    if result.chunk.page_url:
        st.info(f"Full page URL: {result.chunk.page_url}")
        # Could add: st.markdown(f"[Open Page]({result.chunk.page_url})")
    else:
        st.warning("No page URL available for this result")


def render_search_stats(results: List[ContentSearchResult], query: str, document_name: str = None):
    """
    Render search statistics and summary.

    Args:
        results: Search results
        query: Original query
        document_name: Name of document searched (optional)
    """
    if not results:
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Results Found", len(results))

    with col2:
        avg_score = sum(r.score for r in results) / len(results)
        st.metric("Average Score", f"{avg_score:.3f}")

    with col3:
        max_score = max(r.score for r in results)
        st.metric("Best Score", f"{max_score:.3f}")

    # Query and document info
    if document_name:
        st.caption(f"Searched in: **{document_name}**")
    st.caption(f"Query: **{query}**")
