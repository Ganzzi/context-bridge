"""
Crawled pages management page for Context Bridge Streamlit app.
"""

import streamlit as st
import pandas as pd
from typing import List, Optional
from context_bridge.database.repositories.document_repository import DocumentRepository, Document
from utils.session_state import SessionState

st.title("📄 Page Management")

# Get bridge instance
bridge = SessionState.get_bridge()

# Initialize session state for pages
if "selected_document_pages" not in st.session_state:
    st.session_state.selected_document_pages = None
if "pages_list" not in st.session_state:
    st.session_state.pages_list = []
if "pages_loaded" not in st.session_state:
    st.session_state.pages_loaded = False
if "selected_pages" not in st.session_state:
    st.session_state.selected_pages = []

# Document selector
st.subheader("Select Document")

# Get available documents for dropdown
try:
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    documents = loop.run_until_complete(bridge.list_documents(limit=100))
    loop.close()

    if documents:
        doc_options = ["Select a document..."] + [
            f"{doc.name} v{doc.version} (ID: {doc.id})" for doc in documents
        ]
        doc_ids = [None] + [doc.id for doc in documents]

        selected_idx = st.selectbox(
            "Choose a document to view its pages:",
            range(len(doc_options)),
            format_func=lambda x: doc_options[x],
            key="document_selector",
        )

        selected_doc_id = doc_ids[selected_idx] if selected_idx > 0 else None

        if selected_doc_id != st.session_state.selected_document_pages:
            # Document changed, reset pages
            st.session_state.selected_document_pages = selected_doc_id
            st.session_state.pages_loaded = False
            st.session_state.selected_pages = []
            st.rerun()

    else:
        st.warning("No documents available. Please crawl some documentation first.")
        selected_doc_id = None

except Exception as e:
    st.error(f"Error loading documents: {str(e)}")
    selected_doc_id = None

# Only show page management if a document is selected
if selected_doc_id:
    st.divider()

    # Page filters and controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        status_filter = st.selectbox(
            "Status Filter", ["all", "pending", "processing", "chunked", "deleted"], index=0
        )

    with col2:
        page_size = st.selectbox("Items per page", [10, 25, 50, 100], index=1)

    with col3:
        page_num = st.number_input("Page", min_value=1, value=1, step=1)

    with col4:
        if st.button("🔄 Refresh", key="refresh_pages"):
            st.session_state.pages_loaded = False
            st.rerun()

    # Load pages
    if (
        st.button("📄 Load Pages", type="primary", key="load_pages_initial")
        or st.session_state.pages_loaded
    ):
        if not st.session_state.pages_loaded or st.button(
            "📄 Load Pages", type="primary", key="load_pages_rerun"
        ):
            try:
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                offset = (page_num - 1) * page_size
                status_param = None if status_filter == "all" else status_filter

                pages = loop.run_until_complete(
                    bridge.list_pages(
                        document_id=selected_doc_id,
                        status=status_param,
                        offset=offset,
                        limit=page_size,
                    )
                )
                loop.close()

                st.session_state.pages_list = pages
                st.session_state.pages_loaded = True

            except Exception as e:
                st.error(f"Error loading pages: {str(e)}")
                st.session_state.pages_list = []
                st.session_state.pages_loaded = False

        # Display pages if loaded
        if st.session_state.pages_loaded and st.session_state.pages_list:
            pages = st.session_state.pages_list

            # Convert to DataFrame for display
            df_data = []
            for page in pages:
                df_data.append(
                    {
                        "ID": page.id,
                        "URL": page.url,
                        "Size (chars)": page.content_length,
                        "Status": page.status,
                        "Crawled": page.crawled_at.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            df = pd.DataFrame(df_data)

            # Selection controls
            st.subheader("📋 Page Selection for Chunking")

            # Select All / Clear All buttons
            col_select1, col_select2, col_select3 = st.columns([1, 1, 3])

            with col_select1:
                if st.button("✅ Select All", key="select_all_pages", use_container_width=True):
                    st.session_state.selected_pages = [page.id for page in pages]
                    st.rerun()

            with col_select2:
                if st.button("❌ Clear All", key="clear_all_pages", use_container_width=True):
                    st.session_state.selected_pages = []
                    st.rerun()

            with col_select3:
                selected_count = len(st.session_state.selected_pages)
                total_size = sum(
                    page.content_length
                    for page in pages
                    if page.id in st.session_state.selected_pages
                )
                st.metric("Selected", f"{selected_count} pages", f"{total_size:,} chars")

            # Individual page selection with improved layout
            st.write("**Select pages to process:**")

            # Sort pages by URL for better organization
            sorted_pages = sorted(pages, key=lambda p: p.url)

            # Display pages in a single column with better formatting
            for page in sorted_pages:
                is_selected = page.id in st.session_state.selected_pages

                # Create a container for each page
                with st.container():
                    col_check, col_info = st.columns([0.5, 9.5])

                    with col_check:
                        # Checkbox for selection
                        selected = st.checkbox(
                            "Select",
                            value=is_selected,
                            key=f"page_{page.id}",
                            label_visibility="collapsed",
                        )

                        # Update selection state
                        if selected and page.id not in st.session_state.selected_pages:
                            st.session_state.selected_pages.append(page.id)
                        elif not selected and page.id in st.session_state.selected_pages:
                            st.session_state.selected_pages.remove(page.id)

                    with col_info:
                        # Display page info with full URL visible
                        status_emoji = {
                            "pending": "⏳",
                            "processing": "⚙️",
                            "chunked": "✅",
                            "deleted": "🗑️",
                        }.get(page.status, "❓")

                        st.markdown(
                            f"{status_emoji} **ID {page.id}**: [{page.url}]({page.url})  \n"
                            f"📊 Size: {page.content_length:,} chars | "
                            f"📅 Crawled: {page.crawled_at.strftime('%Y-%m-%d %H:%M')}"
                        )

                    st.divider()

            # Chunk Processing Section
            if st.session_state.selected_pages:
                st.divider()
                st.subheader("⚙️ Process Selected Pages")

                # Selected pages summary - sorted by URL
                selected_pages_info = [
                    page for page in pages if page.id in st.session_state.selected_pages
                ]
                # Sort by URL to ensure logical order (root first, then alphabetically)
                selected_pages_info.sort(key=lambda p: p.url)

                total_chars = sum(page.content_length for page in selected_pages_info)

                with st.expander("📊 Selected Pages Summary", expanded=True):
                    st.write(f"**Selected:** {len(selected_pages_info)} pages")
                    st.write(f"**Total content:** {total_chars:,} characters")

                    # Show selected page URLs in sorted order
                    st.write("**Pages to process (in order):**")
                    for page in selected_pages_info:
                        st.write(f"- {page.url} ({page.content_length:,} chars)")

                # Chunk size configuration
                col_chunk1, col_chunk2 = st.columns([1, 2])

                with col_chunk1:
                    chunk_size = st.number_input(
                        "Chunk Size (characters)",
                        min_value=100,
                        max_value=3000,
                        value=2000,
                        step=100,
                        help="Maximum characters per chunk",
                    )

                with col_chunk2:
                    if st.button("🚀 Start Chunking Process", type="primary", key="start_chunking"):
                        # Validate selection
                        if not st.session_state.selected_pages:
                            st.error("No pages selected for processing.")
                        elif len(st.session_state.selected_pages) > 50:
                            st.error("Too many pages selected. Please select 50 or fewer pages.")
                        else:
                            # Start processing
                            try:
                                with st.spinner(
                                    "Processing pages into chunks... This may take a few minutes."
                                ):
                                    # Create progress bar
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()

                                    status_text.text("Initializing chunking process...")

                                    # Run processing in asyncio event loop
                                    import asyncio

                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                    # Update progress
                                    progress_bar.progress(10)
                                    status_text.text("Validating pages...")

                                    # Process the pages synchronously
                                    progress_bar.progress(20)
                                    status_text.text("Processing pages into chunks...")

                                    result = loop.run_until_complete(
                                        bridge.process_pages(
                                            document_id=selected_doc_id,
                                            page_ids=st.session_state.selected_pages,
                                            chunk_size=chunk_size,
                                            run_async=False,  # Run synchronously for Streamlit
                                        )
                                    )
                                    loop.close()

                                    progress_bar.progress(100)
                                    status_text.text("Chunking process completed!")

                                    # Display results
                                    st.success("✅ Chunking process completed successfully!")

                                    with st.expander("📊 Processing Results", expanded=True):
                                        col_res1, col_res2 = st.columns(2)
                                        with col_res1:
                                            st.metric("Pages Processed", result.pages_processed)
                                        with col_res2:
                                            st.metric("Document ID", result.document_id)

                                        # Get chunk statistics
                                        try:
                                            stats_loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(stats_loop)
                                            stats = stats_loop.run_until_complete(
                                                bridge.get_chunk_stats(selected_doc_id)
                                            )
                                            stats_loop.close()
                                            st.metric("Chunks Created", stats["total_chunks"])
                                            st.write("Page Status Summary:")
                                            for status, count in stats[
                                                "page_status_counts"
                                            ].items():
                                                st.write(f"- {status}: {count} pages")
                                        except Exception as stats_error:
                                            st.warning(
                                                f"Could not retrieve chunk statistics: {stats_error}"
                                            )

                                        st.info(
                                            "🎉 Chunking completed! You can now search through the processed content."
                                        )

                                        # Clear selection after successful processing
                                        if st.button(
                                            "Clear Selection", key="clear_after_processing"
                                        ):
                                            st.session_state.selected_pages = []
                                            st.session_state.pages_loaded = (
                                                False  # Refresh to show updated status
                                            )
                                            st.rerun()

                            except Exception as e:
                                st.error(f"❌ Processing failed: {str(e)}")
                                st.info("Please check your selection and try again.")

            else:
                st.info("Select pages above to enable chunk processing.")

            # Page Details View
            st.divider()
            st.subheader("🔍 Page Details")

            # Page selector for details
            page_options = ["Select a page to view details..."] + [
                f"Page {page.id}: {page.url[:50]}..." for page in pages
            ]
            page_ids = [None] + [page.id for page in pages]

            selected_page_idx = st.selectbox(
                "Choose a page to view details:",
                range(len(page_options)),
                format_func=lambda x: page_options[x],
                key="page_details_selector",
            )

            selected_page_id = page_ids[selected_page_idx] if selected_page_idx > 0 else None

            if selected_page_id:
                selected_page = next((page for page in pages if page.id == selected_page_id), None)

                if selected_page:
                    # Page metadata
                    col_detail1, col_detail2 = st.columns([2, 1])

                    with col_detail1:
                        st.markdown(f"**URL:** {selected_page.url}")
                        st.markdown(f"**Status:** {selected_page.status}")
                        st.markdown(
                            f"**Crawled:** {selected_page.crawled_at.strftime('%Y-%m-%d %H:%M:%S')}"
                        )

                    with col_detail2:
                        st.markdown(f"**Page ID:** {selected_page.id}")
                        st.markdown(
                            f"**Content Length:** {selected_page.content_length:,} characters"
                        )

                    # Action buttons
                    action_col1, action_col2, action_col3 = st.columns(3)

                    with action_col1:
                        if st.button("👁️ View Full Content", key=f"view_content_{selected_page_id}"):
                            st.session_state[f"show_content_{selected_page_id}"] = True
                            st.rerun()

                    with action_col2:
                        if st.button(
                            "🗑️ Delete Page", key=f"delete_page_{selected_page_id}", type="secondary"
                        ):
                            st.session_state[f"confirm_delete_page_{selected_page_id}"] = True
                            st.rerun()

                    with action_col3:
                        if st.button("🔄 Refresh Status", key=f"refresh_page_{selected_page_id}"):
                            st.session_state.pages_loaded = False
                            st.rerun()

                    # Content preview
                    if st.session_state.get(f"show_content_{selected_page_id}", False):
                        st.subheader("📄 Content Preview")

                        # Get full page content (we'll need to fetch it from the database)
                        try:
                            import asyncio

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                            # Get full page from repository
                            page_repo = bridge._doc_manager.page_repo
                            full_page = loop.run_until_complete(
                                page_repo.get_by_id(selected_page_id)
                            )
                            loop.close()

                            if full_page:
                                # Show content preview (first 2000 characters)
                                content_preview = full_page.content[:2000]
                                st.text_area(
                                    "Content Preview (first 2000 characters)",
                                    value=content_preview,
                                    height=300,
                                    disabled=True,
                                    key=f"content_preview_{selected_page_id}",
                                )

                                if len(full_page.content) > 2000:
                                    st.info(
                                        f"Content truncated. Full content: {len(full_page.content):,} characters."
                                    )

                                # Hide content button
                                if st.button(
                                    "Hide Content", key=f"hide_content_{selected_page_id}"
                                ):
                                    del st.session_state[f"show_content_{selected_page_id}"]
                                    st.rerun()
                            else:
                                st.error("Could not load page content.")

                        except Exception as e:
                            st.error(f"Error loading page content: {str(e)}")

                    # Delete confirmation
                    if st.session_state.get(f"confirm_delete_page_{selected_page_id}", False):
                        st.warning(
                            f"Are you sure you want to delete this page? This action cannot be undone."
                        )

                        col_confirm_page, col_cancel_page = st.columns(2)
                        with col_confirm_page:
                            if st.button(
                                "✅ Yes, Delete Page",
                                key=f"confirm_delete_yes_{selected_page_id}",
                                type="primary",
                            ):
                                try:
                                    import asyncio

                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    success = loop.run_until_complete(
                                        bridge.delete_page(selected_page_id)
                                    )
                                    loop.close()

                                    if success:
                                        st.success("Page deleted successfully!")
                                        del st.session_state[
                                            f"confirm_delete_page_{selected_page_id}"
                                        ]
                                        st.session_state.pages_loaded = False  # Refresh list
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete page.")

                                except Exception as e:
                                    st.error(f"Error deleting page: {str(e)}")

                        with col_cancel_page:
                            if st.button("❌ Cancel", key=f"confirm_delete_no_{selected_page_id}"):
                                del st.session_state[f"confirm_delete_page_{selected_page_id}"]
                                st.rerun()

                    # TODO: Add chunk display for processed pages
                    if selected_page.status == "chunked":
                        st.info(
                            "Chunk display for processed pages will be implemented in a future update."
                        )

        elif st.session_state.pages_loaded:
            st.info("No pages found matching your criteria.")
        else:
            st.info("Click 'Load Pages' to view pages for this document.")

else:
    st.info("Please select a document above to view its pages.")
