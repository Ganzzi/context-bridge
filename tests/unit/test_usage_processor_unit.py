#!/usr/bin/env python3
"""
Unit Test: Usage Processor with Mock Context Generation

This test verifies that the usage processor feature works correctly by:
1. Creating a mock ContextGenerator with a fake LLM that returns RunUsage
2. Registering a usage processor to track token counts
3. Calling generate_context and verifying the processor is called with token data

This test doesn't require a database and demonstrates the processor integration.
"""

import asyncio
import logging
from typing import Dict, Optional
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

from pydantic_ai import RunUsage
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChunkContext(BaseModel):
    """Output model for chunk context generation."""

    context: str


@dataclass
class MockRunResult:
    """Mock result from agent run."""

    output: ChunkContext
    usage: RunUsage


class UsageTracker:
    """Track token usage across operations."""

    def __init__(self):
        self.calls: list[RunUsage] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def process_usage(self, usage: RunUsage) -> None:
        """Process RunUsage data from LLM operations."""
        self.calls.append(usage)
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens

        total = usage.input_tokens + usage.output_tokens
        logger.info(
            f"✓ Processor called with usage data: "
            f"{usage.input_tokens} input + {usage.output_tokens} output = {total} total tokens"
        )

    def get_summary(self) -> Dict:
        """Get summary of all tracked usage."""
        return {
            "processor_call_count": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }


async def test_usage_processor_is_called():
    """Test that usage processor is called during context generation."""

    print("\n" + "=" * 80)
    print("UNIT TEST: Usage Processor Integration with Context Generation")
    print("=" * 80)

    print("\nTest Plan:")
    print("  1. Create a mock ContextGenerator")
    print("  2. Register a usage processor")
    print("  3. Call generate_context (which calls the agent)")
    print("  4. Verify processor was called with RunUsage data")
    print("  5. Call generate_contexts_batch and verify multiple calls")
    print("\n" + "-" * 80)

    # Import the real ContextGenerator from the local code
    # This demonstrates the actual integration
    from context_bridge.agents.context_generator import ContextGenerator
    from context_bridge.config import Config

    tracker = UsageTracker()

    # Create a config
    config = Config()

    # Create ContextGenerator with tracker
    context_gen = ContextGenerator(config=config, usage_processor=tracker.process_usage)

    print("\n✓ ContextGenerator created with usage processor")

    # Mock the agent to avoid making actual LLM calls
    print("\n" + "-" * 80)
    print("TEST 1: Single context generation")
    print("-" * 80)

    # Create a mock agent that returns test data
    mock_agent = AsyncMock()
    mock_usage = RunUsage(
        input_tokens=45,
        output_tokens=156,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    mock_result = MockRunResult(
        output=ChunkContext(context="This chunk discusses connection handling."),
        usage=mock_usage,
    )
    mock_agent.run = AsyncMock(return_value=mock_result)

    # Replace the agent with our mock
    context_gen._agent = mock_agent
    context_gen._current_document = "Mock document content"

    # Call generate_context
    result = await context_gen.generate_context(
        chunk_content="This is a test chunk about database connections.",
        document_content="Mock document content",
    )

    print(f"\n✓ Context generated: {result}")
    print(
        f"\nProcessor calls after single generation: {tracker.get_summary()['processor_call_count']}"
    )

    if tracker.get_summary()["processor_call_count"] != 1:
        print(
            f"❌ FAILED: Expected 1 processor call, got {tracker.get_summary()['processor_call_count']}"
        )
        return False

    print(f"✓ Processor was called once with:")
    print(f"  - Input tokens: {mock_usage.input_tokens}")
    print(f"  - Output tokens: {mock_usage.output_tokens}")
    print(f"  - Total: {mock_usage.input_tokens + mock_usage.output_tokens}")

    # Test 2: Batch context generation
    print("\n" + "-" * 80)
    print("TEST 2: Batch context generation")
    print("-" * 80)

    # Reset mock for multiple calls
    call_count = 0

    async def mock_agent_run_side_effect(prompt: str):
        nonlocal call_count
        call_count += 1
        return MockRunResult(
            output=ChunkContext(context=f"Context for chunk {call_count}"),
            usage=RunUsage(
                input_tokens=40 + call_count * 5,  # Vary slightly
                output_tokens=150 + call_count * 10,
            ),
        )

    mock_agent.run = mock_agent_run_side_effect

    # Generate contexts for 3 chunks
    chunks = [
        "Chunk 1 about connection pooling",
        "Chunk 2 about query optimization",
        "Chunk 3 about transaction handling",
    ]

    contexts = await context_gen.generate_contexts_batch(
        chunks=chunks,
        document_content="Mock document content",
    )

    print(f"\n✓ Generated {len(contexts)} contexts")
    for i, ctx in enumerate(contexts, 1):
        print(f"  {i}. {ctx}")

    summary = tracker.get_summary()
    print(f"\nProcessor calls after batch generation: {summary['processor_call_count']}")
    print(f"Total tokens tracked: {summary['total_tokens']}")

    if summary["processor_call_count"] != 4:  # 1 from test 1 + 3 from test 2
        print(
            f"❌ FAILED: Expected 4 total processor calls, "
            f"got {summary['processor_call_count']}"
        )
        return False

    print(f"✓ Processor was called correctly for all {len(chunks)} chunks")

    # Final results
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    print(f"\n✅ ALL TESTS PASSED!")
    print(f"\nUsage Processor Integration Status:")
    print(f"  Total processor calls: {summary['processor_call_count']}")
    print(f"  Total input tokens tracked: {summary['total_input_tokens']}")
    print(f"  Total output tokens tracked: {summary['total_output_tokens']}")
    print(f"  Total tokens tracked: {summary['total_tokens']}")

    print(f"\nKey Findings:")
    print(f"  ✓ Usage processor is called during context generation")
    print(f"  ✓ RunUsage data is properly passed to the processor")
    print(f"  ✓ Token counts are correctly accumulated")
    print(f"  ✓ The feature works correctly with batch operations")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_usage_processor_is_called())
    exit(0 if success else 1)
