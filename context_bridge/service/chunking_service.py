"""Smart Markdown chunking service for context_bridge.

This module provides intelligent chunking of Markdown content that preserves
structural integrity by splitting at logical boundaries rather than arbitrary points.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for smart Markdown chunking that preserves structure.

    This service implements intelligent chunking algorithms that attempt to split
    Markdown content at logical boundaries (code blocks, paragraphs, sentences)
    rather than at arbitrary character positions.
    """

    def __init__(self, default_chunk_size: int = 2000):
        """Initialize the chunking service.

        Args:
            default_chunk_size: Default maximum chunk size in characters.
        """
        self.default_chunk_size = default_chunk_size

    def smart_chunk_markdown(self, markdown: str, chunk_size: Optional[int] = None) -> List[str]:
        """Smart chunk Markdown content preserving structure.

        Algorithm prioritizes splitting at logical boundaries:
        1. Try to split at code blocks (```)
        2. Fall back to paragraph breaks (\n\n)
        3. Fall back to sentence breaks (. )
        4. Fall back to hard limit

        Args:
            markdown: The Markdown content to chunk.
            chunk_size: Maximum chunk size. Uses default if None.

        Returns:
            List of chunk strings.
        """
        if not markdown:
            return []

        chunk_size = chunk_size or self.default_chunk_size
        chunks: List[str] = []
        start = 0
        content_length = len(markdown)

        while start < content_length:
            # Calculate potential end position
            end = start + chunk_size

            # If we're at the end of the content, take remaining
            if end >= content_length:
                chunk = markdown[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Look for the best boundary within this chunk
            slice_content = markdown[start:end]

            # Priority 1: Code blocks (```) - find last occurrence >30% into chunk
            code_block_pos = self._find_last_boundary(slice_content, "```", chunk_size * 0.3)
            if code_block_pos is not None:
                end = start + code_block_pos
            else:
                # Priority 2: Paragraph breaks (\n\n) - find last occurrence >30% into chunk
                paragraph_pos = self._find_last_boundary(slice_content, "\n\n", chunk_size * 0.3)
                if paragraph_pos is not None:
                    end = start + paragraph_pos
                else:
                    # Priority 3: Sentence breaks (. ) - find last occurrence >30% into chunk
                    sentence_pos = self._find_last_boundary(slice_content, ". ", chunk_size * 0.3)
                    if sentence_pos is not None:
                        # Include the ". " in the current chunk
                        end = start + sentence_pos + 2
                    # Priority 4: Hard limit (end remains start + chunk_size)

            # Extract chunk
            chunk = markdown[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position
            start = end

        return chunks

    def _find_last_boundary(
        self, content: str, boundary: str, min_position: float
    ) -> Optional[int]:
        """Find the last occurrence of a boundary that's past the minimum position.

        Args:
            content: Content to search in.
            boundary: Boundary string to find.
            min_position: Minimum position (characters from start).

        Returns:
            Position of the boundary start, or None if not found.
        """
        last_pos = content.rfind(boundary)
        if last_pos >= min_position:
            return last_pos
        return None

    def estimate_chunks(self, content_length: int, chunk_size: Optional[int] = None) -> int:
        """Estimate number of chunks for given content length.

        This is a rough estimate assuming average chunk utilization.
        Actual chunk count may vary based on content structure.

        Args:
            content_length: Total length of content in characters.
            chunk_size: Chunk size to use. Uses default if None.

        Returns:
            Estimated number of chunks.
        """
        chunk_size = chunk_size or self.default_chunk_size
        if content_length <= 0:
            return 0

        # Estimate assuming 80% utilization on average
        avg_chunk_size = int(chunk_size * 0.8)
        estimated = (content_length + avg_chunk_size - 1) // avg_chunk_size
        return max(1, estimated)

    def validate_chunks(
        self, chunks: List[str], min_size: int = 100, max_size: int = 10000
    ) -> bool:
        """Validate that chunks meet size constraints.

        Args:
            chunks: List of chunk strings to validate.
            min_size: Minimum allowed chunk size in characters.
            max_size: Maximum allowed chunk size in characters.

        Returns:
            True if all chunks are within size constraints.
        """
        if not chunks:
            return False

        for i, chunk in enumerate(chunks):
            chunk_len = len(chunk)
            if chunk_len < min_size:
                logger.warning(f"Chunk {i} too small: {chunk_len} chars (min: {min_size})")
                return False
            if chunk_len > max_size:
                logger.warning(f"Chunk {i} too large: {chunk_len} chars (max: {max_size})")
                return False

        return True
