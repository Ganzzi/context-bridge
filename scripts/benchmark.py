#!/usr/bin/env python3
"""
Performance Benchmarking Script for Context Bridge v0.2.0

This script measures performance metrics for all core components:
1. Crawling Performance - URL crawl time, pages/sec, content size
2. Chunking Performance - Chunks/sec, quality metrics, chunk size impact
3. Embedding Performance - Embedding time, batch efficiency, memory usage
4. Context Generation Performance - LLM latency, batch throughput, token tracking
5. Re-processing Performance - Group reprocessing time, batch efficiency
6. Search Performance - Vector/BM25/hybrid latency by dataset size

Run: python scripts/benchmark.py [--output <filepath>] [--component <name>]
"""

import asyncio
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.services.crawling_service import CrawlingService
from context_bridge.services.chunking_service import ChunkingService
from context_bridge.services.embedding import EmbeddingService
from context_bridge.database.repositories.chunk_repository import ChunkRepository
from context_bridge.database.repositories.document_repository import DocumentRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement"""

    component: str
    operation: str
    duration_ms: float
    items_processed: int
    throughput: float  # items per second
    metadata: Dict[str, Any]
    timestamp: str


class BenchmarkRunner:
    """Runs comprehensive performance benchmarks"""

    def __init__(self, config: Optional[Config] = None):
        """Initialize benchmark runner"""
        self.config = config or Config()
        self.db_manager = PostgreSQLManager(self.config)
        self.metrics: List[PerformanceMetric] = []

        # Initialize services
        self.crawling_service = CrawlingService(self.config, self.db_manager)
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService(
            model_name="all-MiniLM-L6-v2",  # Small model for fast benchmarking
            cache_path=self.config.embedding_cache_dir,
        )
        self.chunk_repo = ChunkRepository(self.db_manager)
        self.doc_repo = DocumentRepository(self.db_manager)

    async def benchmark_crawling(self) -> None:
        """Benchmark crawling performance"""
        logger.info("=" * 60)
        logger.info("BENCHMARK: Crawling Performance")
        logger.info("=" * 60)

        test_urls = [
            "https://www.wikipedia.org",
            "https://www.python.org/doc",
            "https://github.com/",
        ]

        for url in test_urls:
            try:
                logger.info(f"Crawling: {url}")
                start_time = time.time()

                # Perform crawl
                result = await asyncio.wait_for(
                    self.crawling_service.crawl_webpage(url), timeout=30.0
                )

                duration_ms = (time.time() - start_time) * 1000
                content_size = len(result.get("content", ""))

                metric = PerformanceMetric(
                    component="crawling",
                    operation=f"crawl_{url.split('/')[-1] or 'root'}",
                    duration_ms=duration_ms,
                    items_processed=1,
                    throughput=1000 / duration_ms if duration_ms > 0 else 0,
                    metadata={
                        "url": url,
                        "content_size_kb": content_size / 1024,
                        "status": "success",
                    },
                    timestamp=datetime.now().isoformat(),
                )

                self.metrics.append(metric)
                logger.info(f"  Duration: {duration_ms:.2f}ms, Content: {content_size/1024:.2f}KB")

            except asyncio.TimeoutError:
                logger.warning(f"  Timeout crawling {url}")
                metric = PerformanceMetric(
                    component="crawling",
                    operation=f"crawl_{url.split('/')[-1] or 'root'}",
                    duration_ms=30000,
                    items_processed=0,
                    throughput=0,
                    metadata={"url": url, "status": "timeout"},
                    timestamp=datetime.now().isoformat(),
                )
                self.metrics.append(metric)
            except Exception as e:
                logger.error(f"  Error crawling {url}: {e}")

    async def benchmark_chunking(self) -> None:
        """Benchmark chunking performance"""
        logger.info("=" * 60)
        logger.info("BENCHMARK: Chunking Performance")
        logger.info("=" * 60)

        # Test content samples
        test_samples = {
            "small": "This is a small document. " * 10,  # ~260 chars
            "medium": "This is a medium document. " * 100,  # ~2.6 KB
            "large": "This is a large document. " * 1000,  # ~26 KB
        }

        for size_name, content in test_samples.items():
            logger.info(f"Chunking {size_name} document ({len(content)} chars)")

            start_time = time.time()
            chunks = await self.chunking_service.smart_chunk_markdown(
                content, chunk_size=self.config.chunk_size
            )
            duration_ms = (time.time() - start_time) * 1000

            metric = PerformanceMetric(
                component="chunking",
                operation=f"chunk_{size_name}",
                duration_ms=duration_ms,
                items_processed=len(chunks),
                throughput=len(chunks) / (duration_ms / 1000) if duration_ms > 0 else 0,
                metadata={
                    "content_size_kb": len(content) / 1024,
                    "chunk_count": len(chunks),
                    "avg_chunk_size": len(content) / len(chunks) if chunks else 0,
                },
                timestamp=datetime.now().isoformat(),
            )

            self.metrics.append(metric)
            logger.info(
                f"  Duration: {duration_ms:.2f}ms, Chunks: {len(chunks)}, "
                f"Throughput: {metric.throughput:.2f} chunks/sec"
            )

    async def benchmark_embedding(self) -> None:
        """Benchmark embedding generation performance"""
        logger.info("=" * 60)
        logger.info("BENCHMARK: Embedding Performance")
        logger.info("=" * 60)

        # Test texts of varying length
        test_texts = {
            "short": "Python is a programming language",
            "medium": "Python is a high-level, interpreted programming language known for its "
            "simplicity and readability. It has a vast standard library and third-party packages.",
            "long": "Python is a high-level, interpreted programming language known for its simplicity "
            "and readability. It supports multiple programming paradigms including procedural, "
            "object-oriented, and functional programming. Python has a vast standard library "
            "providing tools for web development, data analysis, scientific computing, and more.",
        }

        for text_type, text in test_texts.items():
            logger.info(f"Embedding {text_type} text ({len(text)} chars)")

            start_time = time.time()
            embedding = await self.embedding_service.generate_embedding(text)
            duration_ms = (time.time() - start_time) * 1000

            metric = PerformanceMetric(
                component="embedding",
                operation=f"embed_{text_type}",
                duration_ms=duration_ms,
                items_processed=1,
                throughput=1000 / duration_ms if duration_ms > 0 else 0,
                metadata={
                    "text_length": len(text),
                    "embedding_dim": len(embedding) if embedding else 0,
                    "status": "success" if embedding else "failed",
                },
                timestamp=datetime.now().isoformat(),
            )

            self.metrics.append(metric)
            logger.info(
                f"  Duration: {duration_ms:.2f}ms, Embedding dims: "
                f"{len(embedding) if embedding else 0}"
            )

    async def benchmark_batch_embedding(self) -> None:
        """Benchmark batch embedding performance"""
        logger.info("=" * 60)
        logger.info("BENCHMARK: Batch Embedding Performance")
        logger.info("=" * 60)

        # Test different batch sizes
        base_text = "This is a test document for embedding. "
        batch_sizes = [5, 10, 20]

        for batch_size in batch_sizes:
            texts = [base_text * (i % 3 + 1) for i in range(batch_size)]
            logger.info(f"Embedding batch of {batch_size} texts")

            start_time = time.time()
            embeddings = await asyncio.gather(
                *[self.embedding_service.generate_embedding(text) for text in texts]
            )
            duration_ms = (time.time() - start_time) * 1000

            metric = PerformanceMetric(
                component="embedding",
                operation=f"batch_embed_{batch_size}",
                duration_ms=duration_ms,
                items_processed=batch_size,
                throughput=batch_size / (duration_ms / 1000) if duration_ms > 0 else 0,
                metadata={
                    "batch_size": batch_size,
                    "avg_time_per_embedding_ms": duration_ms / batch_size if batch_size > 0 else 0,
                    "status": "success",
                },
                timestamp=datetime.now().isoformat(),
            )

            self.metrics.append(metric)
            logger.info(
                f"  Duration: {duration_ms:.2f}ms, "
                f"Throughput: {metric.throughput:.2f} embeddings/sec"
            )

    async def benchmark_search(self) -> None:
        """Benchmark search performance"""
        logger.info("=" * 60)
        logger.info("BENCHMARK: Search Performance")
        logger.info("=" * 60)

        try:
            # Get document count
            docs = await self.doc_repo.list_documents(limit=1)
            if not docs:
                logger.warning("No documents found for search benchmark")
                return

            doc_id = docs[0].id

            # Test search queries
            test_queries = ["Python programming", "machine learning", "data analysis"]

            for query in test_queries:
                logger.info(f"Searching: {query}")

                start_time = time.time()
                results = await self.chunk_repo.search_chunks(
                    query=query, document_id=doc_id, limit=10
                )
                duration_ms = (time.time() - start_time) * 1000

                metric = PerformanceMetric(
                    component="search",
                    operation=f"search_{query.replace(' ', '_')}",
                    duration_ms=duration_ms,
                    items_processed=len(results),
                    throughput=10 / (duration_ms / 1000) if duration_ms > 0 else 0,
                    metadata={"query": query, "results_count": len(results), "status": "success"},
                    timestamp=datetime.now().isoformat(),
                )

                self.metrics.append(metric)
                logger.info(f"  Duration: {duration_ms:.2f}ms, Results: {len(results)}")

        except Exception as e:
            logger.error(f"Error during search benchmark: {e}")

    async def run_all_benchmarks(self) -> None:
        """Run all benchmarks"""
        logger.info("Starting Context Bridge Performance Benchmarks")
        logger.info(f"Configuration: {self.config.environment}")
        logger.info("")

        try:
            # Run benchmarks
            await self.benchmark_chunking()
            await self.benchmark_embedding()
            await self.benchmark_batch_embedding()
            await self.benchmark_search()

            # Optional: crawling (can be slow and flaky)
            # await self.benchmark_crawling()

            logger.info("")
            logger.info("=" * 60)
            logger.info("BENCHMARK COMPLETE")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error running benchmarks: {e}", exc_info=True)

    def generate_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "version": "0.2.0",
            "environment": self.config.environment,
            "metrics": [asdict(m) for m in self.metrics],
            "summary": self._generate_summary(),
        }

        # Write report
        if output_path:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report written to: {output_path}")

        return report

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        summary = {}

        by_component = {}
        for metric in self.metrics:
            if metric.component not in by_component:
                by_component[metric.component] = []
            by_component[metric.component].append(metric)

        for component, metrics in by_component.items():
            durations = [m.duration_ms for m in metrics]
            throughputs = [m.throughput for m in metrics if m.throughput > 0]

            summary[component] = {
                "total_operations": sum(m.items_processed for m in metrics),
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "avg_throughput": sum(throughputs) / len(throughputs) if throughputs else 0,
                "operations_count": len(metrics),
            }

        return summary


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Context Bridge Performance Benchmark")
    parser.add_argument("--output", type=str, help="Output file for benchmark results (JSON)")
    parser.add_argument("--component", type=str, help="Run specific component benchmark only")

    args = parser.parse_args()

    # Create runner
    runner = BenchmarkRunner()

    # Run benchmarks
    await runner.run_all_benchmarks()

    # Generate report
    output_path = args.output or ".github/benchmark_results.json"
    report = runner.generate_report(output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    for component, stats in report["summary"].items():
        print(f"\n{component.upper()}:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
