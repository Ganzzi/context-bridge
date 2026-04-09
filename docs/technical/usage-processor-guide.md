# Usage Processor Guide

## Overview

The **Usage Processor** is a pluggable feature in Agent Mem that allows you to track and monitor LLM token usage from Pydantic AI agent operations. This is essential for understanding costs, monitoring usage patterns, and optimizing your application's resource consumption.

## Table of Contents

1. [Concept](#concept)
2. [Architecture](#architecture)
3. [Basic Usage](#basic-usage)
4. [Implementation Patterns](#implementation-patterns)
5. [RunUsage Object](#runusage-object)
6. [Integration Examples](#integration-examples)
7. [Cost Tracking](#cost-tracking)
8. [Best Practices](#best-practices)
9. [Advanced Patterns](#advanced-patterns)

---

## Concept

### What is a Usage Processor?

A Usage Processor is a callback function (or coroutine) that receives token usage data from Pydantic AI agent runs. It allows you to:

- **Track token consumption** per operation, agent, or time period
- **Monitor costs** based on your LLM pricing
- **Identify bottlenecks** in token usage
- **Implement custom logging** and analytics
- **Enforce usage quotas** or limits

### When Usage is Tracked

Token usage is tracked whenever an Agent Mem operation involves Pydantic AI agents:

- ✅ `deep_search_memories()` - AI synthesis uses agents
- ✅ Memory consolidation workflows - Entity extraction and relationship analysis
- ❌ `search_memories()` - Programmatic search, no agent involved
- ❌ Creating/updating/deleting active memories - No agent involved
- ❌ Retrieving memories - No agent involved

---

## Architecture

### Design Pattern

The usage processor follows a **Protocol-based design pattern** for flexibility:

```python
from typing import Protocol
from pydantic_ai.usage import RunUsage

class UsageProcessor(Protocol):
    """Protocol for pluggable token usage processing."""

    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """
        Process token usage data from an agent run.

        Args:
            external_id: Agent identifier
            usage: RunUsage object from pydantic-ai agent
        """
        ...
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────┐
│            AgentMem (Stateless)                         │
│  - Serves multiple agents/workers                       │
│  - Has optional usage_processor                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ set_usage_processor(processor)
                       ▼
┌─────────────────────────────────────────────────────────┐
│        MemoryManager                                    │
│  - Coordinates memory operations                        │
│  - Calls usage_processor after agent runs              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ Agent operations
                       ▼
┌─────────────────────────────────────────────────────────┐
│     Pydantic AI Agents                                  │
│  - MemoryRetrieveAgent                                  │
│  - ExtractionAgent                                      │
│  - Returns RunUsage with token counts                   │
└─────────────────────────────────────────────────────────┘
```

---

## Basic Usage

### Simplest Implementation

The most basic usage processor is a simple logging function:

```python
import asyncio
from pydantic_ai import RunUsage
from agent_reminiscence import AgentMem

async def log_usage(external_id: str, usage: RunUsage) -> None:
    """Simple usage logger."""
    total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
    print(f"{external_id}: {total} tokens (in: {usage.input_tokens}, out: {usage.output_tokens})")

async def main():
    agent_mem = AgentMem()
    await agent_mem.initialize()
    
    # Register the usage processor
    agent_mem.set_usage_processor(log_usage)
    
    # Now all agent operations will call log_usage
    result = await agent_mem.deep_search_memories(
        external_id="user-123",
        query="What is the current status?",
        synthesis=True
    )
    # ✓ log_usage is called with usage data
    
    await agent_mem.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using a Class-Based Tracker

A more structured approach using a class:

```python
from pydantic_ai import RunUsage

class UsageTracker:
    """Tracks token usage across operations."""
    
    def __init__(self):
        self.total_tokens = 0
        self.operations = []
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Process token usage from agent run."""
        total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        self.total_tokens += total
        
        self.operations.append({
            "agent_id": external_id,
            "tokens": total,
            "requests": usage.requests
        })

# Usage
tracker = UsageTracker()
agent_mem.set_usage_processor(tracker.process_usage)
```

---

## Implementation Patterns

### Pattern 1: Simple Logging

```python
async def log_tokens(external_id: str, usage: RunUsage) -> None:
    """Log token usage to console."""
    print(f"[{external_id}] Tokens: {usage.total_tokens}")
```

### Pattern 2: Database Storage

```python
import aiosqlite

class DatabaseTracker:
    def __init__(self, db_path: str = "usage.db"):
        self.db_path = db_path
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Store usage to SQLite database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO usage_logs (external_id, input_tokens, output_tokens) VALUES (?, ?, ?)",
                (external_id, usage.input_tokens, usage.output_tokens)
            )
            await db.commit()
```

### Pattern 3: Cost Calculation

```python
class CostCalculator:
    """Calculate costs based on token usage and model pricing."""
    
    def __init__(self, input_rate: float = 3.0, output_rate: float = 15.0):
        """
        Initialize with per-1M-token pricing.
        
        Args:
            input_rate: Cost per 1M input tokens (default: $3)
            output_rate: Cost per 1M output tokens (default: $15)
        """
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.total_cost = 0.0
        self.operations = []
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Calculate and track costs."""
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
        
        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.input_rate
        output_cost = (output_tokens / 1_000_000) * self.output_rate
        operation_cost = input_cost + output_cost
        
        self.total_cost += operation_cost
        self.operations.append({
            "external_id": external_id,
            "cost": operation_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        })
        
        print(f"[{external_id}] Cost: ${operation_cost:.6f}")
    
    def get_summary(self) -> dict:
        """Get cost summary."""
        return {
            "total_cost": self.total_cost,
            "operations_count": len(self.operations),
            "average_cost": self.total_cost / len(self.operations) if self.operations else 0
        }
```

### Pattern 4: Quota Enforcement

```python
class QuotaEnforcer:
    """Enforce token usage quotas."""
    
    def __init__(self, quota_per_agent: int = 100_000):
        """
        Initialize with per-agent quota.
        
        Args:
            quota_per_agent: Max tokens allowed per agent
        """
        self.quota_per_agent = quota_per_agent
        self.usage_per_agent = {}
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Check quota and log usage."""
        total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        
        # Update usage
        current = self.usage_per_agent.get(external_id, 0)
        new_total = current + total
        self.usage_per_agent[external_id] = new_total
        
        # Check quota
        remaining = self.quota_per_agent - new_total
        if remaining < 0:
            raise QuotaExceeded(
                f"Agent {external_id} exceeded quota by {-remaining} tokens"
            )
        
        print(f"[{external_id}] Usage: {new_total}/{self.quota_per_agent} tokens")

class QuotaExceeded(Exception):
    """Raised when agent exceeds usage quota."""
    pass
```

### Pattern 5: Metrics Collection

```python
from collections import defaultdict
from datetime import datetime

class MetricsCollector:
    """Collect usage metrics and analytics."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_time = datetime.now()
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Collect metrics."""
        metric = {
            "timestamp": datetime.now(),
            "external_id": external_id,
            "input_tokens": usage.input_tokens or 0,
            "output_tokens": usage.output_tokens or 0,
            "requests": usage.requests or 0
        }
        self.metrics[external_id].append(metric)
    
    def get_agent_stats(self, external_id: str) -> dict:
        """Get statistics for an agent."""
        operations = self.metrics[external_id]
        if not operations:
            return {}
        
        input_tokens = sum(op["input_tokens"] for op in operations)
        output_tokens = sum(op["output_tokens"] for op in operations)
        
        return {
            "operations_count": len(operations),
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "average_tokens_per_operation": (input_tokens + output_tokens) / len(operations),
            "requests": sum(op["requests"] for op in operations)
        }
```

---

## RunUsage Object

### Structure

The `RunUsage` object from Pydantic AI contains:

```python
from pydantic_ai import RunUsage

class RunUsage:
    """Token usage information from an agent run."""
    
    input_tokens: Optional[int]   # Number of tokens in the input/prompt
    output_tokens: Optional[int]  # Number of tokens in the output/response
    requests: Optional[int]       # Number of API requests made
    
    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return (self.input_tokens or 0) + (self.output_tokens or 0)
```

### Example Values

For a typical deep search operation with synthesis:

```python
RunUsage(
    input_tokens=1250,      # Prompt with memory context
    output_tokens=450,      # AI synthesis response
    requests=1              # One agent run
)

# Total: 1700 tokens for this operation
```

---

## Integration Examples

### Example 1: Complete Token Tracking

```python
import asyncio
from pydantic_ai import RunUsage
from agent_reminiscence import AgentMem

class TokenUsageTracker:
    """Track and log token usage across operations."""
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
        self.operations = []
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Process token usage data."""
        self.total_input_tokens += usage.input_tokens or 0
        self.total_output_tokens += usage.output_tokens or 0
        self.total_requests += usage.requests or 0
        
        operation = {
            "external_id": external_id,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": (usage.input_tokens or 0) + (usage.output_tokens or 0)
        }
        self.operations.append(operation)
        
        print(f"[{external_id}] {operation['total_tokens']} tokens")
    
    def print_summary(self):
        """Print usage summary."""
        total = self.total_input_tokens + self.total_output_tokens
        print(f"\n{'='*60}")
        print(f"Total Input Tokens:  {self.total_input_tokens:,}")
        print(f"Total Output Tokens: {self.total_output_tokens:,}")
        print(f"Total Tokens:        {total:,}")
        print(f"Total Requests:      {self.total_requests}")
        print(f"{'='*60}\n")

async def main():
    tracker = TokenUsageTracker()
    
    agent_mem = AgentMem()
    await agent_mem.initialize()
    agent_mem.set_usage_processor(tracker.process_usage)
    
    try:
        # Perform agent operations
        result = await agent_mem.deep_search_memories(
            external_id="user-123",
            query="Summarize the project status",
            synthesis=True
        )
        
        result2 = await agent_mem.deep_search_memories(
            external_id="user-456",
            query="What are the key technologies?",
            synthesis=True
        )
        
        # Print summary
        tracker.print_summary()
        
    finally:
        await agent_mem.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Multi-Agent Tracking

```python
class MultiAgentTracker:
    """Track usage across multiple agents."""
    
    def __init__(self):
        self.agents = {}
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Track usage per agent."""
        if external_id not in self.agents:
            self.agents[external_id] = {
                "total_tokens": 0,
                "operations": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        agent_data = self.agents[external_id]
        total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        
        agent_data["total_tokens"] += total
        agent_data["operations"] += 1
        agent_data["input_tokens"] += usage.input_tokens or 0
        agent_data["output_tokens"] += usage.output_tokens or 0
    
    def get_report(self) -> dict:
        """Get detailed report of all agents."""
        report = {}
        total_tokens = 0
        
        for agent_id, data in self.agents.items():
            avg_tokens = data["total_tokens"] / data["operations"]
            report[agent_id] = {
                **data,
                "average_tokens_per_operation": avg_tokens
            }
            total_tokens += data["total_tokens"]
        
        report["summary"] = {
            "total_agents": len(self.agents),
            "total_tokens": total_tokens,
            "total_operations": sum(d["operations"] for d in self.agents.values())
        }
        
        return report
```

---

## Cost Tracking

### Pricing Models

Different LLM providers have different pricing structures:

```python
# OpenAI GPT-4o mini (example rates as of 2025)
OPENAI_PRICING = {
    "input": 3.0,       # $3 per 1M input tokens
    "output": 15.0      # $15 per 1M output tokens
}

# Anthropic Claude (example)
ANTHROPIC_PRICING = {
    "input": 3.0,       # $3 per 1M input tokens
    "output": 15.0      # $15 per 1M output tokens
}

# Google Gemini (example)
GOOGLE_PRICING = {
    "input": 1.25,      # $1.25 per 1M input tokens
    "output": 5.0       # $5 per 1M output tokens
}
```

### Cost Calculation Example

```python
class CostTracker:
    """Track costs with per-model pricing."""
    
    PRICING = {
        "openai:gpt-4o-mini": {"input": 3.0, "output": 15.0},
        "anthropic": {"input": 3.0, "output": 15.0},
        "google": {"input": 1.25, "output": 5.0}
    }
    
    def __init__(self):
        self.costs_by_agent = {}
        self.costs_by_model = {}
    
    async def process_usage(
        self, 
        external_id: str, 
        usage: RunUsage,
        model: str = "openai:gpt-4o-mini"
    ) -> None:
        """Calculate and track cost."""
        pricing = self.PRICING.get(model, self.PRICING["openai:gpt-4o-mini"])
        
        input_cost = (usage.input_tokens or 0) / 1_000_000 * pricing["input"]
        output_cost = (usage.output_tokens or 0) / 1_000_000 * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Track by agent
        if external_id not in self.costs_by_agent:
            self.costs_by_agent[external_id] = 0
        self.costs_by_agent[external_id] += total_cost
        
        # Track by model
        if model not in self.costs_by_model:
            self.costs_by_model[model] = 0
        self.costs_by_model[model] += total_cost
    
    def get_cost_summary(self) -> dict:
        """Get cost summary."""
        return {
            "by_agent": self.costs_by_agent,
            "by_model": self.costs_by_model,
            "total": sum(self.costs_by_agent.values())
        }
```

---

## Best Practices

### 1. Always Set a Usage Processor

```python
# ✅ Good
agent_mem = AgentMem()
await agent_mem.initialize()
agent_mem.set_usage_processor(my_tracker.process_usage)

# ❌ Avoid
agent_mem = AgentMem()
await agent_mem.initialize()
# No usage processor set - can't track usage!
```

### 2. Handle Exceptions in Processor

```python
async def safe_processor(external_id: str, usage: RunUsage) -> None:
    """Handle exceptions gracefully."""
    try:
        # Your processing logic
        await database.record_usage(external_id, usage)
    except Exception as e:
        # Log error but don't crash the main operation
        logger.error(f"Failed to process usage: {e}")
```

### 3. Make Processors Lightweight

```python
# ✅ Good - Fast, minimal processing
async def quick_logger(external_id: str, usage: RunUsage) -> None:
    logger.info(f"{external_id}: {usage.total_tokens} tokens")

# ❌ Avoid - Heavy processing blocks main flow
async def slow_processor(external_id: str, usage: RunUsage) -> None:
    # Complex ML model training
    model = train_model(usage)  # Takes 5 minutes!
```

### 4. Use Async Operations

```python
# ✅ Good - Use async for I/O
async def async_database_logger(external_id: str, usage: RunUsage) -> None:
    async with aiosqlite.connect("usage.db") as db:
        await db.execute(...)
        await db.commit()

# ❌ Avoid - Blocking operations
def sync_processor(external_id: str, usage: RunUsage) -> None:
    db = sqlite3.connect("usage.db")  # Blocks!
    db.execute(...)
```

### 5. Document Usage Expectations

```python
class DocumentedProcessor:
    """Track usage with clear documentation.
    
    Usage:
        processor = DocumentedProcessor()
        agent_mem.set_usage_processor(processor.process_usage)
    
    Methods:
        process_usage(): Called after each agent operation
        get_summary(): Returns usage statistics
    
    Attributes:
        total_tokens: Total tokens tracked
        operations: List of operations
    """
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Process token usage from agent run."""
        pass
```

---

## Advanced Patterns

### Pattern: Conditional Processing

```python
class ConditionalProcessor:
    """Only track certain agents or operations."""
    
    def __init__(self, tracked_agents: set = None, min_tokens: int = 100):
        self.tracked_agents = tracked_agents or set()
        self.min_tokens = min_tokens
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Process only if conditions met."""
        # Skip if agent not tracked
        if self.tracked_agents and external_id not in self.tracked_agents:
            return
        
        # Skip if tokens below threshold
        total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        if total < self.min_tokens:
            return
        
        # Process
        print(f"[{external_id}] {total} tokens")
```

### Pattern: Chaining Multiple Processors

```python
class ProcessorChain:
    """Chain multiple processors together."""
    
    def __init__(self, processors: list):
        self.processors = processors
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Call all processors in sequence."""
        for processor in self.processors:
            try:
                await processor(external_id, usage)
            except Exception as e:
                logger.error(f"Processor failed: {e}")

# Usage
chain = ProcessorChain([
    log_usage,
    track_cost,
    check_quota
])
agent_mem.set_usage_processor(chain.process_usage)
```

### Pattern: Time-Based Tracking

```python
from datetime import datetime, timedelta

class TimeBasedTracker:
    """Track usage by time period."""
    
    def __init__(self, period_minutes: int = 60):
        self.period = timedelta(minutes=period_minutes)
        self.periods = {}
    
    async def process_usage(self, external_id: str, usage: RunUsage) -> None:
        """Track usage by time period."""
        now = datetime.now()
        period_key = now.strftime("%Y-%m-%d %H:00")
        
        if period_key not in self.periods:
            self.periods[period_key] = {"total_tokens": 0, "count": 0}
        
        total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        self.periods[period_key]["total_tokens"] += total
        self.periods[period_key]["count"] += 1
    
    def get_hourly_stats(self) -> dict:
        """Get statistics by hour."""
        return {
            period: {
                "total_tokens": data["total_tokens"],
                "operations": data["count"],
                "average": data["total_tokens"] / data["count"] if data["count"] > 0 else 0
            }
            for period, data in self.periods.items()
        }
```

---

## Reference Implementation

A complete reference implementation is available in:

- **Example**: `examples/token_usage_tracking.py`
- **Core Integration**: `agent_reminiscence/services/memory_manager.py`
  - Method: `_track_usage()`
  - Attribute: `usage_processor`

---

## Troubleshooting

### Usage Processor Not Being Called

**Problem**: Processor is registered but never called.

**Solution**: Ensure you're using operations that trigger agents:
- ✅ `deep_search_memories()` - Uses AI synthesis
- ✅ Memory consolidation - Uses entity extraction
- ❌ `search_memories()` - No agent involved
- ❌ `create_active_memory()` - No agent involved

```python
# ✓ This triggers the processor
result = await agent_mem.deep_search_memories(
    external_id="user-1",
    query="...",
    synthesis=True  # This requires agents
)

# ✗ This does NOT trigger the processor
result = await agent_mem.search_memories(
    external_id="user-1",
    query="..."  # No synthesis, no agents
)
```

### Async Errors in Processor

**Problem**: `TypeError: object is not awaitable`

**Solution**: Ensure processor is `async def`:

```python
# ✅ Correct
async def processor(external_id: str, usage: RunUsage) -> None:
    await some_async_operation()

# ❌ Wrong
def processor(external_id: str, usage: RunUsage) -> None:
    await some_async_operation()  # Error!
```

### Processor Crashes Application

**Problem**: Exception in processor stops the whole application.

**Solution**: Wrap processor in try-except:

```python
async def safe_processor(external_id: str, usage: RunUsage) -> None:
    try:
        await my_processing_logic(usage)
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        # Application continues despite processor error
```

---

## Summary

The Usage Processor feature provides:

- **Flexible token tracking** through pluggable callbacks
- **Multiple implementation patterns** for different use cases
- **Cost monitoring** and quota enforcement capabilities
- **Easy integration** with existing applications
- **Stateless design** supporting multi-agent scenarios

Use it to understand your LLM costs, optimize usage, and monitor application health.
