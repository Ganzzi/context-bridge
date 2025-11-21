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
