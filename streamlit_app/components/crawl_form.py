"""
Crawl form component for initiating document crawling.
"""

import streamlit as st
import asyncio
from context_bridge import ContextBridge
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.ui_helpers import (
    show_error,
    show_success,
    show_info,
    handle_error,
    validate_input,
)
from utils.caching import CacheManager


def render_crawl_form(bridge: ContextBridge):
    """Render form for crawling new documentation with enhanced error handling."""
    st.subheader("🚀 Crawl New Documentation")

    show_info(
        "Enter the details below to crawl and add new documentation to your library. "
        "The crawler will follow internal links up to the specified depth from each URL. "
        "Fragment duplicates (e.g., #section-name) are automatically filtered."
    )

    # Initialize crawl result in session state if not exists
    if "crawl_result" not in st.session_state:
        st.session_state.crawl_result = None

    with st.form("crawl_form"):
        name = st.text_input(
            "Document Name*",
            placeholder="e.g., psqlpy",
            help="A unique name for this documentation",
        )
        version = st.text_input(
            "Version*", placeholder="e.g., 0.9.0", help="Version number of the documentation"
        )
        url = st.text_input(
            "Source URL*",
            placeholder="https://example.com/docs",
            help="Starting URL for the crawler",
        )
        description = st.text_area(
            "Description (optional)",
            placeholder="Brief description of this documentation...",
            help="Optional description to help identify this documentation",
        )
        additional_urls_text = st.text_area(
            "Additional URLs (optional)",
            placeholder="https://example.com/api-docs\nhttps://example.com/tutorials\nOne URL per line",
            help="Additional starting URLs to crawl. Each URL will be crawled with the specified max depth, following internal links. Fragment duplicates are automatically filtered.",
            height=100,
        )
        max_depth = st.slider(
            "Max Crawl Depth",
            min_value=1,
            max_value=10,
            value=3,
            help="Maximum depth to follow links (1 = only the start page, 2 = one level deep, etc.)",
        )

        submitted = st.form_submit_button("🚀 Start Crawling", type="primary")

        if submitted:
            # Validate all inputs
            errors = []

            is_valid, error_msg = validate_input(
                name, "Document Name", required=True, min_length=2, max_length=100
            )
            if not is_valid:
                errors.append(error_msg)

            is_valid, error_msg = validate_input(
                version, "Version", required=True, min_length=1, max_length=50
            )
            if not is_valid:
                errors.append(error_msg)

            is_valid, error_msg = validate_input(url, "Source URL", required=True, min_length=10)
            if not is_valid:
                errors.append(error_msg)
            elif not url.startswith(("http://", "https://")):
                errors.append("URL must start with http:// or https://")

            # Validate additional URLs
            additional_urls = []
            if additional_urls_text.strip():
                url_lines = [
                    line.strip() for line in additional_urls_text.split("\n") if line.strip()
                ]
                for i, url_line in enumerate(url_lines, 1):
                    if not url_line.startswith(("http://", "https://")):
                        errors.append(f"Additional URL {i} must start with http:// or https://")
                    else:
                        additional_urls.append(url_line)

            # Show all validation errors
            if errors:
                for error in errors:
                    show_error(error)
                return

            # Start crawling process
            try:
                with st.spinner("Crawling documentation... This may take a few minutes."):
                    # Create progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    status_text.text("🔍 Initializing crawler...")

                    # Run crawling in asyncio event loop
                    # Use WindowsProactorEventLoopPolicy for Windows to support subprocesses
                    if sys.platform == "win32":
                        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # Update progress
                    progress_bar.progress(25)
                    status_text.text("🌐 Starting crawl process...")

                    try:
                        # Perform the crawl
                        result = loop.run_until_complete(
                            bridge.crawl_documentation(
                                name=name.strip(),
                                version=version.strip(),
                                source_url=url.strip(),
                                description=description.strip() if description else None,
                                max_depth=max_depth,
                                additional_urls=additional_urls if additional_urls else None,
                            )
                        )

                        progress_bar.progress(100)
                        status_text.text("✅ Crawl completed!")

                        # Invalidate documents cache
                        CacheManager.invalidate(prefix="documents")

                        # Store result in session state for button access
                        st.session_state.crawl_result = result

                        # Display results
                        show_success("Crawling completed successfully!")

                        with st.expander("📊 Crawl Results", expanded=True):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Document ID", result.document_id)
                            with col2:
                                st.metric("Pages Crawled", result.pages_crawled)
                            with col3:
                                st.metric("Pages Stored", result.pages_stored)
                            with col4:
                                st.metric("Duplicates Skipped", result.duplicates_skipped)

                            if result.errors > 0:
                                st.warning(f"⚠️ {result.errors} errors occurred during crawling")

                            show_info(
                                f"Document '{result.document_name} v{result.document_version}' has been added to your library."
                            )
                        
                        # Automatically trigger chunking to create initial group
                        if result.pages_stored > 0:
                            status_text.text("⚙️ Processing pages and creating group...")
                            
                            # Get all pages for the document
                            pages = loop.run_until_complete(
                                bridge.list_pages(result.document_id, limit=1000)
                            )
                            page_ids = [p.id for p in pages]
                            
                            if page_ids:
                                # Trigger chunking
                                chunk_result = loop.run_until_complete(
                                    bridge.process_chunking(
                                        document_id=result.document_id,
                                        page_ids=page_ids,
                                        run_async=False # Run synchronously to ensure group is created before user navigates
                                    )
                                )
                                status_text.text("✅ Processing complete! Group created.")
                                show_success(f"Processed {chunk_result.pages_processed} pages into chunks.")
                            else:
                                status_text.text("⚠️ No pages to process.")
                        else:
                            status_text.text("⚠️ No pages stored, skipping processing.")

                    finally:
                        loop.close()

            except ConnectionError as e:
                handle_error(e, "Network Connection", show_details=True)
                show_info("Please check your internet connection and try again.")

            except ValueError as e:
                handle_error(e, "Invalid Input", show_details=True)
                show_info("Please verify your inputs and try again.")

            except TimeoutError as e:
                handle_error(e, "Crawl Timeout", show_details=True)
                show_info(
                    "The crawl took too long. Try reducing the max depth or checking the URL."
                )

            except Exception as e:
                handle_error(e, "Crawling Process", show_details=True)
                show_info(
                    "Please check your URL and try again. Make sure the website allows crawling and is accessible."
                )

    # Display view button outside the form if we have a successful crawl result
    if st.session_state.crawl_result:
        if st.button(
            "👀 View Pages", key=f"view_crawled_{st.session_state.crawl_result.document_id}"
        ):
            st.session_state.selected_document = st.session_state.crawl_result.document_id
            st.switch_page("pages/crawled_pages.py")
