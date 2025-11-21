# Pydantic AI Integration Guide

This guide provides step-by-step instructions for integrating Pydantic AI into your project to create AI agents, based on the implementation in the `agent_reminiscence` project.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Setup](#project-setup)
3. [Model Provider Setup](#model-provider-setup)
4. [Creating AI Agents](#creating-ai-agents)
5. [Agent Configuration](#agent-configuration)
6. [Usage Examples](#usage-examples)
7. [Best Practices](#best-practices)

---

## Prerequisites

### Dependencies

Add the following dependencies to your `pyproject.toml`:

```toml
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-ai>=0.3.4",
    "pydantic-ai-slim[anthropic,google,openai]>=0.3.4",
    # Add other dependencies as needed
]
```

### Environment Variables

Set up environment variables for API keys:

```bash
# .env file
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
GROK_API_KEY=your_grok_key
```

---

## Project Setup

### Directory Structure

Organize your project with the following structure:

```
your_project/
├── config/
│   └── settings.py          # Configuration management
├── services/
│   └── llm_model_provider.py # Model provider service
├── agents/
│   └── your_agent.py        # AI agent implementations
└── pyproject.toml
```

### Configuration Management

Create a settings module to manage configuration:

```python
# config/settings.py
from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""

    # AI Model Configuration
    er_extractor_agent_model: str = Field(
        default="openai:gpt-4o-mini",
        description="Model for ER extraction agent"
    )

    # API Keys
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    grok_api_key: Optional[str] = Field(default=None)

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
```

---

## Model Provider Setup

### Creating a Model Provider

Create a service to manage different LLM providers:

```python
# services/llm_model_provider.py
"""
Model provider module for mapping model names to pydantic-ai model instances.
"""

from typing import Dict, Any, Optional, Type
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.grok import GrokProvider
from pydantic_ai.providers.google import GoogleProvider

from config.settings import settings

# Mapping of providers to their model classes
PROVIDER_MODEL_CLASS_MAPPING: Dict[str, Type[Model]] = {
    "openai": OpenAIChatModel,
    "anthropic": AnthropicModel,
    "google": GoogleModel,
    "grok": OpenAIChatModel,  # Grok uses OpenAIChatModel but with GrokProvider
}

# Mapping of providers to their provider classes
PROVIDER_CLASS_MAPPING = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "grok": GrokProvider,
}


class ModelProvider:
    """
    A class that provides model instances based on model names.
    Maps shorthand model names to their respective providers and models.
    """

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the ModelProvider with optional API keys.

        Args:
            api_keys: Dictionary mapping provider names to API keys.
                      If not provided, will try to use config settings.
        """
        # Load API keys from provided dict or config
        self.api_keys = api_keys or self._load_api_keys_from_config()

    def get_model(
        self,
        model_info: str,
    ) -> Model:
        """
        Get a model instance based on the model name.
        Args:
            model_info: A string in the format "provider:model_name"
        Returns:
            An instance of the requested model.
        """
        provider_name, actual_model_name = model_info.split(":", 1)

        # Get the model class for this provider
        model_class = PROVIDER_MODEL_CLASS_MAPPING.get(provider_name)

        if not model_class:
            raise ValueError(f"Provider {provider_name} is not supported")

        # Check if we have an API key for this provider
        api_key = self.api_keys.get(provider_name)

        # If we have an API key, create a provider instance
        if api_key:
            provider_class = PROVIDER_CLASS_MAPPING.get(provider_name)
            if provider_class:
                provider = provider_class(api_key=api_key)
                return model_class(
                    actual_model_name,
                    provider=provider,
                )

        # Otherwise just create the model instance directly
        # For some models like OpenAI, the SDK will check for environment variables itself
        return model_class(actual_model_name)

    def _load_api_keys_from_config(self) -> Dict[str, str]:
        """
        Load API keys from centralized config.

        Returns:
            Dictionary mapping provider names to API keys.
        """
        api_keys = {}

        # Load API keys for each provider from config
        if settings.openai_api_key:
            api_keys["openai"] = settings.openai_api_key
        if settings.anthropic_api_key:
            api_keys["anthropic"] = settings.anthropic_api_key
        if settings.google_api_key:
            api_keys["google"] = settings.google_api_key
        if settings.grok_api_key:
            api_keys["grok"] = settings.grok_api_key

        return api_keys


# Global model provider instance
model_provider = ModelProvider()
```

### Usage

```python
from services.llm_model_provider import model_provider

# Get a model instance
model = model_provider.get_model("openai:gpt-4o-mini")
```

---

## Creating AI Agents

### Basic Agent Structure

Create agents following this pattern:

```python
# agents/your_agent.py
"""
Your AI Agent implementation.
"""

import logging
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from config.settings import settings
from services.llm_model_provider import model_provider

logger = logging.getLogger(__name__)

# =========================================================================
# OUTPUT MODELS
# =========================================================================

class YourOutputModel(BaseModel):
    """Structured output for your agent."""
    result: str = Field(description="The main result")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")

# =========================================================================
# SYSTEM PROMPT
# =========================================================================

SYSTEM_PROMPT = """You are a specialized AI assistant.

**Your Role:**
[Describe what the agent does]

**Guidelines:**
1. [Guideline 1]
2. [Guideline 2]
3. [Guideline 3]

**Important:**
- [Important note 1]
- [Important note 2]
"""

# =========================================================================
# AGENT CREATION
# =========================================================================

def get_your_agent() -> Agent[None, YourOutputModel]:
    """
    Factory function to create your AI agent.

    Returns:
        Configured Agent instance
    """
    model = model_provider.get_model(settings.your_agent_model)

    return Agent(
        model=model,
        deps_type=None,  # Add dependencies if needed
        system_prompt=SYSTEM_PROMPT,
        output_type=YourOutputModel,
        model_settings={"temperature": 0.3},
        retries=2,
    )

# =========================================================================
# MAIN FUNCTION
# =========================================================================

async def your_agent_function(input_data: str) -> YourOutputModel:
    """
    Main function to run your agent.

    Args:
        input_data: Input for the agent

    Returns:
        Structured output from the agent
    """
    logger.info(f"Running your agent with input: {len(input_data)} characters")
    try:
        agent = get_your_agent()
        result = await agent.run(input_data)
        logger.info("Agent execution completed successfully")
        return result.output
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise
```

### Agent with Dependencies

For agents that need external dependencies:

```python
# agents/agent_with_deps.py
"""
AI Agent with dependencies.
"""

from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from typing import Optional

@dataclass
class AgentDependencies:
    """Dependencies for the agent."""
    api_key: str
    database_url: str
    http_client: Optional[Any] = None

def get_agent_with_deps() -> Agent[AgentDependencies, YourOutputModel]:
    """Create agent with dependencies."""

    @agent.tool
    async def fetch_data(ctx: RunContext[AgentDependencies], query: str) -> str:
        """Fetch data using dependencies."""
        # Use ctx.deps to access dependencies
        async with ctx.deps.http_client.get(f"{ctx.deps.database_url}/query?q={query}") as response:
            return await response.text()

    return Agent(
        model=model_provider.get_model("openai:gpt-4o"),
        deps_type=AgentDependencies,
        tools=[fetch_data],
        system_prompt="You are an agent with access to external data.",
        output_type=YourOutputModel,
    )

# Usage
async def run_agent_with_deps(input_text: str) -> YourOutputModel:
    deps = AgentDependencies(
        api_key="your-api-key",
        database_url="https://api.example.com",
        http_client=httpx.AsyncClient()
    )

    agent = get_agent_with_deps()
    result = await agent.run(input_text, deps=deps)
    return result.output
```

---

## Agent Configuration

### Configuration Settings

Add agent-specific settings to your config:

```python
# config/settings.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Agent Models
    er_extractor_agent_model: str = "openai:gpt-4o-mini"
    your_agent_model: str = "anthropic:claude-3-5-haiku"

    # Agent Settings
    agent_temperature: float = 0.3
    agent_max_retries: int = 2
```

### Environment-Specific Configuration

```python
# config/settings.py
class Settings(BaseSettings):
    environment: str = Field(default="development")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def agent_model(self) -> str:
        """Select model based on environment."""
        if self.is_production:
            return "openai:gpt-4o"  # More expensive but better
        else:
            return "openai:gpt-4o-mini"  # Cheaper for development
```

---

## Usage Examples

### Basic Agent Usage

```python
# example_usage.py
import asyncio
from agents.your_agent import your_agent_function

async def main():
    result = await your_agent_function("Process this text")
    print(f"Result: {result.result}")
    print(f"Confidence: {result.confidence}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Agent with Custom Configuration

```python
# custom_agent_usage.py
from pydantic_ai import Agent
from services.llm_model_provider import model_provider

# Create agent with custom settings
agent = Agent(
    model=model_provider.get_model("anthropic:claude-3-5-sonnet"),
    system_prompt="You are a creative writing assistant.",
    model_settings={
        "temperature": 0.8,  # More creative
        "max_tokens": 1000
    },
    retries=3
)

async def creative_task():
    result = await agent.run("Write a short story about AI")
    print(result.output)
```

### Multiple Agents Coordination

```python
# multi_agent_example.py
from agents.er_extractor import extract_entities_and_relationships
from agents.your_agent import your_agent_function

async def process_document(content: str):
    """Process a document with multiple agents."""

    # First, extract entities
    entities = await extract_entities_and_relationships(content)

    # Then, analyze with another agent
    analysis_prompt = f"Analyze this content with entities: {entities.entities}"
    analysis = await your_agent_function(analysis_prompt)

    return {
        "entities": entities,
        "analysis": analysis
    }
```

---

## Best Practices

### 1. Error Handling

```python
# agents/your_agent.py
async def your_agent_function(input_data: str) -> YourOutputModel:
    try:
        agent = get_your_agent()
        result = await agent.run(input_data)
        return result.output
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        # Return a default response or re-raise
        raise
```

### 2. Logging

```python
# agents/your_agent.py
async def your_agent_function(input_data: str) -> YourOutputModel:
    logger.info(f"Processing input: {len(input_data)} characters")

    start_time = time.time()
    try:
        agent = get_your_agent()
        result = await agent.run(input_data)

        duration = time.time() - start_time
        logger.info(f"Agent completed in {duration:.2f}s")

        return result.output
    except Exception as e:
        logger.error(f"Agent failed after {time.time() - start_time:.2f}s: {e}")
        raise
```

### 3. Testing

```python
# tests/test_your_agent.py
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from agents.your_agent import get_your_agent

# Disable real API calls in tests
models.ALLOW_MODEL_REQUESTS = False

@pytest.mark.asyncio
async def test_your_agent():
    agent = get_your_agent()

    # Override with test model
    test_model = TestModel(custom_result_json={
        "result": "test result",
        "confidence": 0.9
    })

    with agent.override(model=test_model):
        result = await agent.run("test input")
        assert result.output.result == "test result"
        assert result.output.confidence == 0.9
```

### 4. Configuration Management

```python
# agents/your_agent.py
def get_your_agent() -> Agent[None, YourOutputModel]:
    model = model_provider.get_model(settings.your_agent_model)

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        output_type=YourOutputModel,
        model_settings={
            "temperature": settings.agent_temperature,
            "max_tokens": settings.agent_max_tokens
        },
        retries=settings.agent_max_retries,
    )
```

### 5. Dependency Injection

```python
# agents/agent_with_deps.py
@dataclass
class AgentDeps:
    http_client: httpx.AsyncClient
    cache: Redis
    database: DatabaseConnection

def get_agent_with_deps() -> Agent[AgentDeps, OutputType]:
    # Agent that uses external services
    return Agent(
        model=model_provider.get_model("openai:gpt-4o"),
        deps_type=AgentDeps,
        # ... other config
    )
```

### 6. Structured Outputs

Always use Pydantic models for outputs:

```python
# agents/your_agent.py
class StructuredOutput(BaseModel):
    """Well-defined output structure."""
    summary: str = Field(description="Brief summary")
    keywords: List[str] = Field(description="Key terms")
    sentiment: float = Field(ge=-1.0, le=1.0, description="Sentiment score")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
```

### 7. System Prompt Best Practices

```python
# agents/your_agent.py
SYSTEM_PROMPT = """You are a specialized assistant.

**Role:** [Clear role definition]

**Guidelines:**
1. [Specific guideline 1]
2. [Specific guideline 2]
3. [Specific guideline 3]

**Output Format:** [Describe expected output structure]

**Constraints:**
- [Any limitations or requirements]
- [Quality standards]

**Examples:**
Input: [Example input]
Output: [Example output]
"""
```

---

## Conclusion

This guide provides a comprehensive approach to integrating Pydantic AI into your project. The key components are:

1. **Model Provider**: Centralized model management across providers
2. **Agent Factory Functions**: Consistent agent creation patterns
3. **Configuration Management**: Environment-based settings
4. **Structured Outputs**: Type-safe responses with Pydantic
5. **Error Handling**: Robust error management and logging
6. **Testing**: Comprehensive test coverage with test models

Following these patterns will help you build maintainable, testable, and production-ready AI agents with Pydantic AI.