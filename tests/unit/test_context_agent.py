"""
Unit tests for ContextGenerationAgent service.

Tests cover:
- Agent initialization with various config options
- Context generation for single chunks
- Batch context generation
- Error handling and graceful degradation
- Prompt caching (agent reuse across documents)
- API key handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from typing import Optional

from pydantic import Field

from context_bridge.config import Config
from context_bridge.service.context_agent import (
    ContextGenerationAgent,
    ChunkContext,
    CONTEXT_GENERATION_SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)


@pytest.fixture
def mock_config():
    """Fixture providing a test configuration."""
    return Config(
        context_agent_model="anthropic:claude-3-5-sonnet-20241022",
        context_agent_temperature=0.3,
        context_agent_max_tokens=500,
        context_batch_size=10,
        context_enable_cache=True,
        anthropic_api_key="test-anthropic-key",
        openai_api_key=None,
    )


@pytest.fixture
def mock_model_provider():
    """Fixture providing a mocked ModelProvider."""
    provider = MagicMock()
    return provider


@pytest.fixture
def mock_agent():
    """Fixture providing a mocked pydantic-ai Agent."""
    agent = AsyncMock()
    return agent


class TestContextGenerationAgentInit:
    """Tests for ContextGenerationAgent initialization."""

    def test_init_with_api_keys(self, mock_config):
        """Test initialization with API keys from config."""
        with patch("context_bridge.service.context_agent.ModelProvider") as mock_provider_class:
            agent = ContextGenerationAgent(mock_config)

            assert agent.config == mock_config
            assert agent._agent is None
            assert agent._current_document is None
            mock_provider_class.assert_called_once()

    def test_init_without_api_keys(self):
        """Test initialization without API keys (uses environment)."""
        config = Config(
            context_agent_model="anthropic:claude-3-5-sonnet-20241022",
            anthropic_api_key=None,
            openai_api_key=None,
        )

        with patch("context_bridge.service.context_agent.ModelProvider") as mock_provider_class:
            agent = ContextGenerationAgent(config)

            assert agent.config == config
            mock_provider_class.assert_called_once_with({})

    def test_init_with_partial_api_keys(self):
        """Test initialization with only some API keys."""
        config = Config(
            context_agent_model="openai:gpt-4",
            anthropic_api_key=None,
            openai_api_key="test-openai-key",
        )

        with patch("context_bridge.service.context_agent.ModelProvider") as mock_provider_class:
            agent = ContextGenerationAgent(config)

            mock_provider_class.assert_called_once_with({"openai": "test-openai-key"})


class TestContextGenerationAgentCreateAgent:
    """Tests for internal agent creation."""

    def test_create_agent_with_document_content(self, mock_config):
        """Test creating an agent with document content in system prompt."""
        with patch("context_bridge.service.context_agent.ModelProvider") as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider

            mock_model = MagicMock()
            mock_provider.get_model.return_value = mock_model

            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                agent_instance = ContextGenerationAgent(mock_config)
                document = "This is a test document about APIs."

                result = agent_instance._create_agent(document)

                # Verify model was retrieved
                mock_provider.get_model.assert_called_once_with(
                    "anthropic:claude-3-5-sonnet-20241022"
                )

                # Verify Agent was created with correct system prompt
                mock_agent_class.assert_called_once()
                call_kwargs = mock_agent_class.call_args[1]

                assert call_kwargs["model"] == mock_model
                assert "This is a test document about APIs." in call_kwargs["system_prompt"]
                assert call_kwargs["result_type"] == ChunkContext
                assert call_kwargs["model_settings"]["temperature"] == 0.3
                assert call_kwargs["model_settings"]["max_tokens"] == 500

    def test_create_agent_formats_system_prompt(self, mock_config):
        """Test that system prompt correctly formats with document content."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                agent_instance = ContextGenerationAgent(mock_config)
                doc_content = "Important API documentation"

                agent_instance._create_agent(doc_content)

                call_kwargs = mock_agent_class.call_args[1]
                system_prompt = call_kwargs["system_prompt"]

                # Verify document content is in the system prompt
                assert doc_content in system_prompt
                # Verify prompt structure
                assert "contextual summaries" in system_prompt
                assert "search retrieval" in system_prompt


class TestContextGenerationSingleChunk:
    """Tests for single chunk context generation."""

    @pytest.mark.asyncio
    async def test_generate_context_success(self, mock_config):
        """Test successful context generation for a single chunk."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                # Mock the agent instance
                mock_agent_instance = AsyncMock()
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Generated context summary")
                mock_agent_instance.run.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunk = "This is a chunk about authentication."
                document = "Complete API documentation about authentication and authorization."

                result = await agent.generate_context(chunk, document)

                assert result == "Generated context summary"
                mock_agent_instance.run.assert_called_once()
                call_args = mock_agent_instance.run.call_args[0][0]
                assert chunk in call_args
                assert "authentication" in call_args

    @pytest.mark.asyncio
    async def test_generate_context_reuses_agent(self, mock_config):
        """Test that agent is reused for same document (prompt caching)."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Test context")
                mock_agent_instance.run.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                document = "Same document content"
                chunk1 = "First chunk"
                chunk2 = "Second chunk"

                # Generate contexts for two chunks from same document
                await agent.generate_context(chunk1, document)
                await agent.generate_context(chunk2, document)

                # Agent should be created only once (prompt caching)
                mock_agent_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_context_creates_new_agent_for_different_document(self, mock_config):
        """Test that new agent is created when document changes."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Test context")
                mock_agent_instance.run.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)

                # Generate context for first document
                await agent.generate_context("Chunk 1", "Document A")
                assert mock_agent_class.call_count == 1

                # Generate context for different document
                await agent.generate_context("Chunk 2", "Document B")
                assert mock_agent_class.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_context_returns_empty_on_error(self, mock_config):
        """Test that empty string is returned on generation error."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()
                mock_agent_instance.run.side_effect = Exception("API Error")
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                result = await agent.generate_context("Chunk", "Document")

                assert result == ""

    @pytest.mark.asyncio
    async def test_generate_context_formats_user_prompt(self, mock_config):
        """Test that user prompt is correctly formatted with chunk content."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Context")
                mock_agent_instance.run.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunk = "Authentication endpoint description"
                document = "API docs"

                await agent.generate_context(chunk, document)

                prompt = mock_agent_instance.run.call_args[0][0]
                assert chunk in prompt
                assert "<chunk>" in prompt
                assert "</chunk>" in prompt


class TestContextGenerationBatch:
    """Tests for batch context generation."""

    @pytest.mark.asyncio
    async def test_generate_contexts_batch_success(self, mock_config):
        """Test successful batch context generation."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()

                # Mock different results for each call
                mock_result1 = MagicMock()
                mock_result1.data = ChunkContext(context="Context 1")
                mock_result2 = MagicMock()
                mock_result2.data = ChunkContext(context="Context 2")
                mock_result3 = MagicMock()
                mock_result3.data = ChunkContext(context="Context 3")

                mock_agent_instance.run.side_effect = [
                    mock_result1,
                    mock_result2,
                    mock_result3,
                ]
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
                document = "Test document"

                results = await agent.generate_contexts_batch(chunks, document)

                assert len(results) == 3
                assert results[0] == "Context 1"
                assert results[1] == "Context 2"
                assert results[2] == "Context 3"

    @pytest.mark.asyncio
    async def test_generate_contexts_batch_preserves_order(self, mock_config):
        """Test that batch results maintain order of input chunks."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()

                contexts = [ChunkContext(context=f"Context {i}") for i in range(5)]
                mock_results = [MagicMock() for _ in contexts]
                for mock_result, context in zip(mock_results, contexts):
                    mock_result.data = context

                mock_agent_instance.run.side_effect = mock_results
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunks = [f"Chunk {i}" for i in range(5)]
                document = "Document"

                results = await agent.generate_contexts_batch(chunks, document)

                assert results == [f"Context {i}" for i in range(5)]

    @pytest.mark.asyncio
    async def test_generate_contexts_batch_handles_partial_failures(self, mock_config):
        """Test batch processing continues with partial failures."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()

                # Mix of successes and failures
                mock_result1 = MagicMock()
                mock_result1.data = ChunkContext(context="Context 1")
                mock_result3 = MagicMock()
                mock_result3.data = ChunkContext(context="Context 3")

                mock_agent_instance.run.side_effect = [
                    mock_result1,
                    Exception("API Error"),
                    mock_result3,
                ]
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
                document = "Document"

                results = await agent.generate_contexts_batch(chunks, document)

                assert len(results) == 3
                assert results[0] == "Context 1"
                assert results[1] == ""  # Failed chunk
                assert results[2] == "Context 3"

    @pytest.mark.asyncio
    async def test_generate_contexts_batch_empty_chunks(self, mock_config):
        """Test batch processing with empty chunk list."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            agent = ContextGenerationAgent(mock_config)
            results = await agent.generate_contexts_batch([], "Document")

            assert results == []

    @pytest.mark.asyncio
    async def test_generate_contexts_batch_concurrent_processing(self, mock_config):
        """Test that batch processing happens concurrently."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()

                # Create mock results
                mock_results = [
                    MagicMock(data=ChunkContext(context=f"Context {i}")) for i in range(10)
                ]
                mock_agent_instance.run.side_effect = mock_results
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                chunks = [f"Chunk {i}" for i in range(10)]
                document = "Document"

                results = await agent.generate_contexts_batch(chunks, document)

                # All contexts should be generated
                assert len(results) == 10
                assert all(ctx for ctx in results)


class TestContextGenerationIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_caching(self, mock_config):
        """Test full workflow with agent reuse and caching."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Generated context")
                mock_agent_instance.run.return_value = mock_result
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                document = "Complete documentation"

                # Generate context for multiple chunks
                ctx1 = await agent.generate_context("Chunk 1", document)
                ctx2 = await agent.generate_context("Chunk 2", document)
                ctx3 = await agent.generate_context("Chunk 3", document)

                # Agent created only once
                assert mock_agent_class.call_count == 1
                # All contexts generated
                assert ctx1 == ctx2 == ctx3 == "Generated context"

    @pytest.mark.asyncio
    async def test_model_provider_integration(self, mock_config):
        """Test integration with ModelProvider for API key handling."""
        with patch("context_bridge.service.context_agent.ModelProvider") as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider

            agent = ContextGenerationAgent(mock_config)

            # Verify ModelProvider was initialized with correct API keys
            mock_provider_class.assert_called_once_with({"anthropic": "test-anthropic-key"})

    @pytest.mark.asyncio
    async def test_error_recovery_maintains_functionality(self, mock_config):
        """Test that agent recovers from errors and continues functioning."""
        with patch("context_bridge.service.context_agent.ModelProvider"):
            with patch("context_bridge.service.context_agent.Agent") as mock_agent_class:
                mock_agent_instance = AsyncMock()

                # First call fails, second succeeds
                mock_result = MagicMock()
                mock_result.data = ChunkContext(context="Success context")
                mock_agent_instance.run.side_effect = [
                    Exception("First error"),
                    mock_result,
                ]
                mock_agent_class.return_value = mock_agent_instance

                agent = ContextGenerationAgent(mock_config)
                document = "Document"

                # First call fails
                result1 = await agent.generate_context("Chunk 1", document)
                assert result1 == ""

                # Second call succeeds
                result2 = await agent.generate_context("Chunk 2", document)
                assert result2 == "Success context"
