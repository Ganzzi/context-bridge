"""
AI agent for generating contextual summaries of chunks.

This module provides the ContextGenerationAgent that uses pydantic-ai to generate
contextual summaries for document chunks. These contexts improve search retrieval
accuracy by situating each chunk within its document context.

Features:
- Prompt caching for cost efficiency (same document context reused)
- Batch processing for multiple chunks
- Error handling and graceful degradation
- Support for multiple LLM providers (Anthropic, OpenAI)
"""

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from context_bridge.config import Config
from context_bridge.service.llm_model_provider import ModelProvider

logger = logging.getLogger(__name__)


class ChunkContext(BaseModel):
    """Output model for chunk context generation."""

    context: str = Field(description="Succinct context situating the chunk within the document")


# System prompt template
CONTEXT_GENERATION_SYSTEM_PROMPT = """You are an AI assistant specialized in providing contextual summaries for document chunks to improve search retrieval accuracy.

**Your Task:**
Given a complete document and a specific chunk from that document, generate a SHORT and SUCCINCT context (2-3 sentences maximum) that:
1. Situates the chunk within the overall document structure
2. Explains what the chunk is about in relation to the whole document
3. Mentions key concepts or topics that would help with semantic search
4. Is written in a way that improves search retrieval

**Important Guidelines:**
- Keep the context concise (2-3 sentences)
- Focus on improving search relevance
- Mention the document structure (e.g., "This chunk from the API Reference section...")
- Include key terms that would be searched for
- Do NOT summarize the chunk itself, provide CONTEXT for it
- Answer ONLY with the context, nothing else

**Complete Document:**
{document_content}
"""

USER_PROMPT_TEMPLATE = """Here is the chunk we want to situate within the whole document:

<chunk>
{chunk_content}
</chunk>

Please provide a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""


class ContextGenerationAgent:
    """Agent for generating contextual information for chunks using AI."""

    def __init__(self, config: Config):
        """
        Initialize the context generation agent.

        Args:
            config: Configuration object with AI settings
        """
        self.config = config

        # Set up model provider with API keys from config
        api_keys = {}
        if config.anthropic_api_key:
            api_keys["anthropic"] = config.anthropic_api_key
        if config.openai_api_key:
            api_keys["openai"] = config.openai_api_key

        self.model_provider = ModelProvider(api_keys)

        # Cache agent and document content for prompt caching efficiency
        self._agent: Optional[Agent] = None
        self._current_document: Optional[str] = None

        logger.debug("ContextGenerationAgent initialized")

    def _create_agent(self, document_content: str) -> Agent:
        """
        Create an agent with document content in system prompt.

        This enables prompt caching for cost efficiency - the document content
        is cached on the LLM provider's side for reuse across multiple requests.

        Args:
            document_content: The complete document text

        Returns:
            Configured pydantic-ai Agent instance
        """
        model = self.model_provider.get_model(self.config.context_agent_model)

        system_prompt = CONTEXT_GENERATION_SYSTEM_PROMPT.format(document_content=document_content)

        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            result_type=ChunkContext,
            model_settings={
                "temperature": self.config.context_agent_temperature,
                "max_tokens": self.config.context_agent_max_tokens,
            },
        )

        logger.debug(
            f"Created new agent for context generation "
            f"(model={self.config.context_agent_model})"
        )
        return agent

    async def generate_context(
        self,
        chunk_content: str,
        document_content: str,
    ) -> str:
        """
        Generate context for a chunk within its document.

        The agent is cached per document to enable prompt caching on the
        LLM provider side, reducing costs for multiple chunks from the same document.

        Args:
            chunk_content: The chunk text to generate context for
            document_content: The complete document content for context

        Returns:
            Generated context string (2-3 sentences), or empty string on error
        """
        # Create agent if needed or document changed
        if self._agent is None or self._current_document != document_content:
            logger.debug("Creating new context agent with updated system prompt")
            self._agent = self._create_agent(document_content)
            self._current_document = document_content

        # Generate context
        user_prompt = USER_PROMPT_TEMPLATE.format(chunk_content=chunk_content)

        try:
            result = await self._agent.run(user_prompt)
            context = result.data.context

            logger.debug(f"Generated context: {context[:100]}...")
            return context

        except Exception as e:
            logger.error(f"Failed to generate context: {e}", exc_info=True)
            # Return empty context on failure - search will still work
            return ""

    async def generate_contexts_batch(
        self,
        chunks: list[str],
        document_content: str,
    ) -> list[str]:
        """
        Generate contexts for multiple chunks in batch.

        Processes chunks concurrently for efficiency. The agent is reused
        across all chunks to maximize prompt caching benefits.

        Args:
            chunks: List of chunk texts to generate contexts for
            document_content: The complete document content

        Returns:
            List of generated contexts in same order as input.
            Failed chunks return empty strings.

        Note:
            - Concurrent processing is handled via asyncio.gather
            - Individual chunk failures don't block others
            - Returns empty string for failed chunks
        """
        if not chunks:
            logger.warning("Empty chunks list provided to generate_contexts_batch")
            return []

        logger.info(
            f"Generating contexts for {len(chunks)} chunks "
            f"(batch_size={self.config.context_batch_size})"
        )

        # Generate contexts concurrently
        tasks = [self.generate_context(chunk, document_content) for chunk in chunks]

        contexts = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions and format results
        result = []
        failed_count = 0
        for i, ctx in enumerate(contexts):
            if isinstance(ctx, Exception):
                logger.error(f"Failed to generate context for chunk {i}: {ctx}")
                result.append("")
                failed_count += 1
            else:
                result.append(ctx)

        if failed_count > 0:
            logger.warning(f"Failed to generate {failed_count}/{len(chunks)} contexts")
        else:
            logger.info(f"Successfully generated {len(chunks)} contexts")

        return result
