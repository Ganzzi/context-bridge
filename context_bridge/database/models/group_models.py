"""
Group models for database representation and Pydantic validation.

Groups represent collections of pages that are processed together for chunking
and optional context generation. Each group tracks processing status and metadata.
"""

from enum import Enum
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """
    Processing status for a group.

    Tracks the lifecycle of a group from creation through completion or failure.
    """

    PENDING = "pending"  # Created but not yet processed
    PROCESSING = "processing"  # Currently being processed (chunking/embedding)
    COMPLETED = "completed"  # Successfully processed
    FAILED = "failed"  # Processing failed
    REPROCESSING = "reprocessing"  # Being reprocessed with new context generation


class Group(BaseModel):
    """
    Complete Group model for database representation.

    Represents a collection of pages that are processed together, with tracking
    for processing status, context generation, and metadata.

    Attributes:
        id: Unique identifier (UUID)
        document_id: Reference to parent document
        name: Optional human-readable name
        description: Optional description of the group
        context_enabled: Whether context generation was applied
        context_model: Model used for context generation (if enabled)
        combined_content_length: Total length of combined page content
        total_pages: Number of pages in this group
        total_chunks: Number of chunks generated from pages
        created_at: When the group was created
        processed_at: When processing completed (or None if pending)
        processing_status: Current processing status
        metadata: Additional metadata as JSONB
    """

    id: UUID
    document_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    context_enabled: bool = False
    context_model: Optional[str] = None
    combined_content_length: Optional[int] = None
    total_pages: int = 0
    total_chunks: int = 0
    created_at: datetime
    processed_at: Optional[datetime] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
        use_enum_values = False


class GroupCreate(BaseModel):
    """
    Model for creating a new group.

    Used for input validation when creating groups via API or UI.

    Attributes:
        document_id: Reference to parent document (required)
        name: Optional human-readable name
        description: Optional description
        context_enabled: Whether to enable context generation
        context_model: Model to use for context generation (if enabled)
    """

    document_id: int
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    context_enabled: bool = False
    context_model: Optional[str] = Field(None, max_length=255)

    class Config:
        use_enum_values = False


class GroupUpdate(BaseModel):
    """
    Model for updating an existing group.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Updated name (optional)
        description: Updated description (optional)
        context_enabled: Updated context generation flag (optional)
        context_model: Updated model for context generation (optional)
        processing_status: Updated processing status (optional)
        processed_at: Updated processing completion time (optional)
        total_pages: Updated page count (optional)
        total_chunks: Updated chunk count (optional)
        combined_content_length: Updated combined content length (optional)
        metadata: Updated metadata (optional)
    """

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    context_enabled: Optional[bool] = None
    context_model: Optional[str] = Field(None, max_length=255)
    processing_status: Optional[ProcessingStatus] = None
    processed_at: Optional[datetime] = None
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    combined_content_length: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = False


class GroupWithStats(Group):
    """
    Group model extended with calculated statistics.

    Includes additional computed fields like average chunk size,
    processing duration, etc.
    """

    avg_chunk_size: Optional[float] = None
    processing_duration_seconds: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
        use_enum_values = False


class GroupStatistics(BaseModel):
    """
    Statistics about a group's contents and processing.

    Provides aggregate information about a group's pages and chunks.
    """

    group_id: UUID
    total_pages: int = 0
    total_chunks: int = 0
    total_content_bytes: int = 0
    avg_page_size: float = 0.0
    avg_chunk_size: float = 0.0
    page_ids: list[int] = Field(default_factory=list)
    processing_duration_seconds: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None


class GroupProcessingResult(BaseModel):
    """
    Result of processing a group.

    Returned after completing group processing operations (chunking, embedding, etc.).
    """

    group_id: UUID
    success: bool
    message: str
    pages_processed: int = 0
    chunks_created: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GroupInfo(BaseModel):
    """
    Group information returned by list_groups() and list_reprocessable_groups().

    Provides a summary of group metadata and processing status for display
    in UI lists and API responses.

    Attributes:
        id: UUID of the group (as string for JSON serialization)
        document_id: Reference to parent document
        name: Optional human-readable name
        description: Optional description
        context_enabled: Whether context generation was applied
        context_model: Model used for context generation (if enabled)
        total_pages: Number of pages in this group
        total_chunks: Number of chunks generated
        processing_status: Current status (pending, processing, completed, failed, reprocessing)
        created_at: ISO format timestamp of creation
        processed_at: ISO format timestamp of completion (None if not processed)
    """

    id: str  # UUID as string for JSON serialization
    document_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    context_enabled: bool = False
    context_model: Optional[str] = None
    total_pages: int = 0
    total_chunks: int = 0
    processing_status: str
    created_at: str  # ISO format timestamp
    processed_at: Optional[str] = None  # ISO format timestamp

    class Config:
        from_attributes = True

    @classmethod
    def from_group(cls, group: "Group") -> "GroupInfo":
        """Create GroupInfo from a Group model."""
        return cls(
            id=str(group.id),
            document_id=group.document_id,
            name=group.name,
            description=group.description,
            context_enabled=group.context_enabled,
            context_model=group.context_model,
            total_pages=group.total_pages,
            total_chunks=group.total_chunks,
            processing_status=(
                group.processing_status.value
                if isinstance(group.processing_status, ProcessingStatus)
                else group.processing_status
            ),
            created_at=group.created_at.isoformat(),
            processed_at=group.processed_at.isoformat() if group.processed_at else None,
        )


class GroupStats(BaseModel):
    """
    Detailed statistics for a specific group.

    Returned by get_group_stats() with comprehensive information about
    group processing status, content size, and chunk breakdown.

    Attributes:
        group_id: UUID of the group (as string)
        document_id: Reference to parent document
        name: Optional human-readable name
        description: Optional description
        status: Current processing status
        context_enabled: Whether context generation was applied
        context_model: Model used for context generation
        total_pages: Number of pages in group
        total_chunks: Number of chunks generated
        chunks_by_status: Breakdown of chunks by status (e.g., {"completed": 10, "pending": 0})
        total_content_size: Total characters across all chunks
        created_at: ISO format timestamp of creation
        processed_at: ISO format timestamp of completion (None if not processed)
    """

    group_id: str  # UUID as string
    document_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    status: str
    context_enabled: bool = False
    context_model: Optional[str] = None
    total_pages: int = 0
    total_chunks: int = 0
    chunks_by_status: Dict[str, int] = Field(default_factory=dict)
    total_content_size: int = 0
    created_at: str  # ISO format timestamp
    processed_at: Optional[str] = None  # ISO format timestamp

    class Config:
        from_attributes = True


class GroupCreationResult(BaseModel):
    """
    Result of create_group() operation.

    Returned immediately when group processing is initiated. Since processing
    runs asynchronously, this indicates that the group has been created and
    queued for processing.

    Attributes:
        group_id: UUID of the created group (as string)
        document_id: Reference to parent document
        status: Always "processing" for async operations
        pages_selected: Number of pages included in the group
        estimated_chunks: Estimated number of chunks (based on content size)
        context_enabled: Whether context generation is enabled
        context_model: Model to use for context generation (if enabled)
    """

    group_id: str  # UUID as string
    document_id: int
    status: str = "processing"
    pages_selected: int = 0
    estimated_chunks: int = 0
    context_enabled: bool = False
    context_model: Optional[str] = None

    class Config:
        from_attributes = True


class ReprocessingResult(BaseModel):
    """
    Result of reprocess_group() operation.

    Contains details about the reprocessing outcome including counts of
    deleted and created chunks, and any errors encountered.

    Attributes:
        status: Overall status ("success", "failed", or "partial")
        group_id: UUID of the reprocessed group (as string)
        chunks_deleted: Number of chunks deleted before reprocessing
        chunks_created: Number of new chunks created
        contexts_generated: Number of context strings generated (if context enabled)
        context_enabled: Whether context generation was used
        context_model: Model used for context generation (if any)
        errors: Number of errors encountered during processing
        error_messages: List of error messages (if any)
    """

    status: str  # "success", "failed", or "partial"
    group_id: str  # UUID as string
    chunks_deleted: int = 0
    chunks_created: int = 0
    contexts_generated: int = 0
    context_enabled: bool = False
    context_model: Optional[str] = None
    errors: int = 0
    error_messages: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True
