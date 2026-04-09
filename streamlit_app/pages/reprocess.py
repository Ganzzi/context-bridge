"""
Re-processing page for Context Bridge Streamlit app.

This page allows users to:
- View groups that can be re-processed (no context yet)
- Select groups for re-processing with context generation
- Configure context generation settings
- Monitor re-processing progress
- Perform batch re-processing operations
"""

import streamlit as st
import pandas as pd
import asyncio
from typing import List, Optional
from uuid import UUID
from utils.session_state import SessionState

st.title("🔄 Re-process Groups with Context")

# Get bridge instance
bridge = SessionState.get_bridge()

# Initialize session state
if "reprocess_selected_doc" not in st.session_state:
    st.session_state.reprocess_selected_doc = None
if "reprocess_groups_list" not in st.session_state:
    st.session_state.reprocess_groups_list = []
if "reprocess_groups_loaded" not in st.session_state:
    st.session_state.reprocess_groups_loaded = False
if "reprocess_selected_groups" not in st.session_state:
    st.session_state.reprocess_selected_groups = []
if "reprocess_in_progress" not in st.session_state:
    st.session_state.reprocess_in_progress = False

st.markdown(
    """
This page helps you regenerate chunks for existing groups with AI-generated context.
Re-processing improves search results by adding contextual information to each chunk.
"""
)

# Document selector
st.subheader("📄 Select Document")

try:
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
            "Choose a document:",
            range(len(doc_options)),
            format_func=lambda x: doc_options[x],
            key="reprocess_document_selector",
        )

        selected_doc_id = doc_ids[selected_idx] if selected_idx > 0 else None

        if selected_doc_id != st.session_state.reprocess_selected_doc:
            st.session_state.reprocess_selected_doc = selected_doc_id
            st.session_state.reprocess_groups_loaded = False
            st.session_state.reprocess_selected_groups = []
            st.rerun()

    else:
        st.warning("No documents available. Please crawl some documentation first.")
        selected_doc_id = None

except Exception as e:
    st.error(f"Error loading documents: {str(e)}")
    selected_doc_id = None

# Display reprocessable groups if document is selected
if selected_doc_id:
    st.divider()

    # Load Groups Section
    col_load1, col_load2 = st.columns([3, 1])

    with col_load1:
        st.subheader("📋 Groups Eligible for Re-processing")

    with col_load2:
        if st.button("🔄 Refresh", key="refresh_reprocess_groups"):
            st.session_state.reprocess_groups_loaded = False
            st.rerun()

    # Load groups button
    if (
        st.button("📊 Load Reprocessable Groups", type="primary", key="load_reprocess_groups")
        or st.session_state.reprocess_groups_loaded
    ):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Get reprocessable groups
            groups = loop.run_until_complete(
                bridge.list_reprocessable_groups(document_id=selected_doc_id)
            )
            loop.close()

            st.session_state.reprocess_groups_list = groups
            st.session_state.reprocess_groups_loaded = True

            if not groups:
                st.info(
                    "✅ No groups need re-processing. All groups either have context enabled or haven't been processed yet."
                )
            else:
                st.success(f"✅ Found {len(groups)} group(s) eligible for re-processing")

        except Exception as e:
            st.error(f"Error loading groups: {str(e)}")

    # Display groups if loaded
    if st.session_state.reprocess_groups_loaded and st.session_state.reprocess_groups_list:
        st.subheader("Select Groups to Re-process")

        # Create a dataframe for display
        groups_data = []
        for group in st.session_state.reprocess_groups_list:
            groups_data.append(
                {
                    "ID": str(group["id"])[:8] + "...",
                    "Name": group.get("name") or "Unnamed",
                    "Pages": group.get("total_pages", 0),
                    "Current Chunks": group.get("total_chunks", 0),
                    "Status": group.get("processing_status", "Unknown"),
                    "Full ID": group["id"],
                }
            )

        groups_df = pd.DataFrame(groups_data)

        # Group selection
        st.write("**Select groups to re-process:**")
        selected_groups = st.multiselect(
            "Groups:",
            options=groups_df["Full ID"].tolist(),
            format_func=lambda x: next(
                (g["Name"] for g in groups_data if g["Full ID"] == x),
                str(x)[:8],
            ),
            key="reprocess_groups_multiselect",
        )

        if selected_groups:
            st.session_state.reprocess_selected_groups = selected_groups

            # Display selected groups info
            st.info(f"📌 {len(selected_groups)} group(s) selected for re-processing")

            # Show context generation settings
            st.divider()
            st.subheader("⚙️ Context Generation Settings")

            col1, col2 = st.columns(2)

            with col1:
                context_model = st.selectbox(
                    "Context Model:",
                    [
                        "anthropic:claude-3-5-sonnet-20241022",
                        "openai:gpt-4o",
                        "openai:gpt-4-turbo",
                    ],
                    index=0,
                    key="reprocess_context_model",
                )

            with col2:
                temperature = st.slider(
                    "Temperature:",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.3,
                    step=0.1,
                    key="reprocess_temperature",
                    help="Lower values = more deterministic, Higher values = more creative",
                )

            # Confirmation section
            st.divider()
            st.warning(
                f"⚠️ **Re-processing will delete {sum(g.get('total_chunks', 0) for g in [next(x for x in st.session_state.reprocess_groups_list if x['id'] == gid) for gid in selected_groups])} existing chunks and regenerate them with context.**"
            )

            col_confirm1, col_confirm2 = st.columns([1, 1])

            with col_confirm1:
                if st.button(
                    "✅ Confirm & Re-process",
                    type="primary",
                    key="confirm_reprocess",
                    use_container_width=True,
                ):
                    st.session_state.reprocess_in_progress = True

            with col_confirm2:
                if st.button(
                    "❌ Cancel",
                    key="cancel_reprocess",
                    use_container_width=True,
                ):
                    st.session_state.reprocess_selected_groups = []
                    st.rerun()

            # Execute re-processing if confirmed
            if st.session_state.reprocess_in_progress:
                progress_container = st.container()

                with progress_container:
                    st.subheader("⏳ Re-processing in Progress...")

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        if len(selected_groups) == 1:
                            # Single group
                            group_id = selected_groups[0]
                            status_text.write(f"Re-processing group {str(group_id)[:8]}...")
                            progress_bar.progress(50)

                            result = loop.run_until_complete(
                                bridge.reprocess_group_with_context(
                                    group_id=group_id,
                                    context_model=context_model,
                                )
                            )

                            progress_bar.progress(100)

                            if result.get("success"):
                                st.success(
                                    f"✅ Successfully re-processed group!\n\n"
                                    f"- Chunks created: {result.get('chunks_created', 0)}\n"
                                    f"- Status: {result.get('processing_status', 'Unknown')}"
                                )
                            else:
                                st.error(
                                    f"❌ Re-processing failed: {result.get('error', 'Unknown error')}"
                                )

                        else:
                            # Batch processing
                            status_text.write(f"Re-processing {len(selected_groups)} groups...")
                            result = loop.run_until_complete(
                                bridge.reprocess_multiple_groups_with_context(
                                    group_ids=selected_groups,
                                    context_model=context_model,
                                )
                            )

                            progress_bar.progress(100)

                            # Display results
                            st.subheader("📊 Batch Re-processing Results")

                            results_data = {
                                "Total Groups": result.get("total_groups", 0),
                                "Successful": result.get("successful", 0),
                                "Failed": result.get("failed", 0),
                            }

                            col_res1, col_res2, col_res3 = st.columns(3)
                            with col_res1:
                                st.metric("Total", results_data["Total Groups"])
                            with col_res2:
                                st.metric("Successful ✅", results_data["Successful"])
                            with col_res3:
                                st.metric("Failed ❌", results_data["Failed"])

                            # Show detailed results
                            if result.get("results"):
                                st.write("**Detailed Results:**")
                                for item_result in result["results"]:
                                    if item_result.get("success"):
                                        st.success(
                                            f"✅ Group {str(item_result['group_id'])[:8]}: "
                                            f"{item_result.get('chunks_created', 0)} chunks created"
                                        )
                                    else:
                                        st.error(
                                            f"❌ Group {str(item_result['group_id'])[:8]}: "
                                            f"{item_result.get('error', 'Unknown error')}"
                                        )

                        loop.close()

                    except Exception as e:
                        st.error(f"Error during re-processing: {str(e)}")

                    finally:
                        st.session_state.reprocess_in_progress = False
                        st.session_state.reprocess_selected_groups = []

else:
    st.info("👈 Select a document from above to view groups available for re-processing")
