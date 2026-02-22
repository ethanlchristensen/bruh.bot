import asyncio
import logging
import os
from datetime import datetime, UTC
from typing import Literal

import yaml
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger("bot.config")


class ProviderConfig(BaseModel):
    """Generic AI provider config."""

    apiKey: str = ""
    endpoint: str = ""
    preferredModel: str = ""
    voice: str = ""
    realTimeModel: str = ""


class OrchestratorConfig(BaseModel):
    preferredAiProvider: Literal["ollama", "openai", "antropic", "google"] = "google"
    preferredModel: str = ""


class AIConfig(BaseModel):
    preferredAiProvider: Literal["ollama", "openai", "antropic", "google"] = "google"
    ollama: ProviderConfig = Field(default_factory=lambda: ProviderConfig(endpoint="localhost:11434", preferredModel="llama3.1"))
    openai: ProviderConfig = Field(default_factory=lambda: ProviderConfig(preferredModel="gpt-5-nano"))
    antropic: ProviderConfig = Field(default_factory=lambda: ProviderConfig(preferredModel="claude-4-5-sonnet"))
    google: ProviderConfig = Field(default_factory=lambda: ProviderConfig(preferredModel="gemini-3-flash-preview"))
    elevenlabs: ProviderConfig = Field(default_factory=ProviderConfig)
    realTimeConfig: ProviderConfig = Field(default_factory=lambda: ProviderConfig(voice="alloy"))
    orchestrator: OrchestratorConfig = Field(default_factory=lambda: OrchestratorConfig(preferredAiProvider="google", preferredModel="gemini-3-flash-preview"))
    boostImagePrompts: bool = False
    maxDailyImages: int = 1


class DeleteUserMessagesConfig(BaseModel):
    enabled: bool = False
    userIds: list[int] = []


class BaseConfig(BaseModel):
    """Secrets from YAML - never changes."""

    devDiscordToken: str
    prodDiscordToken: str
    mongoUri: str
    mongoDbName: str
    encryptionKey: str
    mongoConfigCollectionName: str = "bot_config"
    adminApiKey: str
    adminApiKeyProd: str


class DynamicConfig(BaseModel):
    """Dynamic config stored in MongoDB."""

    configVersion: int = 1
    lastUpdated: datetime | None = None
    adminIds: list[str] = Field(default_factory=list)
    invisible: bool = False
    aiConfig: AIConfig = Field(default_factory=AIConfig)
    usersToId: dict[str, str] = Field(default_factory=dict)
    idToUsers: dict[str, str] = Field(default_factory=dict)
    mentionCooldown: int = 20
    cooldownBypassList: list[str] = Field(default_factory=list)
    promptsPath: str = "prompts.json"
    mongoMessagesDbName: str = ""
    mongoMessagesCollectionName: str = ""
    mongoMorningConfigsCollectionName: str = "MorningConfigs"
    mongoImageLimitsCollectionName: str = "ImageLimits"
    allowedBotsToRespondTo: list[str] = Field(default_factory=list)
    deleteUserMessages: DeleteUserMessagesConfig = Field(default_factory=DeleteUserMessagesConfig)
    globalBlockList: list[str] = Field(default_factory=list)


class ConfigService:
    ENCRYPTED_PROVIDERS = [
        "openai",
        "antropic",
        "google",
        "elevenlabs",
        "realTimeConfig",
    ]

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.base: BaseConfig | None = None
        self.dynamic: DynamicConfig | None = None
        self.db: AsyncIOMotorDatabase | None = None
        self.cipher: Fernet | None = None
        self._version: int = 0
        self._watch_task: asyncio.Task | None = None
        self.environment: str | None = None

    async def initialize(self, environment: str):
        """Load config from YAML and MongoDB."""
        self.base = self._load_yaml(environment)
        self.cipher = Fernet(self.base.encryptionKey.encode())

        client = AsyncIOMotorClient(self.base.mongoUri)
        self.db = client[self.base.mongoDbName]
        logger.info(f"Connected to MongoDB: {self.base.mongoDbName}")

        await self._load_from_mongo()
        self._validate()

        logger.info(f"Config loaded: env={environment.upper()}, version={self._version}")

    def _load_yaml(self, environment: str) -> BaseConfig:
        """Load secrets from YAML."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        return BaseConfig(**data)

    async def _load_from_mongo(self):
        """Load dynamic config from MongoDB."""
        coll = self.db[self.base.mongoConfigCollectionName]
        doc = await coll.find_one({"_id": "main"})

        if not doc:
            logger.warning("No config in MongoDB, creating default...")
            self.dynamic = DynamicConfig()
            await self.save()
        else:
            doc.pop("_id", None)
            self._decrypt(doc)
            self.dynamic = DynamicConfig(**doc)
            self._version = self.dynamic.configVersion

        logger.info(f"Dynamic config loaded (v{self._version})")

    async def save(self):
        """Save dynamic config to MongoDB."""
        self.dynamic.configVersion += 1
        self.dynamic.lastUpdated = datetime.now(UTC)
        self._version = self.dynamic.configVersion

        data = self.dynamic.model_dump()
        self._encrypt(data)

        coll = self.db[self.base.mongoConfigCollectionName]
        await coll.update_one({"_id": "main"}, {"$set": data}, upsert=True)

        logger.info(f"Config saved (v{self._version})")

    def _encrypt(self, config: dict):
        """Encrypt API keys in place."""
        ai = config.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            if provider in ai and ai[provider]:
                key = ai[provider].get("apiKey", "")
                if key:
                    ai[provider]["apiKey"] = self.cipher.encrypt(key.encode()).decode()

    def _decrypt(self, config: dict):
        """Decrypt API keys in place."""
        ai = config.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            if provider in ai and ai[provider]:
                key = ai[provider].get("apiKey", "")
                if key:
                    try:
                        ai[provider]["apiKey"] = self.cipher.decrypt(key.encode()).decode()
                    except Exception as e:
                        logger.warning(f"Failed to decrypt {provider}: {e}")

    async def reload_if_changed(self) -> bool:
        """Check for config changes and reload."""
        coll = self.db[self.base.mongoConfigCollectionName]
        doc = await coll.find_one({"_id": "main"}, {"configVersion": 1})

        if doc and doc.get("configVersion", 0) > self._version:
            logger.info(f"Config changed (v{doc['configVersion']}), reloading...")
            await self._load_from_mongo()
            self._validate()
            return True

        return False

    async def start_watcher(self, interval: int = 5):
        """Start background watcher for config changes."""

        async def watch():
            while True:
                try:
                    await asyncio.sleep(interval)
                    if await self.reload_if_changed():
                        logger.info("Config reloaded")
                except Exception as e:
                    logger.error(f"Watcher error: {e}")

        self._watch_task = asyncio.create_task(watch())
        logger.info(f"Watcher started (interval={interval}s)")

    async def stop_watcher(self):
        """Stop the watcher."""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            logger.info("Watcher stopped")

    async def update(self, updates: dict):
        """Update dynamic config."""
        data = self.dynamic.model_dump()
        data.update(updates)
        self.dynamic = DynamicConfig(**data)
        await self.save()
        self._validate()

    def _validate(self):
        """Validate config."""
        if not self.base.devDiscordToken or not self.base.prodDiscordToken:
            raise ValueError("Discord tokens missing")
        if not self.dynamic.adminIds:
            raise ValueError("adminIds missing")

        provider = self.dynamic.aiConfig.preferredAiProvider
        cfg = getattr(self.dynamic.aiConfig, provider)

        if provider == "ollama":
            if not cfg.endpoint or not cfg.preferredModel:
                raise ValueError("Ollama not configured")
        else:
            if not cfg.apiKey:
                raise ValueError(f"{provider} apiKey missing")

    @property
    def discord_token(self) -> str:
        """Get Discord token for current environment."""
        env = os.getenv("ENVIRONMENT", "dev").lower()
        return self.base.prodDiscordToken if env in ["prod", "production"] else self.base.devDiscordToken

    @property
    def api_admin_key(self) -> str:
        env = os.getenv("ENVIRONMENT", "dev").lower()
        return self.base.adminApiKeyProd if env in ["prod", "production"] else self.base.adminApiKey


_service: ConfigService | None = None


def get_config_service(config_path: str = "config/base_config.yaml") -> ConfigService:
    """Get singleton."""
    global _service
    if _service is None:
        _service = ConfigService(config_path)
    return _service
