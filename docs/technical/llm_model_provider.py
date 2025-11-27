"""
Model provider module for mapping model names to pydantic-ai model instances.
This allows for flexible model selection by name across different providers.
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

from agent_reminiscence.config.settings import get_config

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

    Example:
        >>> provider = ModelProvider()
        >>> model = provider.get_model("o3-mini")
        >>> # Returns an OpenAIChatModel instance for gpt-3.5-turbo
    """

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the ModelProvider with optional API keys and model settings.

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
        config = get_config()
        api_keys = {}

        # Load API keys for each provider from config
        if config.openai_api_key:
            api_keys["openai"] = config.openai_api_key
        if config.anthropic_api_key:
            api_keys["anthropic"] = config.anthropic_api_key
        if config.google_api_key:
            api_keys["google"] = config.google_api_key
        if config.grok_api_key:
            api_keys["grok"] = config.grok_api_key

        return api_keys


model_provider = ModelProvider()


