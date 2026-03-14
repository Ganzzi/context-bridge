"""Unit tests for LLM model provider."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from context_bridge.service.llm_model_provider import ModelProvider


class TestModelProvider:
    """Test suite for ModelProvider class."""

    def test_init_with_api_keys(self):
        """Test ModelProvider initialization with API keys."""
        api_keys = {"anthropic": "sk-ant-test123", "openai": "sk-test123"}
        provider = ModelProvider(api_keys=api_keys)
        assert provider.api_keys == api_keys

    def test_init_without_api_keys(self):
        """Test ModelProvider initialization without API keys."""
        provider = ModelProvider()
        assert provider.api_keys == {}

    def test_supports_provider_anthropic(self):
        """Test that Anthropic provider is supported."""
        provider = ModelProvider()
        assert provider.supports_provider("anthropic") is True
        assert provider.supports_provider("Anthropic") is True
        assert provider.supports_provider("ANTHROPIC") is True

    def test_supports_provider_openai(self):
        """Test that OpenAI provider is supported."""
        provider = ModelProvider()
        assert provider.supports_provider("openai") is True
        assert provider.supports_provider("OpenAI") is True
        assert provider.supports_provider("OPENAI") is True

    def test_supports_provider_unsupported(self):
        """Test that unsupported providers return False."""
        provider = ModelProvider()
        assert provider.supports_provider("bedrock") is False

    def test_get_supported_providers(self):
        """Test getting list of supported providers."""
        provider = ModelProvider()
        supported = provider.get_supported_providers()
        assert "openai" in supported
        assert "anthropic" in supported
        assert "google" in supported
        assert "grok" in supported

    def test_get_api_key_from_dict(self):
        """Test retrieving API key from provided dict."""
        api_keys = {"anthropic": "test-key-123"}
        provider = ModelProvider(api_keys=api_keys)
        assert provider._get_api_key("anthropic") == "test-key-123"

    def test_get_api_key_from_environment(self):
        """Test retrieving API key from environment variable."""
        provider = ModelProvider()

        # Set environment variable
        os.environ["ANTHROPIC_API_KEY"] = "env-key-456"
        try:
            assert provider._get_api_key("anthropic") == "env-key-456"
        finally:
            # Clean up
            del os.environ["ANTHROPIC_API_KEY"]

    def test_get_api_key_prefers_dict_over_environment(self):
        """Test that dict keys are preferred over environment variables."""
        api_keys = {"anthropic": "dict-key"}
        provider = ModelProvider(api_keys=api_keys)

        os.environ["ANTHROPIC_API_KEY"] = "env-key"
        try:
            assert provider._get_api_key("anthropic") == "dict-key"
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    def test_get_api_key_not_found(self):
        """Test that None is returned when API key not found."""
        provider = ModelProvider()
        # Clean environment first
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = provider._get_api_key("anthropic")
        assert result is None

    def test_get_model_invalid_format_no_colon(self):
        """Test get_model with invalid format (no colon)."""
        provider = ModelProvider(api_keys={"anthropic": "test-key"})
        with pytest.raises(ValueError) as exc_info:
            provider.get_model("anthropic")
        assert "Invalid model_info format" in str(exc_info.value)
        assert "provider:model_name" in str(exc_info.value)

    def test_get_model_unsupported_provider(self):
        """Test get_model with unsupported provider."""
        provider = ModelProvider()
        with pytest.raises(ValueError) as exc_info:
            provider.get_model("google:model-123")
        assert "Unsupported provider" in str(exc_info.value)
        assert "google" in str(exc_info.value)

    def test_get_model_model_name_parsing(self):
        """Test that model names are parsed correctly."""
        provider = ModelProvider(api_keys={"anthropic": "test-key"})

        # Test with colons in model name (should work with split limit=1)
        # This will fail at pydantic_ai level but should parse correctly
        try:
            provider.get_model("anthropic:claude-3-5-sonnet:test")
        except Exception as e:
            # Should not be format error
            assert "Invalid model_info format" not in str(e)

    def test_get_model_backend_mode_requires_executor(self):
        """Test backend mode hard-fails when executor is missing."""
        provider = ModelProvider(backend_mode=True)
        with pytest.raises(RuntimeError) as exc_info:
            provider.get_model("anthropic:claude-3-5-sonnet-20241022")
        assert "No LLM executor injected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_agent_uses_injected_executor(self):
        """Test run_agent routes through injected executor when configured."""
        executor = AsyncMock(
            return_value={
                "text": "executor-response",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )
        provider = ModelProvider(executor=executor)
        mock_agent = MagicMock()
        mock_agent.output_type = str
        mock_agent.run = AsyncMock()

        result = await provider.run_agent(
            mock_agent,
            "hello",
            metadata={"source_component": "ctx_bridge", "operation": "context_generation"},
            model_info="anthropic:claude-3-5-sonnet-20241022",
            model_settings={"temperature": 0.3},
        )

        mock_agent.run.assert_not_called()
        executor.assert_awaited_once()
        assert result.output == "executor-response"
        assert result.usage().input_tokens == 10
        assert result.usage().output_tokens == 5


class TestModelProviderIntegration:
    """Integration tests for ModelProvider."""

    def test_provider_initialization_multiple_instances(self):
        """Test that multiple provider instances work independently."""
        provider1 = ModelProvider(api_keys={"anthropic": "key1"})
        provider2 = ModelProvider(api_keys={"openai": "key2"})

        assert provider1.api_keys == {"anthropic": "key1"}
        assert provider2.api_keys == {"openai": "key2"}

    def test_provider_supported_list_completeness(self):
        """Test that all expected providers are in supported list."""
        provider = ModelProvider()
        supported = provider.get_supported_providers()

        assert len(supported) >= 2
        assert "anthropic" in supported
        assert "openai" in supported

    def test_api_key_env_vars_mapping(self):
        """Test that environment variable names are correctly mapped."""
        provider = ModelProvider()

        # Verify mapping constants exist
        assert "anthropic" in provider.API_KEY_ENV_VARS
        assert "openai" in provider.API_KEY_ENV_VARS
        assert provider.API_KEY_ENV_VARS["anthropic"] == "ANTHROPIC_API_KEY"
        assert provider.API_KEY_ENV_VARS["openai"] == "OPENAI_API_KEY"
