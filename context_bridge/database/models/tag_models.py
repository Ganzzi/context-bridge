"""
Tag models and enums for document categorization.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TagCategory(str, Enum):
    """Tag categories for organization."""

    DOCUMENTATION_TYPE = "documentation_type"
    TECHNOLOGY = "technology"
    DOMAIN = "domain"
    CUSTOM = "custom"


class Tag(BaseModel):
    """Tag model representing a predefined category."""

    id: int = Field(..., description="Unique tag identifier")
    name: str = Field(
        ..., min_length=1, max_length=50, description="Tag name (lowercase, hyphenated)"
    )
    category: TagCategory = Field(..., description="Tag category")
    description: Optional[str] = Field(None, description="Tag description")
    created_at: datetime = Field(..., description="When tag was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "api-reference",
                "category": "documentation_type",
                "description": "API documentation and references",
                "created_at": "2025-11-15T10:00:00Z",
            }
        }


class TagCreate(BaseModel):
    """Model for creating a new tag."""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Tag name (lowercase, hyphenated)"
    )
    category: TagCategory = Field(..., description="Tag category")
    description: Optional[str] = Field(None, max_length=255, description="Tag description")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "api-reference",
                "category": "documentation_type",
                "description": "API documentation and references",
            }
        }


class TagUpdate(BaseModel):
    """Model for updating a tag."""

    description: Optional[str] = Field(None, max_length=255, description="Tag description")


class DocumentTag(BaseModel):
    """Document-Tag relationship model."""

    document_id: int = Field(..., description="Document ID")
    tag_id: int = Field(..., description="Tag ID")
    tag: Optional[Tag] = Field(None, description="Full tag object (optional)")
    created_at: datetime = Field(..., description="When tag was added to document")

    class Config:
        from_attributes = True


class TagStatistics(BaseModel):
    """Statistics for a tag."""

    tag_id: int = Field(..., description="Tag ID")
    name: str = Field(..., description="Tag name")
    category: TagCategory = Field(..., description="Tag category")
    usage_count: int = Field(..., ge=0, description="Number of documents using this tag")
    created_at: datetime = Field(..., description="When tag was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "tag_id": 1,
                "name": "api-reference",
                "category": "documentation_type",
                "usage_count": 42,
                "created_at": "2025-11-15T10:00:00Z",
            }
        }


class DocumentWithTags(BaseModel):
    """Document model with associated tags."""

    id: int = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    version: str = Field(..., description="Document version")
    source_url: Optional[str] = Field(None, description="Source URL")
    description: Optional[str] = Field(None, description="Document description")
    tags: List[Tag] = Field(default_factory=list, description="Associated tags")
    created_at: datetime = Field(..., description="When document was created")
    updated_at: datetime = Field(..., description="When document was last updated")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "PostgreSQL Guide",
                "version": "14.0",
                "source_url": "https://postgresql.org/docs",
                "description": "PostgreSQL documentation",
                "tags": [
                    {
                        "id": 1,
                        "name": "api-reference",
                        "category": "documentation_type",
                        "description": "API documentation",
                    }
                ],
                "created_at": "2025-11-15T10:00:00Z",
                "updated_at": "2025-11-15T10:00:00Z",
            }
        }


# Predefined tag definitions for initialization
PREDEFINED_TAGS = {
    "documentation_type": [
        ("technical-documentation", "General technical documentation"),
        ("api-reference", "API documentation and references"),
        ("user-guide", "User guides and tutorials"),
        ("developer-guide", "Developer-focused documentation"),
        ("wiki", "Wiki-style documentation"),
        ("specification", "Technical specifications (RFC, standards)"),
        ("whitepaper", "Technical whitepapers"),
        ("research-paper", "Academic/research papers"),
        ("blog-post", "Blog articles and posts"),
        ("article", "General articles"),
        ("faq", "Frequently Asked Questions"),
        ("changelog", "Version history and changelogs"),
        ("release-notes", "Software release notes"),
        ("tutorial", "Step-by-step tutorials"),
        ("case-study", "Case studies and examples"),
    ],
    "technology": [
        ("python", "Python programming language"),
        ("javascript", "JavaScript programming language"),
        ("typescript", "TypeScript programming language"),
        ("java", "Java programming language"),
        ("go", "Go programming language"),
        ("rust", "Rust programming language"),
        ("csharp", "C# programming language"),
        ("cpp", "C++ programming language"),
        ("sql", "SQL and database query language"),
        ("database", "Database documentation"),
        ("postgresql", "PostgreSQL database"),
        ("mongodb", "MongoDB database"),
        ("redis", "Redis in-memory data store"),
        ("web-framework", "Web framework documentation"),
        ("ml-ai", "Machine Learning / AI"),
        ("cloud", "Cloud platform documentation"),
        ("aws", "Amazon Web Services"),
        ("azure", "Microsoft Azure"),
        ("gcp", "Google Cloud Platform"),
        ("kubernetes", "Kubernetes container orchestration"),
        ("docker", "Docker containerization"),
        ("devops", "DevOps tools and practices"),
        ("cicd", "CI/CD and automation"),
    ],
    "domain": [
        ("backend", "Backend development"),
        ("frontend", "Frontend development"),
        ("fullstack", "Full-stack development"),
        ("infrastructure", "Infrastructure and systems"),
        ("security", "Security documentation"),
        ("testing", "Testing documentation"),
        ("monitoring", "Monitoring and observability"),
        ("performance", "Performance optimization"),
        ("scalability", "Scalability and architecture"),
        ("deployment", "Deployment and release"),
    ],
}
