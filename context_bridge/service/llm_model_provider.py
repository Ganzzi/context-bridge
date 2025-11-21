"""LLM Model provider for AI context generation.

This module provides a unified interface for instantiating LLM models from
different providers (Anthropic, OpenAI) using the pydantic-ai library.
"""

import logging
import os
from typing import Dict, Optional

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel

logger = logging.getLogger(__name__)


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
    }

    # Environment variable names for API keys
    API_KEY_ENV_VARS = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """Initialize the model provider.

        Args:
            api_keys: Dictionary mapping provider names to API keys.
                     If not provided, will fall back to environment variables.
        """
        self.api_keys = api_keys or {}
        logger.debug(f"ModelProvider initialized with {len(self.api_keys)} API keys")

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
        try:
            provider_name, model_name = model_info.split(":", 1)
        except ValueError:
            raise ValueError(
                f"Invalid model_info format: '{model_info}'. "
                f"Expected format: 'provider:model_name' "
                f"(e.g., 'anthropic:claude-3-5-sonnet-20241022')"
            )

        provider_name = provider_name.strip().lower()

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
