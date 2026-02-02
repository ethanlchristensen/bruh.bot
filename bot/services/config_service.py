import logging
import os
from dataclasses import dataclass, field, fields
from typing import Literal, TypeVar, get_args, get_origin, Optional, List

import yaml

logger = logging.getLogger("bot.config")

T = TypeVar("T")


@dataclass
class OllamaConfig:
    endpoint: str = "localhost:11434"
    preferredModel: str = "llama3.1"


@dataclass
class OpenAIConfig:
    apiKey: str = ""
    preferredModel: str = "gpt-5-nano"


@dataclass
class AntropicConfig:
    apiKey: str = ""
    preferredModel: str = "claude-4-5-sonnet"


@dataclass
class GeminiConfig:
    apiKey: str = ""
    preferredModel: str = "gemini-2.5-flash"


@dataclass
class ElevenLabsConfig:
    apiKey: str = ""


@dataclass
class OrchestratorConfig:
    preferredAiProvider: Literal["ollama", "openai", "antropic", "gemini"] = "google"
    preferredModel: str = ""


@dataclass
class DeleteUserMessagesConfig:
    enabled: bool
    userIds: List[int] = []


@dataclass
class OpenAiRealTimeConfig:
    apiKey: str = ""
    realTimeModel: str = ""
    voice: str = "alloy"


@dataclass
class AIConfig:
    preferredAiProvider: Literal["ollama", "openai", "antropic", "gemini"] = "google"
    ollama: OllamaConfig | None = None
    openai: OpenAIConfig | None = None
    antropic: AntropicConfig | None = None
    gemini: GeminiConfig | None = None
    elevenlabs: ElevenLabsConfig | None = None
    orchestrator: OrchestratorConfig | None = None
    realTimeConfig: OpenAiRealTimeConfig | None = None
    boostImagePrompts: bool = False
    maxDailyImages: int = 1


@dataclass
class Config:
    environment: str = ""
    devDiscordToken: str = ""
    prodDiscordToken: str = ""
    adminIds: List[int] = field(default_factory=List)
    invisible: bool = False
    aiConfig: AIConfig = field(default_factory=AIConfig)
    usersToId: dict[str, str] = field(default_factory=dict)
    idToUsers: dict[str, str] = field(default_factory=dict)
    mentionCooldown: int = 20
    cooldownBypassList: List[int] = field(default_factory=List)
    promptsPath: str = "prompts.json"
    morningConfigsPath: str = "morning_configs.json"
    imageLimitsPath: str = "image_limits.json"
    mongoUri: str = ""
    mongoDbName: str = ""
    mongoMessagesCollectionName: str = ""
    mongoMorningConfigsCollectionName: str = "morning_configs"
    mongoImageLimitsCollectionName: str = "image_limits"
    allowedBotsToRespondTo: List[int] = field(default_factory=List)
    deleteUserMessages: DeleteUserMessagesConfig = field(default_factory=DeleteUserMessagesConfig)
    globalBlockList: List[int] = field(default_factory=List)

    @property
    def discordToken(self) -> str:
        """Get the appropriate Discord token based on environment."""
        env = os.getenv("ENVIRONMENT", "dev").lower()
        if env == "prod" or env == "production":
            return self.prodDiscordToken
        return self.devDiscordToken


class ConfigService:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Config | None = None

    def load(self, environment: str) -> Config:
        """Load and validate configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}. Please copy config.sample.yaml to config.yaml and configure it.")

        with open(self.config_path) as file:
            raw_config = yaml.safe_load(file)

        self.config = self._parse_dataclass(Config, raw_config)
        self._validate_config(self.config)

        logger.info(f"Configuration loaded successfully from {self.config_path}")
        logger.info(f"Environment: {environment.upper()} (using {'prodDiscordToken' if environment in ['prod', 'production'] else 'devDiscordToken'})")

        self.config.environment = environment

        return self.config

    def _parse_dataclass(self, cls: type[T], data: dict | None) -> T:
        """Recursively parse a dictionary into a dataclass instance."""
        if data is None:
            return cls()

        kwargs = {}
        for field_info in fields(cls):
            field_name = field_info.name
            field_type = field_info.type
            field_value = data.get(field_name)

            if field_value is None:
                continue

            origin = get_origin(field_type)

            if origin is type(None) or (origin is type(field_type) and type(None) in get_args(field_type)):
                args = get_args(field_type)
                if args:
                    inner_type = next((arg for arg in args if arg is not type(None)), None)
                    if inner_type and hasattr(inner_type, "__dataclass_fields__"):
                        kwargs[field_name] = self._parse_dataclass(inner_type, field_value)
                    else:
                        kwargs[field_name] = field_value
                else:
                    kwargs[field_name] = field_value
            elif hasattr(field_type, "__dataclass_fields__"):
                kwargs[field_name] = self._parse_dataclass(field_type, field_value)
            else:
                kwargs[field_name] = field_value

        return cls(**kwargs)

    def _validate_config(self, config: Config):
        """Validate the loaded configuration."""
        if not config.devDiscordToken:
            raise ValueError("devDiscordToken is missing or empty in the configuration.")

        if not config.prodDiscordToken:
            raise ValueError("prodDiscordToken is missing or empty in the configuration.")

        if not config.adminIds:
            raise ValueError("adminIds is missing in the configuration.")

        if not config.aiConfig:
            raise ValueError("aiConfig is missing in the configuration.")

        if not config.aiConfig.preferredAiProvider:
            raise ValueError("preferredAiProvider is missing in aiConfig.")

        self._validate_preferred_provider(config.aiConfig)

    def _validate_preferred_provider(self, ai_config: AIConfig):
        """Ensure the preferred AI provider is properly configured."""
        provider = ai_config.preferredAiProvider.lower()

        provider_map = {
            "ollama": (ai_config.ollama, lambda c: c.endpoint and c.preferredModel),
            "openai": (ai_config.openai, lambda c: c.apiKey),
            "antropic": (ai_config.antropic, lambda c: c.apiKey),
            "anthropic": (ai_config.antropic, lambda c: c.apiKey),
            "gemini": (ai_config.gemini, lambda c: c.apiKey),
            "google": (ai_config.gemini, lambda c: c.apiKey),
        }

        if provider not in provider_map:
            raise ValueError(f"Invalid preferredAiProvider: {provider}. Must be one of: {', '.join(provider_map.keys())}")

        config_obj, validator = provider_map[provider]

        if config_obj is None or not validator(config_obj):
            raise ValueError(f"Preferred AI provider '{provider}' is not properly configured. Please add valid configuration for {provider} in aiConfig.")

    def get_config(self) -> Config:
        """Get the loaded configuration."""
        if self.config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config


_config_service: ConfigService | None = None


def get_config_service(config_path: str = "config.yaml") -> ConfigService:
    """Get or create the ConfigService singleton."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService(config_path)
    return _config_service
