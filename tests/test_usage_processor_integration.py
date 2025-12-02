#!/usr/bin/env python3
"""
Integration Test: Usage Processor with Real Context Generation

This test demonstrates that the usage processor feature works end-to-end by:
1. Crawling real documentation that generates actual pages
2. Creating a processing group with chunks
3. Reprocessing the group WITH context generation enabled
4. Verifying that the usage processor is called with real token counts

This test is meant to validate that the usage processor feature is working
correctly and actually receiving RunUsage data from LLM operations.
"""

import asyncio
import logging
from typing import Dict
from pydantic_ai import RunUsage

from context_bridge import ContextBridge, Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UsageTracker:
    """Track token usage across operations."""

    def __init__(self):
        self.operations: list[Dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    async def process_usage(self, usage: RunUsage) -> None:
        """Process RunUsage data from LLM operations."""
        total_tokens = usage.input_tokens + usage.output_tokens

        # Calculate cost (using Gemini pricing)
        # Assuming: $0.075 per 1M input tokens, $0.30 per 1M output tokens
        input_cost = (usage.input_tokens / 1_000_000) * 0.075
        output_cost = (usage.output_tokens / 1_000_000) * 0.30
        operation_cost = input_cost + output_cost

        operation = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": total_tokens,
            "cost": operation_cost,
        }

        self.operations.append(operation)
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cost += operation_cost

        logger.info(
            f"✓ Usage tracked: {total_tokens} tokens "
            f"(input: {usage.input_tokens}, output: {usage.output_tokens}), "
            f"cost: ${operation_cost:.6f}"
        )

    def get_summary(self) -> Dict:
        """Get summary of all tracked usage."""
        return {
            "total_operations": len(self.operations),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "operations": self.operations,
        }


async def test_usage_processor_with_context_generation():
    """Main test: verify usage processor works with real context generation."""

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Usage Processor with Real Context Generation")
    print("=" * 80)
    print("\nThis test will:")
    print("  1. Crawl real documentation (Python requests library)")
    print("  2. Create a processing group with chunks")
    print("  3. Reprocess with context generation ENABLED (triggers LLM calls)")
    print("  4. Verify usage processor receives token counts")
    print("\n" + "-" * 80)

    # Initialize tracker
    tracker = UsageTracker()

    # Create config
    config = Config()

    try:
        async with ContextBridge(config=config) as bridge:
            # Register usage processor
            bridge.set_usage_processor(tracker.process_usage)
            print("\n✓ Usage processor registered")
            print(f"  Model: {config.context_agent_model}")
            print(f"  Temperature: {config.context_agent_temperature}")
            print(f"  Cache enabled: {config.context_enable_cache}")

            # Step 1: Crawl documentation
            print("\n" + "-" * 80)
            print("STEP 1: Crawling documentation...")
            print("-" * 80)

            crawl_result = await bridge.crawl_documentation(
                name="python_requests",
                version="2.31.0",
                source_url="https://requests.readthedocs.io",
                max_depth=2,
            )

            print(f"✓ Crawl complete (Document ID: {crawl_result.document_id})")
            print(f"  Pages crawled: {crawl_result.pages_crawled}")
            print(f"  Pages stored: {crawl_result.pages_stored}")

            if crawl_result.pages_stored == 0:
                print("\n⚠️  No pages were stored from crawl!")
                print("  Trying alternative: crawling httpbin.org with actual HTML pages...")

                # Try a simpler site that definitely returns content
                crawl_result = await bridge.crawl_documentation(
                    name="httpbin_api",
                    version="1.0.0",
                    source_url="https://httpbin.org/html",
                    max_depth=1,
                )

                print(f"✓ Crawl complete (Document ID: {crawl_result.document_id})")
                print(f"  Pages crawled: {crawl_result.pages_crawled}")
                print(f"  Pages stored: {crawl_result.pages_stored}")

            if crawl_result.pages_stored == 0:
                print("\n❌ Failed to get any pages from crawl!")
                print("  Cannot proceed with context generation test.")
                return

            document_id = crawl_result.document_id

            # Step 2: List pages and create group
            print("\n" + "-" * 80)
            print("STEP 2: Creating processing group...")
            print("-" * 80)

            pages = await bridge.list_pages(document_id, limit=50)
            print(f"✓ Found {len(pages)} pages")

            if not pages:
                print("❌ No pages found!")
                return

            # Use first few pages for processing
            page_ids = [p.id for p in pages[:3]]
            print(f"  Using first {len(page_ids)} pages for processing")

            group_result = await bridge.create_group(
                document_id=document_id,
                page_ids=page_ids,
                context_enabled=False,  # Initial group without context
            )

            print(f"✓ Group created")
            print(f"  Pages processed: {group_result.pages_processed}")

            # Step 3: Get the group
            print("\n" + "-" * 80)
            print("STEP 3: Reprocessing group WITH context generation...")
            print("-" * 80)

            groups = await bridge.list_groups(document_id)
            if not groups:
                print("❌ No groups found!")
                return

            latest_group = groups[-1]
            print(f"✓ Found group: {latest_group.id}")
            print(f"  Status: {latest_group.processing_status}")
            print(f"  Initial chunks: {latest_group.chunk_count}")

            # Reprocess WITH context generation enabled
            # This will trigger LLM calls and the usage processor
            print("\n  Starting reprocessing with CONTEXT GENERATION ENABLED...")
            print("  This will generate contexts for each chunk using the LLM...")

            reprocess_result = await bridge.reprocess_group(
                group_id=latest_group.id,
                context_enabled=True,  # Enable context generation - TRIGGERS LLM CALLS
                context_model=config.context_agent_model,
            )

            print(f"\n✓ Reprocessing complete!")
            print(f"  Contexts generated: {reprocess_result.contexts_generated}")

            # Step 4: Print usage summary
            print("\n" + "=" * 80)
            print("USAGE PROCESSOR RESULTS")
            print("=" * 80)

            summary = tracker.get_summary()

            if summary["total_operations"] == 0:
                print("\n❌ FAILED: No usage data was captured!")
                print("   The usage processor was NOT called during context generation.")
                print("   This indicates a problem with the integration.")
            else:
                print(f"\n✓ SUCCESS: Usage processor called {summary['total_operations']} times!")
                print(f"\nToken Usage Summary:")
                print(f"  Total input tokens:  {summary['total_input_tokens']:,}")
                print(f"  Total output tokens: {summary['total_output_tokens']:,}")
                print(f"  Total tokens:        {summary['total_tokens']:,}")
                print(f"  Total cost:          ${summary['total_cost']:.6f}")

                print(f"\nDetailed Operations:")
                for i, op in enumerate(summary["operations"], 1):
                    print(
                        f"  Op #{i}: {op['input_tokens']:,} input + "
                        f"{op['output_tokens']:,} output = "
                        f"{op['total_tokens']:,} total (${op['cost']:.6f})"
                    )

                print("\n✅ INTEGRATION TEST PASSED!")
                print("   The usage processor feature is working correctly.")

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_usage_processor_with_context_generation())
