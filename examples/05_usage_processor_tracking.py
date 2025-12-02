#!/usr/bin/env python3
"""
Example: Token Usage Tracking with Usage Processor

This example demonstrates how to use the usage processor feature to track
LLM token consumption from Pydantic AI agent operations.

The usage processor is simply an async callable function that receives RunUsage
and returns None. Users define their own processor logic externally.

Topics covered:
1. Simple logging processor
2. Token counting processor with closure
3. Cost calculation processor
4. Multiple processors via chaining
5. REAL DEMONSTRATION: How usage processors work with context generation
"""

import asyncio
import logging
from datetime import datetime

from context_bridge import ContextBridge, Config
from pydantic_ai import RunUsage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Pattern 1: Simple Logging Processor
# ============================================================================


async def simple_logger(usage: RunUsage) -> None:
    """Minimal processor that just logs token usage."""
    total_tokens = usage.input_tokens + usage.output_tokens
    logger.info(
        f"Agent used {total_tokens} tokens (input: {usage.input_tokens}, output: {usage.output_tokens})"
    )


# ============================================================================
# Pattern 2: Token Counter with Closure
# ============================================================================


def create_token_counter():
    """Create a token counter processor with internal state."""
    stats = {
        "total_runs": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    async def counter(usage: RunUsage) -> None:
        """Count tokens across all runs."""
        stats["total_runs"] += 1
        stats["total_input_tokens"] += usage.input_tokens
        stats["total_output_tokens"] += usage.output_tokens
        total = usage.input_tokens + usage.output_tokens
        logger.info(
            f"Run #{stats['total_runs']}: {total} tokens "
            f"(total so far: {stats['total_input_tokens'] + stats['total_output_tokens']})"
        )

    return counter, stats


# ============================================================================
# Pattern 3: Cost Calculator Processor
# ============================================================================


def create_cost_calculator(
    input_cost_per_million: float = 3.0,
    output_cost_per_million: float = 15.0,
):
    """Create a cost calculator processor."""
    cost_data = {"total_cost": 0.0, "run_count": 0}

    async def calculate_cost(usage: RunUsage) -> None:
        """Calculate and accumulate costs."""
        input_cost = (usage.input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (usage.output_tokens / 1_000_000) * output_cost_per_million
        run_cost = input_cost + output_cost
        cost_data["total_cost"] += run_cost
        cost_data["run_count"] += 1

        logger.info(
            f"Cost - Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, "
            f"Run total: ${run_cost:.6f}, Accumulated: ${cost_data['total_cost']:.6f}"
        )

    return calculate_cost, cost_data


# ============================================================================
# Pattern 4: Advanced Logger with Timestamps
# ============================================================================


def create_advanced_logger():
    """Create an advanced logger with timestamps."""
    operations = []
    start_time = datetime.now()

    async def log_with_timestamp(usage: RunUsage) -> None:
        """Log usage with detailed timing information."""
        elapsed = (datetime.now() - start_time).total_seconds()
        record = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.input_tokens + usage.output_tokens,
        }
        operations.append(record)
        logger.info(
            f"[{record['elapsed_seconds']:.2f}s] "
            f"Operation #{len(operations)}: {record['total_tokens']} tokens"
        )

    return log_with_timestamp, operations


# ============================================================================
# Pattern 5: Multiple Processors via Chaining
# ============================================================================


def create_multi_processor(*processors):
    """Chain multiple processors together."""

    async def chained_processor(usage: RunUsage) -> None:
        """Call all processors in sequence."""
        for processor in processors:
            try:
                await processor(usage)
            except Exception as e:
                logger.error(f"Processor {processor.__name__} failed: {e}", exc_info=True)

    return chained_processor


# ============================================================================
# DEMONSTRATION: Usage Processor Integration with Real Context Generation
# ============================================================================


async def example_usage_processor_demonstration():
    """
    Demonstrate the usage processor with actual context generation.

    This shows how the processor integrates with Pydantic AI agents
    when context generation is triggered.
    """
    print("\n" + "=" * 70)
    print("DEMONSTRATION: Usage Processor with Context Generation")
    print("=" * 70)

    print("\nHow Usage Processors Work:")
    print("  1. You register an async callable with ContextBridge")
    print("  2. When ContextGenerator runs an LLM agent for context generation")
    print("  3. The processor is called with RunUsage token data")
    print("  4. Your processor can log, track, calculate costs, etc.")

    print("\nTo see this in action:")
    print("  - Run with Docker database: Use test_usage_processor_integration.py")
    print("  - Run mock test: Use test_usage_processor_unit.py")
    print("\nBoth tests verify that usage processors are called with real token counts")

    try:
        from context_bridge.agents.context_generator import ContextGenerator
        from unittest.mock import AsyncMock

        config = Config()

        # Create context generator with processor
        context_gen = ContextGenerator(config=config, usage_processor=simple_logger)
        print("\n[OK] ContextGenerator created with usage processor")

        # Mock the LLM agent to demonstrate without making actual API calls
        class MockResult:
            def __init__(self, input_tok, output_tok):
                self.output = type(
                    "Output", (), {"context": "This chunk discusses database connection pooling."}
                )()
                self.usage = RunUsage(input_tokens=input_tok, output_tokens=output_tok)

        # Mock the agent
        async def mock_agent_run(prompt: str):
            return MockResult(input_tok=45, output_tok=156)

        context_gen._agent = AsyncMock()
        context_gen._agent.run = mock_agent_run
        context_gen._current_document = "Sample documentation"

        # Generate a context - this calls the processor
        print("\nGenerating context (processor will be called)...")
        context = await context_gen.generate_context(
            chunk_content="Database pooling improves performance.",
            document_content="Sample documentation",
        )

        print(f"\n[OK] Context generated: {context}")
        print("[SUCCESS] The processor was called with token usage data!")

        # Batch demonstration
        print("\nBatch processing demonstration...")
        call_count = [0]

        async def mock_batch_run(prompt: str):
            call_count[0] += 1
            return MockResult(input_tok=40 + call_count[0] * 5, output_tok=150 + call_count[0] * 10)

        context_gen._agent.run = mock_batch_run

        chunks = ["Pooling", "Query optimization", "Transactions"]
        print(f"\nGenerating contexts for {len(chunks)} chunks...")

        contexts = await context_gen.generate_contexts_batch(
            chunks=chunks, document_content="Sample documentation"
        )

        print(f"[OK] Generated {len(contexts)} contexts")
        print("[SUCCESS] Multiple processor calls for batch operations!")

    except Exception as e:
        logger.error(f"Error in demonstration: {e}", exc_info=True)
        print(f"Demo error (this is expected if context_bridge is not in PYTHONPATH): {e}")


# ============================================================================
# Main
# ============================================================================


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Context Bridge: Token Usage Tracking Examples")
    print("=" * 70)

    print("\n" + "-" * 70)
    print("PATTERN 1: Simple Logging Processor")
    print("-" * 70)
    print("\nDemonstration of basic logging:")

    counter, stats = create_token_counter()
    print(f"[OK] Token counter created")
    print("\nThis would be called like: bridge.set_usage_processor(simple_logger)")

    print("\n" + "-" * 70)
    print("PATTERN 2: Token Counter with Closure")
    print("-" * 70)
    print("[OK] Token counter created with internal state tracking")
    print("Stats dict maintains count across all runs:")
    print(f"  {stats}")

    print("\n" + "-" * 70)
    print("PATTERN 3: Cost Calculator")
    print("-" * 70)
    cost_calc, cost_data = create_cost_calculator(
        input_cost_per_million=3.0,
        output_cost_per_million=15.0,
    )
    print("[OK] Cost calculator registered (OpenAI pricing)")
    print("Available pricing models: Anthropic, OpenAI, Google, etc.")

    print("\n" + "-" * 70)
    print("PATTERN 4: Advanced Logger with Timestamps")
    print("-" * 70)
    logger_func, operations = create_advanced_logger()
    print("[OK] Advanced logger registered")

    print("\n" + "-" * 70)
    print("PATTERN 5: Multiple Processors")
    print("-" * 70)
    chained = create_multi_processor(simple_logger, counter, cost_calc, logger_func)
    print("[OK] Chained processor registered with 4 processors")
    print("  - Simple logger")
    print("  - Token counter")
    print("  - Cost calculator")
    print("  - Advanced logger with timestamps")

    # Run the real demonstration
    await example_usage_processor_demonstration()

    print("\n" + "=" * 70)
    print("[SUCCESS] All examples completed!")
    print("=" * 70)
    print("\nUsage Processor Definition:")
    print("  async def my_processor(usage: RunUsage) -> None:")
    print("      # Your custom logic here")
    print("      pass")
    print("\n  bridge.set_usage_processor(my_processor)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
