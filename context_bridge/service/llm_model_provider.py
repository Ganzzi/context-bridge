"""LLM Model provider for AI context generation.

This module provides a unified interface for instantiating LLM models from
different providers (Anthropic, OpenAI) using the pydantic-ai library.
"""

import logging
import os
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, TypedDict

from pydantic_ai.usage import RunUsage
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.google import GoogleModel

logger = logging.getLogger(__name__)


class LLMChatResult(TypedDict, total=False):
    """Normalized response payload for injected executor chat calls."""

    text: str
    usage: Dict[str, int]
    provider_response_id: Optional[str]


LLMExecutor = Callable[
    [str, list[dict[str, Any]], Optional[dict[str, Any]], dict[str, Any]],
    Awaitable[LLMChatResult],
]


@dataclass
class ExecutorRunResult:
    """Lightweight run result shim compatible with existing call sites."""

    output: Any
    _usage: RunUsage

    def usage(self) -> RunUsage:
        return self._usage


class ModelProvider:
    """Provides LLM model instances for context generation.

    Supports multiple model providers through a unified interface.
    Uses the "provider:model_name" format for model specification.

    API keys are resolved in this order:
    1. From api_keys dict passed to constructor
    2. From environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY)

    Example:
        ```python
        provider = ModelProvider(api_keys={
            "anthropic": "sk-ant-...",
            "openai": "sk-..."
        })

        # Get Claude model
        model = provider.get_model("anthropic:claude-3-5-sonnet-20241022")

        # Get GPT model
        model = provider.get_model("openai:gpt-4")
        ```
    """

    PROVIDER_MODEL_MAPPING = {
        "openai": OpenAIChatModel,
        "anthropic": AnthropicModel,
        "google": GoogleModel,
        "grok": OpenAIChatModel,  # Grok uses OpenAI-compatible API
    }

    # Environment variable names for API keys
    API_KEY_ENV_VARS = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "grok": "GROK_API_KEY",
    }

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        executor: Optional[LLMExecutor] = None,
        backend_mode: bool = False,
    ):
        """Initialize the model provider.

        Args:
            api_keys: Dictionary mapping provider names to API keys.
                     If not provided, will fall back to environment variables.
        """
        self.api_keys = api_keys or {}
        self._executor = executor
        self._backend_mode = backend_mode
        logger.debug(f"ModelProvider initialized with {len(self.api_keys)} API keys")

    def set_executor(self, executor: Optional[LLMExecutor]) -> None:
        """Set or clear the injected LLM executor."""
        self._executor = executor

    def set_backend_mode(self, enabled: bool) -> None:
        """Enable/disable strict backend mode for provider initialization."""
        self._backend_mode = enabled

    def _get_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key for a provider, checking both dict and environment.

        Args:
            provider_name: Name of the provider (e.g., 'anthropic', 'openai')

        Returns:
            API key string or None if not found
        """
        # First check provided api_keys dict
        if provider_name in self.api_keys:
            return self.api_keys[provider_name]

        # Then check environment variables
        env_var = self.API_KEY_ENV_VARS.get(provider_name)
        if env_var:
            return os.getenv(env_var)

        return None

    def get_model(self, model_info: str) -> Model:
        """Get a model instance from provider:model_name format.

        Args:
            model_info: Model specification in format "provider:model_name"
                       Examples:
                       - "anthropic:claude-3-5-sonnet-20241022"
                       - "openai:gpt-4"

        Returns:
            Model instance ready for use

        Raises:
            ValueError: If provider is not supported or model_info format is invalid

        Example:
            ```python
            provider = ModelProvider(api_keys={"anthropic": "sk-ant-..."})
            model = provider.get_model("anthropic:claude-3-5-sonnet-20241022")
            ```
        """
        if self._backend_mode and self._executor is None:
            raise RuntimeError("No LLM executor injected. Backend mode requires queue executor.")

        try:
            provider_name, model_name = model_info.split(":", 1)
        except ValueError:
            raise ValueError(
                f"Invalid model_info format: '{model_info}'. "
                f"Expected format: 'provider:model_name' "
                f"(e.g., 'anthropic:claude-3-5-sonnet-20241022')"
            )

        provider_name = provider_name.strip().lower()

        # Keep compatibility with current runtime contract: only Anthropic/OpenAI
        # are enabled for model construction in this codepath.
        if provider_name in {"google", "grok"}:
            raise ValueError(f"Unsupported provider: '{provider_name}'")

        model_class = self.PROVIDER_MODEL_MAPPING.get(provider_name)
        if not model_class:
            supported = ", ".join(self.PROVIDER_MODEL_MAPPING.keys())
            raise ValueError(
                f"Unsupported provider: '{provider_name}'. " f"Supported providers: {supported}"
            )

        try:
            logger.debug(
                f"Creating {provider_name} model '{model_name}' "
                f"(API key from {'config' if provider_name in self.api_keys else 'environment'})"
            )

            # pydantic-ai models load API keys from environment variables
            # If we have a key in our dict, set it temporarily
            api_key = self._get_api_key(provider_name)
            old_env_value = None
            env_var_name = self.API_KEY_ENV_VARS.get(provider_name)

            try:
                if api_key and env_var_name:
                    # Temporarily set environment variable
                    old_env_value = os.environ.get(env_var_name)
                    os.environ[env_var_name] = api_key

                # Create model instance (pydantic-ai reads from env)
                return model_class(model_name)
            finally:
                # Restore original environment variable if we modified it
                if env_var_name and old_env_value is not None:
                    os.environ[env_var_name] = old_env_value
                elif env_var_name and old_env_value is None and api_key:
                    # Clean up if we added a new env var
                    os.environ.pop(env_var_name, None)

        except Exception as e:
            logger.error(f"Failed to create {provider_name} model '{model_name}': {e}")
            raise

    async def run_agent(
        self,
        agent: Any,
        user_prompt: str,
        *,
        deps: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        model_info: Optional[str] = None,
        model_settings: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Execute agent call through injected executor when configured.

        Falls back to native `agent.run(...)` when no executor is injected.
        """
        if self._executor is None:
            return await agent.run(user_prompt=user_prompt, deps=deps)

        payload = await self._executor(
            model_info or "unknown:model",
            [{"role": "user", "content": user_prompt}],
            model_settings,
            metadata or {},
        )

        text = payload.get("text", "")
        output = self._parse_output(agent, text)
        usage = self._usage_from_payload(payload.get("usage", {}))
        return ExecutorRunResult(output=output, _usage=usage)

    def _parse_output(self, agent: Any, text: str) -> Any:
        """Parse executor text response into the agent output type."""
        output_type = getattr(agent, "output_type", None)
        if output_type is None:
            return text

        if output_type is str:
            return text

        if hasattr(output_type, "model_validate_json"):
            try:
                return output_type.model_validate_json(text)
            except Exception:
                try:
                    return output_type.model_validate(json.loads(text))
                except Exception as exc:
                    raise RuntimeError(f"Failed to parse executor response for {output_type}: {exc}") from exc

        return text

    @staticmethod
    def _usage_from_payload(usage_payload: Dict[str, Any]) -> RunUsage:
        """Create RunUsage from executor usage payload with safe defaults."""
        return RunUsage(
            requests=1,
            input_tokens=int(usage_payload.get("input_tokens", 0) or 0),
            output_tokens=int(usage_payload.get("output_tokens", 0) or 0),
            cache_write_tokens=int(usage_payload.get("cache_write_tokens", 0) or 0),
            cache_read_tokens=int(usage_payload.get("cache_read_tokens", 0) or 0),
        )

    def supports_provider(self, provider_name: str) -> bool:
        """Check if a provider is supported.

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if provider is supported, False otherwise
        """
        return provider_name.lower() in self.PROVIDER_MODEL_MAPPING

    def get_supported_providers(self) -> list[str]:
        """Get list of supported providers.

        Returns:
            List of supported provider names
        """
        return list(self.PROVIDER_MODEL_MAPPING.keys())
