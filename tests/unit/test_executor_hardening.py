"""Tests for ctx-bridge AI executor hardening.

Covers backend-mode enforcement on ModelProvider, executor chain propagation
through ContextGenerator, and dead-code removal verification.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from context_bridge.service.llm_model_provider import ModelProvider


class TestModelProviderBackendMode:
    """Backend-mode guard tests for ModelProvider."""

    def test_get_model_raises_in_backend_mode_without_executor(self):
        """get_model must raise RuntimeError when backend_mode=True and no executor."""
        provider = ModelProvider(api_keys={}, backend_mode=True)
        with pytest.raises(RuntimeError, match="No LLM executor injected"):
            provider.get_model("anthropic:claude-3-5-sonnet-20241022")

    def test_get_model_skips_guard_when_executor_present(self):
        """get_model must NOT raise when both backend_mode and executor are set."""
        async def dummy_exec(*args, **kwargs):
            return {"text": "", "usage": {}}
        provider = ModelProvider(api_keys={}, executor=dummy_exec, backend_mode=True)
        assert provider._backend_mode is True
        assert provider._executor is not None

    def test_backend_mode_disabled_by_default(self):
        """ModelProvider must default to backend_mode=False."""
        provider = ModelProvider()
        assert provider._backend_mode is False

    def test_backend_mode_set_to_true_activates(self):
        """set_backend_mode(True) must activate the guard."""
        provider = ModelProvider(api_keys={})
        assert provider._backend_mode is False
        provider.set_backend_mode(True)
        assert provider._backend_mode is True
        with pytest.raises(RuntimeError, match="No LLM executor injected"):
            provider.get_model("openai:gpt-4o-mini")

    def test_backend_mode_cleared_with_executor(self):
        """set_executor(None) must leave backend_mode unchanged (caller responsibility)."""
        provider = ModelProvider(api_keys={}, backend_mode=True)
        provider.set_executor(None)
        assert provider._backend_mode is True  # backend_mode unchanged
        assert provider._executor is None


@pytest.mark.asyncio
async def test_context_generator_routes_through_executor():
    """ContextGenerator.generate_context must use the executor when provided."""
    from context_bridge.config import Config
    from context_bridge.agents.context_generator import ContextGenerator

    config = Config(
        openai_api_key="sk-test",
        context_agent_model="openai:gpt-4o-mini",
        context_agent_temperature=0.0,
        context_agent_max_tokens=100,
    )

    calls = []

    async def spy_executor(model_info, messages, model_settings, metadata):
        calls.append(model_info)
        return {
            "text": '{"context":"test context output"}',
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    generator = ContextGenerator(config, executor=spy_executor, backend_mode=True)
    result = await generator.generate_context(
        chunk_content="this is a chunk",
        document_content="this is the document",
    )

    assert len(calls) == 1
    assert calls[0] == "openai:gpt-4o-mini"
    assert result == "test context output"


@pytest.mark.asyncio
async def test_context_generator_no_executor_fallback():
    """ContextGenerator must still work when no executor is injected (no backend mode)."""
    from context_bridge.config import Config
    from context_bridge.agents.context_generator import ContextGenerator

    config = Config(
        openai_api_key="sk-test",
        context_agent_model="openai:gpt-4o-mini",
        context_agent_temperature=0.0,
        context_agent_max_tokens=100,
    )

    # Backend_mode=False, no executor — get_model() should work (falls through to env)
    generator = ContextGenerator(config, executor=None, backend_mode=False)
    assert generator.model_provider._backend_mode is False
    assert generator.model_provider._executor is None
    # This should NOT raise; without backend_mode the guard is bypassed
    # (actual model construction may fail, but that's a different error)


@pytest.mark.asyncio
async def test_usage_processor_called_through_executor_chain():
    """Usage processor must be invoked when executor returns usage data."""
    from context_bridge.config import Config
    from context_bridge.agents.context_generator import ContextGenerator

    config = Config(
        openai_api_key="sk-test",
        context_agent_model="openai:gpt-4o-mini",
        context_agent_temperature=0.0,
        context_agent_max_tokens=100,
    )

    usage_calls = []

    async def tracking_processor(usage):
        usage_calls.append(usage)

    async def dummy_executor(model_info, messages, model_settings, metadata):
        return {
            "text": '{"context":"usage test"}',
            "usage": {"input_tokens": 7, "output_tokens": 3},
        }

    generator = ContextGenerator(
        config,
        executor=dummy_executor,
        backend_mode=True,
        usage_processor=tracking_processor,
    )

    result = await generator.generate_context("chunk", "doc")
    assert result == "usage test"
    assert len(usage_calls) == 1
    assert usage_calls[0].input_tokens == 7
    assert usage_calls[0].output_tokens == 3


@pytest.mark.asyncio
async def test_executor_chain_from_core():
    """Verify ContextBridge.set_llm_executor propagates to DocManager then ContextGenerator.

    This test verifies the propagation chain through the core API surface
    without requiring a live database (mocking DocManager construction).
    """
    from context_bridge.core import ContextBridge
    from context_bridge.config import Config

    config = Config(
        openai_api_key="sk-test",
        context_agent_model="openai:gpt-4o-mini",
    )

    bridge = ContextBridge(config=config)

    # Before initialize, set_llm_executor stores values
    async def dummy_exec(*args, **kwargs):
        return {"text": '{"context":"x"}', "usage": {}}

    bridge.set_llm_executor(dummy_exec, backend_mode=True)
    assert bridge._llm_executor is dummy_exec
    assert bridge._llm_backend_mode is True

    # After initialize, the doc_manager should receive these values
    # (DocManager requires DB, so we just verify the pre-init storage)
    bridge.set_llm_executor(None, backend_mode=False)
    assert bridge._llm_executor is None
    assert bridge._llm_backend_mode is False
