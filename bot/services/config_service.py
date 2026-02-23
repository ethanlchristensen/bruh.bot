import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Literal

import yaml
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field, SecretStr

logger = logging.getLogger("bot.config")


class ProviderConfig(BaseModel):
    """Generic AI provider config."""

    apiKey: SecretStr = ""
    endpoint: str = ""
    preferredModel: str = ""
    voice: str = ""
    realTimeModel: str = ""


class OrchestratorConfig(BaseModel):
    preferredAiProvider: Literal["ollama", "openai", "antropic", "google"] = "google"
    preferredModel: str = ""


class ImageGenerationConfig(BaseModel):
    preferredAiProvidder: Literal["google"] = "google"
    preferredModel: str = ""
    maxDailyImages: int = 5
    boostImagePrompts: bool = False


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
    imageGeneration: ImageGenerationConfig = Field(default_factory=ImageGenerationConfig)


class DeleteUserMessagesConfig(BaseModel):
    enabled: bool = False
    userIds: list[int] = []


class DiscordScrapeBotConfig(BaseModel):
    databaseName: str
    collectionName: str


class BaseConfig(BaseModel):
    """Secrets from YAML - never changes."""

    devDiscordToken: str
    prodDiscordToken: str
    encryptionKey: str
    adminApiKey: str
    adminApiKeyProd: str
    promptsPath: str
    ollamaEndpoint: str

    mongoUri: str
    mongoDbName: str
    mongoConfigCollectionName: str = "config"
    mongoImageLimitsCollectionName: str = "ImageLimits"
    mongoMorningConfigsCollectionName: str = "Morningconfigs"
    mongoCooldownCollectionName: str = "Cooldowns"
    mongoDiscordScrapeBot: DiscordScrapeBotConfig = Field(default_factory=DiscordScrapeBotConfig)


class DynamicConfig(BaseModel):
    """Dynamic config stored in MongoDB."""

    guildId: str
    configVersion: int = 1
    lastUpdated: datetime | None = None
    adminIds: list[str] = Field(default_factory=list)
    invisible: bool = False
    aiConfig: AIConfig = Field(default_factory=AIConfig)
    usersToId: dict[str, str] = Field(default_factory=dict)
    idToUsers: dict[str, str] = Field(default_factory=dict)
    mentionCooldown: int = 20
    cooldownBypassList: list[str] = Field(default_factory=list)
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
        self._configs: dict[str, DynamicConfig] = {}
        self._services: dict[str, dict[str, any]] = {}
        self.db: AsyncIOMotorDatabase | None = None
        self.client: AsyncIOMotorClient | None = None
        self.cipher: Fernet | None = None
        self._version: int = 0
        self._watch_task: asyncio.Task | None = None
        self.environment: str | None = None

    async def initialize(self, environment: str):
        """Load config from YAML."""
        self.environment = environment
        self.base = self._load_yaml(environment)
        self.cipher = Fernet(self.base.encryptionKey.encode())

        self.client = AsyncIOMotorClient(self.base.mongoUri)
        self.db = self.client[self.base.mongoDbName]
        logger.info(f"Connected to MongoDB: {self.base.mongoDbName}")

        await self._ensure_config_indexes()

        logger.info(f"Config initialized: env={environment.upper()}")

    async def _ensure_config_indexes(self):
        try:
            await self.db["config"].create_index([("guildId", 1)], unique=True)
            logger.info("Successfully created indexes for config collection.")
        except Exception as e:
            logger.error("Failed to create indexes for config collection.", exc_info=e)

    def _load_yaml(self, environment: str) -> BaseConfig:
        """Load secrets from YAML."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        return BaseConfig(**data)

    async def get_config(self, guild_id: str) -> DynamicConfig:
        if guild_id not in self._configs:
            await self._load_from_mongo(guild_id)
        return self._configs[guild_id]

    async def _load_from_mongo(self, guild_id: str):
        """Load dynamic config from MongoDB."""
        collection = self.db[self.base.mongoConfigCollectionName]
        doc = await collection.find_one({"guildId": guild_id})

        if not doc:
            logger.info(f"No config for guild {guild_id} in MongoDB, using defaults.")
            new_config = DynamicConfig(guildId=guild_id)
            self._configs[guild_id] = new_config
        else:
            self._decrypt(doc)
            config = DynamicConfig.model_validate(doc)
            self._configs[guild_id] = config

        logger.debug(f"Loaded config for guild {guild_id} (v{self._configs[guild_id].configVersion})")

    async def save(self, guild_id: str):
        """Save specific guild config to MongoDB."""
        config = self._configs[guild_id]
        config.configVersion += 1
        config.lastUpdated = datetime.now(UTC)

        data = config.model_dump(by_alias=True)
        self._encrypt(data)

        coll = self.db[self.base.mongoConfigCollectionName]
        await coll.replace_one({"guildId": guild_id}, data, upsert=True)
        logger.info(f"Saved config for guild {guild_id} (v{config.configVersion})")

    def _encrypt(self, config_dict: dict):
        ai = config_dict.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            p_data = ai.get(provider)
            if p_data and isinstance(p_data, dict):
                key = p_data.get("apiKey", "")
                if key and not key.startswith("gAAAA"):
                    p_data["apiKey"] = self.cipher.encrypt(key.encode()).decode()

    def _decrypt(self, config_dict: dict):
        ai = config_dict.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            p_data = ai.get(provider)
            if p_data and isinstance(p_data, dict):
                key = p_data.get("apiKey", "")
                if key:
                    try:
                        p_data["apiKey"] = self.cipher.decrypt(key.encode()).decode()
                    except Exception as e:
                        logger.warning(f"Failed to decrypt {provider} for guild {config_dict.get('_id')}: {e}")

    async def reload_if_changed(self):
        """Checks all cached guilds for version updates in one query."""
        if not self._configs:
            return

        coll = self.db[self.base.mongoConfigCollectionName]
        cursor = coll.find({"guildId": {"$in": list(self._configs.keys())}}, {"configVersion": 1, "guildId": 1})

        async for doc in cursor:
            gid = doc["guildId"]
            if doc.get("configVersion", 0) > self._configs[gid].configVersion:
                logger.info(f"Reloading guild {gid} due to version mismatch")
                await self._load_from_mongo(gid)
                # Clear services for this guild so they get recreated with new config
                if gid in self._services:
                    del self._services[gid]

    async def start_watcher(self, interval: int = 10):
        async def watch():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.reload_if_changed()
                except Exception as e:
                    logger.error(f"Watcher error: {e}")

        self._watch_task = asyncio.create_task(watch())

    async def stop_watcher(self):
        """Stop the watcher."""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            logger.info("Watcher stopped")

    async def update(self, guild_id: str, updates: dict):
        """Update dynamic config for a specific guild."""
        config = await self.get_config(guild_id)
        data = config.model_dump()
        data.update(updates)
        self._configs[guild_id] = DynamicConfig(**data)
        await self.save(guild_id)
        # Clear services for this guild so they get recreated with new config
        if guild_id in self._services:
            del self._services[guild_id]

    def _validate(self, guild_id: str):
        """Validate config for a specific guild."""
        config = self._configs.get(guild_id)

        if not self.base.devDiscordToken or not self.base.prodDiscordToken:
            raise ValueError("Discord tokens missing")

        if not config:
            return

        if not config.adminIds:
            raise ValueError(f"adminIds missing for guild {guild_id}")

        provider = config.aiConfig.preferredAiProvider
        cfg = getattr(config.aiConfig, provider)

        if provider == "ollama":
            if not cfg.endpoint or not cfg.preferredModel:
                raise ValueError(f"Ollama not configured for guild {guild_id}")
        else:
            if not cfg.apiKey:
                raise ValueError(f"{provider} apiKey missing for guild {guild_id}")

    @property
    def discord_token(self) -> str:
        """Get Discord token for current environment."""
        env = (os.getenv("ENVIRONMENT") or "dev").lower()
        return self.base.prodDiscordToken if env in ["prod", "production"] else self.base.devDiscordToken

    @property
    def api_admin_key(self) -> str:
        env = (os.getenv("ENVIRONMENT") or "dev").lower()
        return self.base.adminApiKeyProd if env in ["prod", "production"] else self.base.adminApiKey

    def get_service(self, guild_id: str, service_name: str):
        """Get a cached service for a guild."""
        return self._services.get(guild_id, {}).get(service_name)

    def set_service(self, guild_id: str, service_name: str, service_instance):
        """Set a cached service for a guild."""
        if guild_id not in self._services:
            self._services[guild_id] = {}
        self._services[guild_id][service_name] = service_instance


_service: ConfigService | None = None


def get_config_service(config_path: str = "config/base_config.yaml") -> ConfigService:
    """Get singleton."""
    global _service
    if _service is None:
        _service = ConfigService(config_path)
    return _service
