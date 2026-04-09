"""
Group management and monitoring page for Context Bridge Streamlit app.

This page allows users to:
- View all groups for a document
- Monitor group processing status
- View group statistics (pages, chunks, processing time)
- Re-process groups with context generation (Phase 3)
- Delete groups
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from utils.session_state import SessionState

st.title("📊 Group Management & Monitoring")

# Get bridge instance
bridge = SessionState.get_bridge()

# Initialize session state
if "selected_document_groups" not in st.session_state:
    st.session_state.selected_document_groups = None
if "groups_list" not in st.session_state:
    st.session_state.groups_list = []
if "groups_loaded" not in st.session_state:
    st.session_state.groups_loaded = False
if "selected_group_id" not in st.session_state:
    st.session_state.selected_group_id = None

# Document selector
st.subheader("📄 Select Document")

# Get available documents
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
            "Choose a document to view its groups:",
            range(len(doc_options)),
            format_func=lambda x: doc_options[x],
            key="document_selector_groups",
        )

        selected_doc_id = doc_ids[selected_idx] if selected_idx > 0 else None

        if selected_doc_id != st.session_state.selected_document_groups:
            st.session_state.selected_document_groups = selected_doc_id
            st.session_state.groups_loaded = False
            st.session_state.selected_group_id = None
            st.rerun()

    else:
        st.warning("No documents available. Please crawl some documentation first.")
        selected_doc_id = None

except Exception as e:
    st.error(f"Error loading documents: {str(e)}")
    selected_doc_id = None

# Display groups if document is selected
if selected_doc_id:
    st.divider()

    # Load Groups Section
    col_load1, col_load2, col_load3 = st.columns([2, 1, 1])

    with col_load1:
        st.subheader("📋 Groups Overview")

    with col_load2:
        if st.button("🔄 Refresh Groups", key="refresh_groups"):
            st.session_state.groups_loaded = False
            st.rerun()

    with col_load3:
        sort_option = st.selectbox(
            "Sort by",
            ["Created (newest)", "Created (oldest)", "Status", "Pages"],
            key="sort_groups",
        )

    # Load groups button
    if (
        st.button("📊 Load Groups", type="primary", key="load_groups_initial")
        or st.session_state.groups_loaded
    ):
        if not st.session_state.groups_loaded:
            try:
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                groups = loop.run_until_complete(bridge.list_groups(document_id=selected_doc_id))
                loop.close()

                # Sort groups based on selection
                if sort_option == "Created (newest)":
                    groups = sorted(groups, key=lambda g: g.get("created_at", ""), reverse=True)
                elif sort_option == "Created (oldest)":
                    groups = sorted(groups, key=lambda g: g.get("created_at", ""))
                elif sort_option == "Status":
                    status_order = {"pending": 0, "processing": 1, "completed": 2, "failed": 3}
                    groups = sorted(
                        groups,
                        key=lambda g: status_order.get(g.get("processing_status", ""), 999),
                    )
                elif sort_option == "Pages":
                    groups = sorted(groups, key=lambda g: g.get("total_pages", 0), reverse=True)

                st.session_state.groups_list = groups
                st.session_state.groups_loaded = True

            except Exception as e:
                st.error(f"Error loading groups: {str(e)}")
                st.session_state.groups_list = []
                st.session_state.groups_loaded = False

    # Display groups table if loaded
    if st.session_state.groups_loaded:
        groups = st.session_state.groups_list

        if groups:
            st.success(f"✅ Loaded {len(groups)} group(s)")

            # Create DataFrame for display
            df_data = []
            for group in groups:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "⚙️",
                    "completed": "✅",
                    "failed": "❌",
                    "reprocessing": "🔄",
                }.get(group.get("processing_status", ""), "❓")

                context_badge = "🤖 AI" if group.get("context_enabled") else "📝"

                # Parse created_at date
                created_at = group.get("created_at", "")
                if isinstance(created_at, str):
                    try:
                        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        created_str = created_dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        created_str = created_at[:16]
                else:
                    created_str = str(created_at)[:16]

                df_data.append(
                    {
                        "Group ID": str(group.get("id", ""))[:8] + "...",
                        "Name": group.get("name", "Unnamed"),
                        "Status": f"{status_emoji} {group.get('processing_status', 'unknown')}",
                        "Context": context_badge,
                        "Pages": group.get("total_pages", 0),
                        "Chunks": group.get("total_chunks", 0),
                        "Created": created_str,
                        "Full ID": str(group.get("id", "")),
                    }
                )

            df = pd.DataFrame(df_data)

            # Display groups as interactive table
            st.dataframe(
                df[["Group ID", "Name", "Status", "Context", "Pages", "Chunks", "Created"]],
                use_container_width=True,
                hide_index=True,
            )

            # Group details section
            st.divider()
            st.subheader("🔍 Group Details")

            # Group selector
            group_options = ["Select a group..."] + [
                f"{group.get('name', 'Unnamed')} ({str(group.get('id', ''))[:8]}...)"
                for group in groups
            ]
            group_full_ids = [None] + [str(group.get("id", "")) for group in groups]

            selected_group_idx = st.selectbox(
                "Choose a group to view details:",
                range(len(group_options)),
                format_func=lambda x: group_options[x],
                key="group_details_selector",
            )

            selected_group_id = (
                group_full_ids[selected_group_idx] if selected_group_idx > 0 else None
            )

            if selected_group_id:
                selected_group = next(
                    (g for g in groups if str(g.get("id", "")) == selected_group_id), None
                )

                if selected_group:
                    # Display group information in columns
                    col_detail1, col_detail2 = st.columns([1, 1])

                    with col_detail1:
                        st.markdown("### Group Information")
                        st.markdown(f"**Name:** {selected_group.get('name', 'Unnamed')}")
                        st.markdown(f"**Description:** {selected_group.get('description', 'None')}")
                        st.markdown(f"**Group ID:** `{selected_group_id}`")
                        st.markdown(
                            f"**Status:** {selected_group.get('processing_status', 'unknown')}"
                        )

                    with col_detail2:
                        st.markdown("### Statistics")
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            st.metric("Pages", selected_group.get("total_pages", 0))
                            st.metric("Chunks", selected_group.get("total_chunks", 0))
                        with col_stat2:
                            context_status = (
                                "✅ Enabled"
                                if selected_group.get("context_enabled")
                                else "❌ Disabled"
                            )
                            st.metric("AI Context", context_status)
                            content_length = selected_group.get("combined_content_length", 0)
                            st.metric("Total Content", f"{content_length:,} chars")

                    # Timestamps
                    st.divider()
                    col_time1, col_time2 = st.columns(2)

                    with col_time1:
                        created_at = selected_group.get("created_at", "")
                        if isinstance(created_at, str):
                            try:
                                created_dt = datetime.fromisoformat(
                                    created_at.replace("Z", "+00:00")
                                )
                                st.write(f"**Created:** {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                            except:
                                st.write(f"**Created:** {created_at}")

                    with col_time2:
                        processed_at = selected_group.get("processed_at")
                        if processed_at:
                            if isinstance(processed_at, str):
                                try:
                                    processed_dt = datetime.fromisoformat(
                                        processed_at.replace("Z", "+00:00")
                                    )
                                    st.write(
                                        f"**Processed:** {processed_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                                    )
                                except:
                                    st.write(f"**Processed:** {processed_at}")
                        else:
                            st.write("**Processed:** Not yet completed")

                    # Action buttons
                    st.divider()
                    st.subheader("⚙️ Actions")

                    col_action1, col_action2, col_action3 = st.columns(3)

                    with col_action1:
                        if st.button("📄 View Pages", key=f"view_pages_{selected_group_id}"):
                            st.session_state[f"show_pages_{selected_group_id}"] = True
                            st.rerun()

                    with col_action2:
                        if st.button(
                            "🔄 Reprocess with Context",
                            key=f"reprocess_{selected_group_id}",
                            type="secondary",
                        ):
                            st.session_state[f"confirm_reprocess_{selected_group_id}"] = True
                            st.rerun()

                    with col_action3:
                        if st.button(
                            "🗑️ Delete Group",
                            key=f"delete_group_{selected_group_id}",
                            type="secondary",
                        ):
                            st.session_state[f"confirm_delete_group_{selected_group_id}"] = True
                            st.rerun()

                    # View Pages
                    if st.session_state.get(f"show_pages_{selected_group_id}", False):
                        st.subheader("📄 Pages in This Group")

                        try:
                            import asyncio

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                            # Get pages for this group - this would need a new method
                            # For now, we'll show a placeholder
                            st.info(
                                "Page listing for groups will be available once the integration is complete."
                            )

                            if st.button("Hide Pages", key=f"hide_pages_{selected_group_id}"):
                                del st.session_state[f"show_pages_{selected_group_id}"]
                                st.rerun()

                        except Exception as e:
                            st.error(f"Error loading pages: {str(e)}")

                    # Reprocess confirmation
                    if st.session_state.get(f"confirm_reprocess_{selected_group_id}", False):
                        st.warning(
                            "⚠️ Re-processing will regenerate chunks and embeddings. This may take a while."
                        )

                        col_reprocess1, col_reprocess2 = st.columns(2)

                        with col_reprocess1:
                            if st.button(
                                "✅ Yes, Reprocess",
                                key=f"confirm_reprocess_yes_{selected_group_id}",
                                type="primary",
                            ):
                                try:
                                    import asyncio

                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                    # Reprocess the group
                                    result = loop.run_until_complete(
                                        bridge._doc_manager.reprocess_group(
                                            group_id=UUID(selected_group_id),
                                            context_model=None,  # Use default model
                                        )
                                    )
                                    loop.close()

                                    st.success(f"✅ Group reprocessing started!")
                                    del st.session_state[f"confirm_reprocess_{selected_group_id}"]
                                    st.session_state.groups_loaded = False  # Refresh
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Error reprocessing group: {str(e)}")

                        with col_reprocess2:
                            if st.button(
                                "❌ Cancel",
                                key=f"confirm_reprocess_no_{selected_group_id}",
                            ):
                                del st.session_state[f"confirm_reprocess_{selected_group_id}"]
                                st.rerun()

                    # Delete confirmation
                    if st.session_state.get(f"confirm_delete_group_{selected_group_id}", False):
                        st.warning(
                            "⚠️ Deleting this group will remove all associated chunks. This cannot be undone."
                        )

                        col_delete1, col_delete2 = st.columns(2)

                        with col_delete1:
                            if st.button(
                                "✅ Yes, Delete Group",
                                key=f"confirm_delete_yes_{selected_group_id}",
                                type="primary",
                            ):
                                try:
                                    import asyncio

                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                    success = loop.run_until_complete(
                                        bridge._doc_manager.group_repo.delete_group(
                                            UUID(selected_group_id)
                                        )
                                    )
                                    loop.close()

                                    if success:
                                        st.success("✅ Group deleted successfully!")
                                        del st.session_state[
                                            f"confirm_delete_group_{selected_group_id}"
                                        ]
                                        st.session_state.groups_loaded = False  # Refresh
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete group.")

                                except Exception as e:
                                    st.error(f"Error deleting group: {str(e)}")

                        with col_delete2:
                            if st.button(
                                "❌ Cancel",
                                key=f"confirm_delete_no_{selected_group_id}",
                            ):
                                del st.session_state[f"confirm_delete_group_{selected_group_id}"]
                                st.rerun()

        else:
            st.info("No groups found for this document. Process some pages to create groups.")

else:
    st.info("Please select a document above to view its groups.")
