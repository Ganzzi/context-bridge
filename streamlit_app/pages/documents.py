"""
Document management page for Context Bridge Streamlit app.
"""

import asyncio
import logging
import streamlit as st
import pandas as pd
from typing import List, Optional
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from utils.session_state import SessionState
from utils.async_utils import run_async
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
from components.tag_selector import render_tag_selector_multiselect

logger = logging.getLogger(__name__)

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

    # Tag filtering
    st.markdown("**Filter by Tags** (optional)")
    try:
        tags = run_async(SessionState.get_bridge().list_tags())
        selected_tag_ids = render_tag_selector_multiselect(
            tags,
            key="documents_page_tags",
            placeholder="Select tags to filter documents...",
            disabled=False,
        )
    except Exception as e:
        logger.error(f"Failed to load tags: {e}")
        selected_tag_ids = []
        st.warning("Could not load tags for filtering")

    # Pagination controls
    col4, col5 = st.columns([1, 3])
    with col4:
        page_size = st.selectbox("Items per page", [10, 25, 50, 100], index=1)
    with col5:
        page = st.number_input("Page", min_value=1, value=1, step=1)

    # Handle search state
    if st.button("🔍 Search", type="primary"):
        st.session_state.search_performed = True
        # Reset pagination when searching
        page = 1
        
    # Document Detail View - Check this FIRST
    if st.session_state.get("selected_document"):
        doc_id = st.session_state.selected_document
        
        # Back button
        if st.button("← Back to Documents", key="back_to_docs"):
            del st.session_state.selected_document
            st.rerun()
            
        try:
            # Load document details
            repo = DocumentRepository(bridge._db_manager)
            doc = run_async(repo.get_by_id(doc_id))
            
            if doc:
                st.header(f"{doc.name} v{doc.version}")
                
                # Metadata columns
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Created", doc.created_at.strftime("%Y-%m-%d") if doc.created_at else "N/A")
                with m2:
                    st.metric("Status", "Active") # Placeholder for status if needed
                with m3:
                    st.empty()
                with m4:
                    st.empty()
                
                if doc.description:
                    st.info(doc.description)
                    
                st.markdown(f"**Source URL:** [{doc.source_url}]({doc.source_url})" if doc.source_url else "**Source URL:** N/A")
                
                st.divider()
                
                # Tag Management Section
                st.subheader("🏷️ Tags")
                
                # Load current tags
                current_tags = run_async(bridge.get_document_tags(doc.id))
                
                # Display current tags with remove buttons
                if current_tags:
                    st.write("Current Tags:")
                    # Use columns for a grid-like layout
                    cols = st.columns(4)
                    for i, tag in enumerate(current_tags):
                        with cols[i % 4]:
                            # Container for tag + delete button
                            with st.container(border=True):
                                st.caption(f"**{tag.name}**")
                                if st.button("🗑️", key=f"rm_tag_{tag.id}", help=f"Remove {tag.name}"):
                                    # Remove tag action
                                    async def remove_tag_action():
                                        from context_bridge.database.repositories.tag_repository import TagRepository
                                        async with bridge._db_manager.connection() as conn:
                                            tag_repo = TagRepository(bridge._db_manager) # TagRepo takes db_manager
                                            return await tag_repo.remove_tag_from_document(doc.id, tag.id)
                                    
                                    if run_async(remove_tag_action()):
                                        st.success(f"Removed tag '{tag.name}'")
                                        st.rerun()
                                    else:
                                        st.error("Failed to remove tag")
                else:
                    st.info("No tags assigned to this document.")
                
                st.divider()
                
                # Add new tags
                st.subheader("Add Tags")
                
                all_tags = run_async(bridge.list_tags())
                current_tag_ids = [t.id for t in current_tags]
                available_tags = [t for t in all_tags if t.id not in current_tag_ids]
                
                if available_tags:
                    tag_options = {t.name: t.id for t in available_tags}
                    selected_tags_to_add = st.multiselect(
                        "Select tags to add",
                        options=list(tag_options.keys()),
                        key="add_tags_multiselect"
                    )
                    
                    if selected_tags_to_add:
                        if st.button("Add Selected Tags", type="primary"):
                            tags_to_add_ids = [tag_options[name] for name in selected_tags_to_add]
                            
                            async def add_tags_action():
                                from context_bridge.database.repositories.tag_repository import TagRepository
                                async with bridge._db_manager.connection() as conn:
                                    tag_repo = TagRepository(bridge._db_manager)
                                    return await tag_repo.add_tags_to_document(doc.id, tags_to_add_ids)
                            
                            added_count = run_async(add_tags_action())
                            if added_count > 0:
                                st.success(f"Added {added_count} tags!")
                                st.rerun()
                            else:
                                st.error("Failed to add tags.")
                else:
                    st.caption("All available tags are already assigned.")
                    
            else:
                st.error("Document not found.")
                if st.button("Go Back"):
                    del st.session_state.selected_document
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error loading document details: {e}")
            logger.error(f"Error detail view: {e}")

    # List View (only if no document selected)
    elif st.session_state.get("search_performed", False):
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
                    offset = (page - 1) * page_size
                    documents = run_async(
                        bridge.find_documents(
                            name=name_filter if name_filter else None,
                            version=version_filter if version_filter else None,
                            offset=offset,
                            limit=page_size,
                        )
                    )

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
            # Display documents as cards with tag information
            for doc in documents:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(f"### {doc.name} (v{doc.version})")
                        if doc.description:
                            st.markdown(f"_{doc.description}_")

                        # Display tags for this document
                        try:
                            doc_tags = run_async(
                                SessionState.get_bridge().get_document_tags(doc.id)
                            )
                            if doc_tags:
                                from components.tag_selector import render_tag_badges

                                st.markdown("**Tags:**")
                                render_tag_badges(doc_tags)
                        except Exception as e:
                            logger.debug(f"Could not load tags for document {doc.id}: {e}")

                        # Additional metadata
                        col_meta1, col_meta2 = st.columns(2)
                        with col_meta1:
                            st.caption(
                                f"🔗 {doc.source_url[:30]}..." if doc.source_url else "No URL"
                            )
                        with col_meta2:
                             st.caption(f"Created: {doc.created_at.strftime('%Y-%m-%d')}")

                    with col2:
                        # Action buttons
                        if st.button("👁️ View", key=f"view_{doc.id}", use_container_width=True):
                            st.session_state.selected_document = doc.id
                            st.rerun()

                        if st.button(
                            "🗑️ Delete",
                            key=f"delete_{doc.id}",
                            type="secondary",
                            use_container_width=True,
                        ):
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
                                success = run_async(
                                    SessionState.get_bridge().delete_document(doc.id)
                                )

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



with tab2:
    # Crawl form
    from components.crawl_form import render_crawl_form

    render_crawl_form(bridge)
