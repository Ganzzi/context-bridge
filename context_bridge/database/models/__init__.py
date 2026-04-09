"""
Database models module.
"""

from context_bridge.database.models.tag_models import (
    TagCategory,
    Tag,
    TagCreate,
    TagUpdate,
    DocumentTag,
    TagStatistics,
    DocumentWithTags,
    PREDEFINED_TAGS,
)

from context_bridge.database.models.group_models import (
    Group,
    GroupCreate,
    GroupUpdate,
    GroupWithStats,
    GroupStatistics,
    GroupProcessingResult,
    GroupInfo,
    GroupStats,
    GroupCreationResult,
    ReprocessingResult,
)

__all__ = [
    # Tag models
    "TagCategory",
    "Tag",
    "TagCreate",
    "TagUpdate",
    "DocumentTag",
    "TagStatistics",
    "DocumentWithTags",
    "PREDEFINED_TAGS",
    # Group models
    "Group",
    "GroupCreate",
    "GroupUpdate",
    "GroupWithStats",
    "GroupStatistics",
    "GroupProcessingResult",
    "GroupInfo",
    "GroupStats",
    "GroupCreationResult",
    "ReprocessingResult",
]
