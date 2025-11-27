"""
Tag Management Page

Provides interface for viewing, creating, and managing tags.
"""

import logging
import asyncio
import nest_asyncio
from streamlit_app.utils.async_utils import run_async

import streamlit as st

from context_bridge import ContextBridge
from context_bridge.database.models.tag_models import TagCategory
from streamlit_app.utils.session_state import SessionState
from streamlit_app.components.tag_selector import (
    render_tag_badges,
    render_tag_statistics,
    render_tag_creation_form,
    render_tag_category_selector,
)

logger = logging.getLogger(__name__)

# Allow nested event loops for Streamlit
nest_asyncio.apply()

# Page configuration
st.set_page_config(
    page_title="Tags Management",
    page_icon="🏷️",
    layout="wide",
)

st.title("🏷️ Tags Management")
st.markdown("View, create, and manage document tags for better organization and filtering.")


async def load_tags():
    """Load all tags from database."""
    try:
        bridge = SessionState.get_bridge()
        tags = await bridge.list_tags()
        return tags
    except Exception as e:
        logger.error(f"Failed to load tags: {e}")
        st.error(f"Failed to load tags: {e}")
        return []


async def load_tag_statistics():
    """Load tag usage statistics."""
    try:
        bridge = SessionState.get_bridge()
        tags = await bridge.list_tags()

        # Get stats for each tag
        stats = {}
        for tag in tags:
            count = await bridge.tag_repo.count_documents_by_tag(tag.id)
            stats[tag.id] = count

        return stats
    except Exception as e:
        logger.error(f"Failed to load tag statistics: {e}")
        return {}


async def create_new_tag(name: str, category: TagCategory, description: str | None):
    """Create a new tag."""
    try:
        bridge = SessionState.get_bridge()
        tag = await bridge.create_tag(name, category, description)
        st.success(f"✅ Tag '{tag.name}' created successfully!")
        st.rerun()
    except ValueError as e:
        st.error(f"❌ Error: {e}")
    except Exception as e:
        logger.error(f"Failed to create tag: {e}")
        st.error(f"Failed to create tag: {e}")


# Initialize session state
if "show_create_form" not in st.session_state:
    st.session_state.show_create_form = False

# Create tabs
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🏷️ All Tags", "➕ Create Tag"])

# Tab 1: Overview
with tab1:
    st.markdown("## Tag System Overview")

    # Load tags and statistics
    tags = run_async(load_tags())
    tag_stats = run_async(load_tag_statistics())

    if tags:
        # Display statistics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Tags", len(tags))

        with col2:
            total_usage = sum(tag_stats.values())
            st.metric("Total Assignments", total_usage)

        with col3:
            if tags:
                avg_usage = sum(tag_stats.values()) / len(tags)
                st.metric("Average Usage", f"{avg_usage:.1f}")

        with col4:
            # Most used tag
            if tag_stats:
                most_used_id = max(tag_stats, key=tag_stats.get)
                most_used_tag = next(t for t in tags if t.id == most_used_id)
                st.metric("Most Used", most_used_tag.name)

        # Categories breakdown
        st.markdown("### Categories Breakdown")

        categories = {}
        for tag in tags:
            cat = tag.category.value
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tag)

        cols = st.columns(len(categories))
        for col, (cat, cat_tags) in zip(cols, sorted(categories.items())):
            with col:
                st.metric(
                    cat.replace("_", " ").title(),
                    len(cat_tags),
                    help=", ".join([t.name for t in cat_tags[:3]])
                    + (f"... +{len(cat_tags)-3} more" if len(cat_tags) > 3 else ""),
                )

        # Display full statistics table
        st.markdown("### Detailed Statistics")
        render_tag_statistics(tags, tag_stats)

    else:
        st.info("📭 No tags available yet. Create some tags to get started!")


# Tab 2: All Tags
with tab2:
    st.markdown("## All Tags")

    tags = run_async(load_tags())

    if tags:
        # Category filter
        selected_category = render_tag_category_selector(key="tags_page_category_filter")

        # Filter tags by category if selected
        filtered_tags = tags
        if selected_category:
            filtered_tags = [t for t in tags if t.category == selected_category]

        st.markdown(f"### Showing {len(filtered_tags)} tag(s)")

        # Display tags in a grid
        for i, tag in enumerate(sorted(filtered_tags, key=lambda t: t.name)):
            if i % 3 == 0:
                cols = st.columns(3)

            col = cols[i % 3]

            with col:
                with st.container(border=True):
                    # Tag header
                    st.markdown(f"**🏷️ {tag.name}**")

                    # Category badge
                    st.caption(f"Category: `{tag.category.value}`")

                    # Description
                    if tag.description:
                        st.markdown(f"_{tag.description}_")
                    else:
                        st.caption("_No description_")

                    # Metadata
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"ID: {tag.id}")
                    with col2:
                        st.caption(f"Created: {tag.created_at.strftime('%Y-%m-%d')}")

    else:
        st.info("📭 No tags available yet. Create some tags in the 'Create Tag' tab.")


# Tab 3: Create Tag
with tab3:
    st.markdown("## Create a New Tag")
    st.markdown("Add a new tag to the system for document categorization.")

    # Get available categories
    categories = list(TagCategory)

    # Render creation form
    tag_data = render_tag_creation_form(categories, key_prefix="tags_page")

    if tag_data:
        # Create the tag
        run_async(create_new_tag(tag_data["name"], tag_data["category"], tag_data["description"]))

    # Display predefined tags as reference
    st.markdown("### 📚 Reference: Predefined Tags")

    from context_bridge.database.models.tag_models import PREDEFINED_TAGS

    # Group by category
    tags_by_cat = {}
    for category, tag_list in PREDEFINED_TAGS.items():
        tags_by_cat[category] = tag_list

    # Display categories
    for category in sorted(tags_by_cat.keys()):
        with st.expander(f"📁 {category.replace('_', ' ').title()}", expanded=False):
           for tag_name, description in tags_by_cat[category]:
                st.caption(f"**{tag_name}** — {description}")


# Footer
st.divider()
st.markdown(
    """
### 💡 Tips

- **Organize Documents**: Assign tags to documents for better categorization
- **Filter Search**: Use tags to narrow down search results  
- **Reuse Tags**: Tags are reusable across multiple documents
- **Categories**: Tags are organized by category for easy browsing

For more information, see the [Tags System Guide](../docs/guides/tags_system_guide.md).
"""
)
