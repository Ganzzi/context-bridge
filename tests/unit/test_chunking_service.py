"""Tests for the ChunkingService."""

import pytest
from context_bridge.service.chunking_service import ChunkingService


class TestChunkingService:
    """Test ChunkingService functionality."""

    @pytest.fixture
    def service(self):
        """Create a ChunkingService instance."""
        return ChunkingService(default_chunk_size=2000)

    @pytest.fixture
    def service_small_chunks(self):
        """Create a ChunkingService with small default chunks."""
        return ChunkingService(default_chunk_size=100)

    def test_init_default_chunk_size(self):
        """Test initialization with default chunk size."""
        service = ChunkingService()
        assert service.default_chunk_size == 2000

    def test_init_custom_chunk_size(self):
        """Test initialization with custom chunk size."""
        service = ChunkingService(default_chunk_size=500)
        assert service.default_chunk_size == 500

    def test_smart_chunk_markdown_empty_content(self, service):
        """Test chunking empty content."""
        chunks = service.smart_chunk_markdown("")
        assert chunks == []

    def test_smart_chunk_markdown_short_content(self, service):
        """Test chunking content shorter than chunk size."""
        content = "Short content"
        chunks = service.smart_chunk_markdown(content, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_smart_chunk_markdown_exact_chunk_size(self, service):
        """Test chunking content exactly matching chunk size."""
        content = "A" * 100
        chunks = service.smart_chunk_markdown(content, chunk_size=100)
        assert len(chunks) == 1
        assert len(chunks[0]) == 100

    def test_smart_chunk_markdown_no_boundaries(self, service):
        """Test chunking long content with no logical boundaries."""
        content = "A" * 500
        chunks = service.smart_chunk_markdown(content, chunk_size=200)
        assert len(chunks) == 3
        assert len(chunks[0]) == 200
        assert len(chunks[1]) == 200
        assert len(chunks[2]) == 100

    def test_smart_chunk_markdown_paragraph_breaks(self, service):
        """Test chunking splits at paragraph breaks."""
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = service.smart_chunk_markdown(content, chunk_size=20)
        # Should split at \n\n boundaries
        assert len(chunks) >= 2
        assert "First paragraph." in chunks[0]
        assert "Second paragraph." in chunks[1]

    def test_smart_chunk_markdown_sentence_breaks(self, service):
        """Test chunking splits at sentence breaks."""
        content = "First sentence. Second sentence. Third sentence."
        chunks = service.smart_chunk_markdown(content, chunk_size=25)
        # Should split at ". " boundaries
        assert len(chunks) >= 2
        assert "First sentence." in chunks[0]

    def test_smart_chunk_markdown_code_blocks_priority(self, service):
        """Test code blocks have highest priority for splitting."""
        content = """Some text before.

```python
def code():
    pass
```

More text after."""
        chunks = service.smart_chunk_markdown(content, chunk_size=30)
        # Should not split inside code block
        assert len(chunks) >= 2
        # Check that code block stays together
        code_found = False
        for chunk in chunks:
            if "```python" in chunk and "```" in chunk:
                code_found = True
                assert "def code():" in chunk
                assert "pass" in chunk
        assert code_found

    def test_smart_chunk_markdown_code_block_boundary(self, service):
        """Test splitting before code blocks."""
        content = "Text before code block.\n\n```python\ncode here\n```"
        chunks = service.smart_chunk_markdown(content, chunk_size=25)
        assert len(chunks) >= 2
        # First chunk should end before code block
        assert "Text before code block." in chunks[0]
        assert "```python" not in chunks[0]

    def test_smart_chunk_markdown_min_position_respected(self, service):
        """Test that boundaries must be past minimum position."""
        # Create content where boundary is too early
        content = "Short. " + "A" * 200  # Boundary at position 7, min would be 60 (30% of 200)
        chunks = service.smart_chunk_markdown(content, chunk_size=200)
        # Content length is 207, chunk_size=200, so should create 2 chunks
        assert len(chunks) == 2
        assert len(chunks[0]) == 200
        assert len(chunks[1]) == 7

    def test_smart_chunk_markdown_strips_whitespace(self, service):
        """Test that chunks are stripped of leading/trailing whitespace."""
        content = "  \n\n  Content with whitespace  \n\n  "
        chunks = service.smart_chunk_markdown(content, chunk_size=50)
        assert len(chunks) == 1
        assert chunks[0] == "Content with whitespace"

    def test_smart_chunk_markdown_uses_default_chunk_size(self, service):
        """Test that default chunk size is used when not specified."""
        content = "A" * 3000
        chunks = service.smart_chunk_markdown(content)  # No chunk_size specified
        # With default 2000, should create 2 chunks
        assert len(chunks) == 2
        assert len(chunks[0]) == 2000
        assert len(chunks[1]) == 1000

    def test_smart_chunk_markdown_custom_chunk_size(self, service):
        """Test custom chunk size parameter."""
        content = "A" * 500
        chunks = service.smart_chunk_markdown(content, chunk_size=100)
        assert len(chunks) == 5
        for chunk in chunks:
            assert len(chunk) == 100

    def test_estimate_chunks_zero_length(self, service):
        """Test estimating chunks for zero length content."""
        assert service.estimate_chunks(0) == 0

    def test_estimate_chunks_negative_length(self, service):
        """Test estimating chunks for negative length."""
        assert service.estimate_chunks(-10) == 0

    def test_estimate_chunks_small_content(self, service):
        """Test estimating chunks for small content."""
        assert service.estimate_chunks(100, chunk_size=200) == 1

    def test_estimate_chunks_large_content(self, service):
        """Test estimating chunks for large content."""
        # 1000 chars with 200 chunk size, 80% utilization = ~7 chunks
        estimated = service.estimate_chunks(1000, chunk_size=200)
        assert estimated >= 6 and estimated <= 8

    def test_estimate_chunks_uses_default_chunk_size(self, service):
        """Test estimate_chunks uses default when not specified."""
        service.default_chunk_size = 500
        assert service.estimate_chunks(1000) == 3  # 1000 / (500 * 0.8) ≈ 2.5, rounded up

    def test_validate_chunks_empty_list(self, service):
        """Test validating empty chunk list."""
        assert not service.validate_chunks([])

    def test_validate_chunks_valid_chunks(self, service):
        """Test validating chunks within size limits."""
        chunks = ["Normal", "A" * 200, "Another"]
        assert service.validate_chunks(chunks, min_size=1, max_size=500)

    def test_validate_chunks_too_small(self, service):
        """Test validating chunks that are too small."""
        chunks = ["A", "Normal"]
        assert not service.validate_chunks(chunks, min_size=2, max_size=500)

    def test_validate_chunks_too_large(self, service):
        """Test validating chunks that are too large."""
        chunks = ["A" * 1000, "Normal"]
        assert not service.validate_chunks(chunks, min_size=1, max_size=500)

    def test_validate_chunks_mixed_sizes(self, service):
        """Test validating chunks with mixed valid/invalid sizes."""
        chunks = ["OK", "A", "A" * 1000]  # One too small, one too large
        assert not service.validate_chunks(chunks, min_size=2, max_size=500)

    def test_validate_chunks_default_limits(self, service):
        """Test validating with default size limits."""
        chunks = ["A" * 50, "A" * 200, "A" * 5000]  # 5000 > 10000 default max
        assert not service.validate_chunks(chunks)

    def test_find_last_boundary_not_found(self, service):
        """Test _find_last_boundary when boundary not found."""
        assert service._find_last_boundary("no boundary here", "|||", 10) is None

    def test_find_last_boundary_found_after_min(self, service):
        """Test _find_last_boundary finds boundary after minimum position."""
        pos = service._find_last_boundary("start|||middle|||end", "|||", 5)
        assert pos == 14  # Position of last "|||"

    def test_find_last_boundary_found_before_min(self, service):
        """Test _find_last_boundary ignores boundary before minimum position."""
        pos = service._find_last_boundary("start|||end", "|||", 10)
        assert pos is None  # "|||" at position 5 < 10

    def test_find_last_boundary_empty_content(self, service):
        """Test _find_last_boundary with empty content."""
        assert service._find_last_boundary("", "|||", 10) is None

    def test_find_last_boundary_boundary_at_start(self, service):
        """Test _find_last_boundary with boundary at start."""
        pos = service._find_last_boundary("|||content", "|||", 0)
        assert pos == 0

    # Integration-style tests with realistic content
    def test_realistic_markdown_chunking(self, service):
        """Test chunking realistic Markdown documentation."""
        content = """# API Reference

This section describes the API endpoints.

## GET /users

Retrieves a list of users.

### Parameters

- `limit`: Maximum number of results
- `offset`: Pagination offset

### Response

```json
{
  "users": [
    {"id": 1, "name": "John"}
  ]
}
```

## POST /users

Creates a new user.

### Request Body

```json
{
  "name": "Jane",
  "email": "jane@example.com"
}
```

### Response

Returns the created user object."""

        chunks = service.smart_chunk_markdown(content, chunk_size=300)
        assert len(chunks) >= 2

        # Verify code blocks stay intact
        json_blocks = [chunk for chunk in chunks if '"users"' in chunk]
        assert len(json_blocks) >= 1

        # Verify all chunks are valid
        assert service.validate_chunks(chunks, min_size=50, max_size=1000)

    def test_realistic_markdown_chunking_small_chunks(self, service_small_chunks):
        """Test chunking realistic Markdown with small chunk size."""
        content = """# Header 1
Some text.

## Header 2
More text.
"""
        chunks = service_small_chunks.smart_chunk_markdown(content, chunk_size=150)

        # Verify at least some headers are preserved (may be consolidated in chunks)
        headers_found = sum(1 for chunk in chunks if "#" in chunk)
        assert headers_found >= 1  # At least one chunk contains headers

        # Verify all chunks are valid
        assert service_small_chunks.validate_chunks(chunks, min_size=20, max_size=300)
