"""
Tag selector component for Streamlit UI.

Provides reusable UI components for selecting and displaying tags in various contexts.
"""

import logging
from typing import List, Optional, Dict, Set

import streamlit as st
from context_bridge.database.models.tag_models import Tag, TagCategory

logger = logging.getLogger(__name__)


def render_tag_badge(tag: Tag, key: Optional[str] = None) -> None:
    """
    Render a single tag as a colored badge.

    Args:
        tag: Tag object to display
        key: Optional key for Streamlit component
    """
    # Color mapping for tag categories
    category_colors = {
        TagCategory.DOCUMENTATION_TYPE: "#1f77b4",  # Blue
        TagCategory.TECHNOLOGY: "#ff7f0e",  # Orange
        TagCategory.DOMAIN: "#2ca02c",  # Green
        TagCategory.CUSTOM: "#d62728",  # Red
    }

    color = category_colors.get(tag.category, "#999999")

    # Render badge-style display
    with st.container(key=key):
        st.write(
            f'<span style="background-color: {color}; color: white; padding: 5px 10px; '
            f'border-radius: 15px; font-size: 12px; display: inline-block;">{tag.name}</span>',
            unsafe_allow_html=True,
        )


def render_tag_badges(tags: List[Tag]) -> None:
    """
    Render multiple tags as badges in a row.

    Args:
        tags: List of Tag objects to display
    """
    if not tags:
        st.caption("No tags assigned")
        return

    # Create columns for each tag
    if len(tags) <= 5:
        cols = st.columns(len(tags))
        for i, (col, tag) in enumerate(zip(cols, tags)):
            with col:
                render_tag_badge(tag, key=f"tag_badge_{tag.id}")
    else:
        # Wrap tags across multiple rows for more than 5 tags
        cols = st.columns(5)
        for i, tag in enumerate(tags):
            col_idx = i % 5
            with cols[col_idx]:
                render_tag_badge(tag, key=f"tag_badge_{tag.id}")


def render_tag_selector_multiselect(
    tags: List[Tag],
    selected_tag_ids: Optional[List[int]] = None,
    key: str = "tag_selector",
    placeholder: str = "Select tags...",
    disabled: bool = False,
) -> List[int]:
    """
    Render a multi-select widget for tag selection.

    Args:
        tags: List of available Tag objects
        selected_tag_ids: List of currently selected tag IDs
        key: Streamlit component key
        placeholder: Placeholder text for multiselect
        disabled: Whether the widget is disabled

    Returns:
        List of selected tag IDs
    """
    if not tags:
        st.warning("No tags available. Create some tags first.")
        return []

    # Create options dict: {tag_name: tag_id}
    tag_options = {f"{tag.name} ({tag.category.value})": tag.id for tag in tags}

    # Create reverse mapping for display
    id_to_name = {tag.id: f"{tag.name} ({tag.category.value})" for tag in tags}

    # Convert selected IDs to names for display
    selected_names = [
        id_to_name[tag_id] for tag_id in (selected_tag_ids or []) if tag_id in id_to_name
    ]

    # Render multiselect
    selected = st.multiselect(
        "Tags",
        options=list(tag_options.keys()),
        default=selected_names,
        placeholder=placeholder,
        key=key,
        disabled=disabled,
    )

    # Convert back to IDs
    selected_ids = [tag_options[name] for name in selected]

    return selected_ids


def render_tag_filter_sidebar(
    tags: List[Tag],
    key: str = "tag_filter_sidebar",
) -> List[int]:
    """
    Render a tag filter widget in the sidebar.

    Args:
        tags: List of available Tag objects
        key: Streamlit component key

    Returns:
        List of selected tag IDs for filtering
    """
    st.sidebar.markdown("### 🏷️ Filter by Tags")

    # Group tags by category
    tags_by_category = {}
    for tag in tags:
        category = tag.category.value
        if category not in tags_by_category:
            tags_by_category[category] = []
        tags_by_category[category].append(tag)

    selected_tag_ids = []

    # Render checkboxes grouped by category
    for category in sorted(tags_by_category.keys()):
        with st.sidebar:
            with st.expander(f"📁 {category.replace('_', ' ').title()}", expanded=False):
                for tag in sorted(tags_by_category[category], key=lambda t: t.name):
                    if st.checkbox(
                        tag.name,
                        key=f"{key}_tag_{tag.id}",
                        help=tag.description or "No description",
                    ):
                        selected_tag_ids.append(tag.id)

    return selected_tag_ids


def render_tag_filter_buttons(
    tags: List[Tag],
    key: str = "tag_filter_buttons",
) -> List[int]:
    """
    Render tag filters as clickable buttons.

    Args:
        tags: List of available Tag objects
        key: Streamlit component key

    Returns:
        List of selected tag IDs for filtering
    """
    st.markdown("### 🏷️ Quick Filters")

    selected_tag_ids = []

    # Group tags by category
    tags_by_category = {}
    for tag in tags:
        category = tag.category.value
        if category not in tags_by_category:
            tags_by_category[category] = []
        tags_by_category[category].append(tag)

    # Render buttons grouped by category
    for category in sorted(tags_by_category.keys()):
        st.subheader(category.replace("_", " ").title(), divider="gray")

        cols = st.columns(min(4, len(tags_by_category[category])))

        for i, tag in enumerate(sorted(tags_by_category[category], key=lambda t: t.name)):
            col_idx = i % len(cols)
            with cols[col_idx]:
                if st.button(
                    f"🏷️ {tag.name}",
                    key=f"{key}_button_{tag.id}",
                    use_container_width=True,
                ):
                    selected_tag_ids.append(tag.id)

    return selected_tag_ids


def render_tag_statistics(tags: List[Tag], tag_stats: Dict[int, int]) -> None:
    """
    Render tag statistics and usage information.

    Args:
        tags: List of Tag objects
        tag_stats: Dictionary mapping tag_id to usage count
    """
    st.markdown("### 📊 Tag Statistics")

    if not tags:
        st.info("No tags available yet.")
        return

    # Create data for display
    stats_data = []
    for tag in sorted(tags, key=lambda t: tag_stats.get(t.id, 0), reverse=True):
        count = tag_stats.get(tag.id, 0)
        stats_data.append(
            {
                "Name": tag.name,
                "Category": tag.category.value,
                "Documents": count,
                "Description": tag.description or "—",
            }
        )

    # Display as table
    st.dataframe(
        stats_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name"),
            "Category": st.column_config.TextColumn("Category"),
            "Documents": st.column_config.NumberColumn("Documents Used"),
            "Description": st.column_config.TextColumn("Description"),
        },
    )

    # Display summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Tags", len(tags))

    with col2:
        total_usage = sum(tag_stats.values())
        st.metric("Total Tag Assignments", total_usage)

    with col3:
        if tags:
            avg_usage = sum(tag_stats.values()) / len(tags)
            st.metric("Avg Usage per Tag", f"{avg_usage:.1f}")


def render_tag_creation_form(
    categories: List[TagCategory], key_prefix: str = "tag_create"
) -> Optional[Dict]:
    """
    Render a form for creating a new tag.

    Args:
        categories: List of available TagCategory values
        key_prefix: Prefix for Streamlit component keys

    Returns:
        Dictionary with tag data if form submitted, None otherwise
    """
    st.markdown("### ➕ Create New Tag")

    with st.form(key=f"{key_prefix}_form"):
        name = st.text_input(
            "Tag Name", max_chars=50, placeholder="e.g., python-async", key=f"{key_prefix}_name"
        )

        category = st.selectbox(
            "Category",
            options=categories,
            format_func=lambda c: c.value.replace("_", " ").title(),
            key=f"{key_prefix}_category",
        )

        description = st.text_area(
            "Description (Optional)",
            max_chars=500,
            placeholder="Brief description of this tag...",
            key=f"{key_prefix}_description",
        )

        submitted = st.form_submit_button("Create Tag", use_container_width=True)

        if submitted:
            if not name or not name.strip():
                st.error("Tag name is required")
                return None

            return {
                "name": name.strip(),
                "category": category,
                "description": description.strip() if description else None,
            }

    return None


def render_tag_category_selector(key: str = "tag_category_filter") -> Optional[TagCategory]:
    """
    Render a dropdown for selecting a single tag category.

    Args:
        key: Streamlit component key

    Returns:
        Selected TagCategory or None
    """
    selected = st.selectbox(
        "Filter by Category",
        options=[None] + list(TagCategory),
        format_func=lambda c: "All Categories" if c is None else c.value.replace("_", " ").title(),
        key=key,
        index=0,
    )

    return selected
