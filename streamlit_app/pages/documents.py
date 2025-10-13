"""
Document management page for Context Bridge Streamlit app.
"""

import streamlit as st
import pandas as pd
from typing import List, Optional
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from utils.session_state import SessionState
from utils.ui_helpers import (
    show_error,
    show_success,
    show_info,
    handle_error,
    show_retry_button,
    validate_input,
    show_connection_status,
)
from utils.caching import CacheManager, cached_function

st.title("📚 Document Management")

# Get bridge instance
bridge = SessionState.get_bridge()

# Show connection status in sidebar
try:
    is_connected = bridge and bridge._db_manager is not None
    show_connection_status(is_connected)
except Exception:
    show_connection_status(False)

tab1, tab2 = st.tabs(["All Documents", "Crawl New"])

with tab1:
    st.subheader("Document Library")

    # Search and filter controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("Search documents", placeholder="Enter document name...")
    with col2:
        name_filter = st.text_input("Filter by name", placeholder="Exact name")
    with col3:
        version_filter = st.text_input("Filter by version", placeholder="e.g., 1.0.0")

    # Pagination controls
    col4, col5 = st.columns([1, 3])
    with col4:
        page_size = st.selectbox("Items per page", [10, 25, 50, 100], index=1)
    with col5:
        page = st.number_input("Page", min_value=1, value=1, step=1)

    # Fetch documents
    if st.button("🔍 Search", type="primary"):
        # Generate cache key
        cache_key = CacheManager.get_cache_key(
            "documents",
            name=name_filter,
            version=version_filter,
            page=page,
            page_size=page_size,
        )

        # Try to get from cache
        documents = CacheManager.get(cache_key)

        if documents is None:
            try:
                with st.spinner("Loading documents..."):
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    offset = (page - 1) * page_size
                    documents = loop.run_until_complete(
                        bridge.find_documents(
                            name=name_filter if name_filter else None,
                            version=version_filter if version_filter else None,
                            offset=offset,
                            limit=page_size,
                        )
                    )
                    loop.close()

                    # Cache the results for 5 minutes
                    CacheManager.set(cache_key, documents, ttl_seconds=300)

            except ConnectionError as e:
                handle_error(e, "Database Connection", show_details=True)
                show_retry_button("Search", lambda: st.rerun())
                documents = []
            except Exception as e:
                handle_error(e, "Document Loading", show_details=True)
                documents = []
        else:
            st.caption("📦 Loaded from cache")

        if documents:
            # Convert to DataFrame for display
            df_data = []
            for doc in documents:
                df_data.append(
                    {
                        "ID": doc.id,
                        "Name": doc.name,
                        "Version": doc.version,
                        "Description": doc.description or "",
                        "Source URL": doc.source_url or "",
                        "Created": doc.created_at.strftime("%Y-%m-%d %H:%M"),
                        "Updated": doc.updated_at.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            df = pd.DataFrame(df_data)

            # Display DataFrame
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", width="small"),
                    "Name": st.column_config.TextColumn("Name", width="medium"),
                    "Version": st.column_config.TextColumn("Version", width="small"),
                    "Description": st.column_config.TextColumn("Description", width="large"),
                    "Source URL": st.column_config.LinkColumn("Source URL", width="medium"),
                    "Created": st.column_config.DatetimeColumn("Created", width="medium"),
                    "Updated": st.column_config.DatetimeColumn("Updated", width="medium"),
                },
            )

            # Action buttons for each document
            st.subheader("Actions")
            cols = st.columns(min(len(documents), 4))
            for i, doc in enumerate(documents):
                with cols[i % 4]:
                    if st.button(f"View {doc.name} v{doc.version}", key=f"view_{doc.id}"):
                        st.session_state.selected_document = doc.id
                        st.rerun()

                    if st.button(f"Delete {doc.name}", key=f"delete_{doc.id}", type="secondary"):
                        # Show delete confirmation
                        st.session_state[f"confirm_delete_{doc.id}"] = True
                        st.rerun()

            # Handle delete confirmations
            for doc in documents:
                if st.session_state.get(f"confirm_delete_{doc.id}", False):
                    st.warning(
                        f"Are you sure you want to delete '{doc.name} v{doc.version}'? This will permanently remove the document and all associated pages and chunks."
                    )

                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("✅ Yes, Delete", key=f"confirm_yes_{doc.id}", type="primary"):
                            try:
                                import asyncio

                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                success = loop.run_until_complete(bridge.delete_document(doc.id))
                                loop.close()

                                if success:
                                    show_success(
                                        f"Document '{doc.name} v{doc.version}' deleted successfully!"
                                    )
                                    # Clear confirmation state
                                    del st.session_state[f"confirm_delete_{doc.id}"]
                                    # Invalidate cache
                                    CacheManager.invalidate(prefix="documents")
                                    # Refresh the list
                                    st.session_state.documents_loaded = False
                                    st.rerun()
                                else:
                                    show_error("Failed to delete document.")

                            except Exception as e:
                                handle_error(e, "Document Deletion", show_details=True)

                    with col_cancel:
                        if st.button("❌ Cancel", key=f"confirm_no_{doc.id}"):
                            # Clear confirmation state
                            del st.session_state[f"confirm_delete_{doc.id}"]
                            st.rerun()

        else:
            show_info("No documents found matching your criteria.")

    else:
        show_info("Click 'Search' to load documents.")

    # Document Detail View
    if st.session_state.get("selected_document"):
        doc_id = st.session_state.selected_document

        st.divider()
        st.subheader("📄 Document Details")

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Get document details
            doc_repo = DocumentRepository(bridge._db_manager)
            document = loop.run_until_complete(doc_repo.get_by_id(doc_id))

            if document:
                # Document metadata
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**Name:** {document.name}")
                    st.markdown(f"**Version:** {document.version}")
                    if document.description:
                        st.markdown(f"**Description:** {document.description}")
                    if document.source_url:
                        st.markdown(
                            f"**Source URL:** [{document.source_url}]({document.source_url})"
                        )

                with col2:
                    st.markdown(f"**Created:** {document.created_at.strftime('%Y-%m-%d %H:%M')}")
                    st.markdown(f"**Updated:** {document.updated_at.strftime('%Y-%m-%d %H:%M')}")
                    st.markdown(f"**Document ID:** {document.id}")

                # Quick actions
                st.subheader("Quick Actions")
                action_col1, action_col2, action_col3, action_col4 = st.columns(4)

                with action_col1:
                    if st.button("📄 View Pages", key=f"view_pages_{doc_id}"):
                        st.switch_page("pages/crawled_pages.py")

                with action_col2:
                    if st.button("🔍 Search Content", key=f"search_{doc_id}"):
                        st.switch_page("pages/search.py")

                with action_col3:
                    if st.button(
                        "🗑️ Delete Document", key=f"delete_detail_{doc_id}", type="secondary"
                    ):
                        st.session_state[f"confirm_delete_detail_{doc_id}"] = True
                        st.rerun()

                with action_col4:
                    if st.button("❌ Close Details", key=f"close_detail_{doc_id}"):
                        del st.session_state.selected_document
                        st.rerun()

                # Delete confirmation for detail view
                if st.session_state.get(f"confirm_delete_detail_{doc_id}", False):
                    st.warning(
                        f"Are you sure you want to delete '{document.name} v{document.version}'? This will permanently remove the document and all associated pages and chunks."
                    )

                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button(
                            "✅ Yes, Delete", key=f"confirm_detail_yes_{doc_id}", type="primary"
                        ):
                            try:
                                success = loop.run_until_complete(bridge.delete_document(doc_id))
                                if success:
                                    st.success(
                                        f"Document '{document.name} v{document.version}' deleted successfully!"
                                    )
                                    del st.session_state.selected_document
                                    del st.session_state[f"confirm_delete_detail_{doc_id}"]
                                    st.session_state.documents_loaded = False
                                    st.rerun()
                                else:
                                    st.error("Failed to delete document.")
                            except Exception as e:
                                st.error(f"Error deleting document: {str(e)}")

                    with col_cancel:
                        if st.button("❌ Cancel", key=f"confirm_detail_no_{doc_id}"):
                            del st.session_state[f"confirm_delete_detail_{doc_id}"]
                            st.rerun()

                # TODO: Add page/chunk counts and recent pages list
                # For now, we'll show placeholder
                st.info("Page and chunk statistics will be displayed here in a future update.")

            else:
                st.error("Document not found.")
                if st.button("Clear Selection"):
                    del st.session_state.selected_document
                    st.rerun()

            loop.close()

        except Exception as e:
            st.error(f"Error loading document details: {str(e)}")
            if st.button("Clear Selection"):
                del st.session_state.selected_document
                st.rerun()

with tab2:
    # Crawl form
    from components.crawl_form import render_crawl_form

    render_crawl_form(bridge)
