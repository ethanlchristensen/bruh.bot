import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any, Literal

import yaml
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field, SecretStr, model_validator

logger = logging.getLogger("bot.config")


class ProviderConfig(BaseModel):
    """Generic AI provider config."""

    apiKey: SecretStr = Field(default=SecretStr(""))
    endpoint: str = ""
    preferredModel: str = ""
    voice: str = ""
    realTimeModel: str = ""

    def get_api_key(self) -> str:
        """Safely get API key value, handling both SecretStr and plain string."""
        if isinstance(self.apiKey, SecretStr):
            return self.apiKey.get_secret_value()
        return str(self.apiKey)


class OrchestratorConfig(BaseModel):
    preferredAiProvider: Literal["ollama", "openrouter", "mesh_router"] = "openrouter"
    preferredModel: str = "deepseek/deepseek-v4-flash"


class ImageGenerationConfig(BaseModel):
    preferredAiProvider: Literal["google", "openrouter"] = "openrouter"
    preferredAiProvidder: str | None = "openrouter"
    preferredModel: str = ""
    maxDailyImages: int = 5
    boostImagePrompts: bool = False

    @model_validator(mode="before")
    @classmethod
    def handle_typo(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "preferredAiProvidder" in data and "preferredAiProvider" not in data:
                data["preferredAiProvider"] = data["preferredAiProvidder"]
        return data


class AIUsageLimitConfig(BaseModel):
    enabled: bool = True
    maxRequestsPerMinute: int = 5
    maxRequestsPerHour: int = 50


def load_default_prompts() -> tuple[str, str]:
    """Helper to load system prompts from local prompts.json if available as initial seed."""
    system_prompt = ""
    realtime_prompt = ""
    try:
        import json

        path = os.path.join(os.getcwd(), "config/prompts.json")
        if os.path.exists(path):
            with open(path) as f:
                prompts = json.load(f)
                system_prompt = prompts.get("main", "")
                realtime_prompt = prompts.get("realtime", "")
    except Exception:
        pass
    return system_prompt, realtime_prompt


class AIConfig(BaseModel):
    preferredAiProvider: Literal["ollama", "openrouter", "mesh_router"] = "openrouter"
    ollama: ProviderConfig = Field(default_factory=lambda: ProviderConfig(endpoint="localhost:11434", preferredModel="llama3.1"))
    openrouter: ProviderConfig = Field(default_factory=lambda: ProviderConfig(preferredModel="deepseek/deepseek-v4-flash"))
    mesh_router: ProviderConfig = Field(default_factory=lambda: ProviderConfig(preferredModel="deepseek/deepseek-v4-flash"))
    google: ProviderConfig = Field(default_factory=ProviderConfig)
    elevenlabs: ProviderConfig = Field(default_factory=ProviderConfig)
    realTimeConfig: ProviderConfig = Field(default_factory=lambda: ProviderConfig(voice="alloy"))
    orchestrator: OrchestratorConfig = Field(default_factory=lambda: OrchestratorConfig(preferredAiProvider="openrouter", preferredModel="deepseek/deepseek-v4-flash"))
    boostImagePrompts: bool = False
    imageGeneration: ImageGenerationConfig = Field(default_factory=ImageGenerationConfig)
    usageLimits: AIUsageLimitConfig = Field(default_factory=AIUsageLimitConfig)
    systemPrompt: str = Field(default_factory=lambda: load_default_prompts()[0])
    realtimePrompt: str = Field(default_factory=lambda: load_default_prompts()[1])


class DeleteUserMessagesConfig(BaseModel):
    enabled: bool = False
    userIds: list[int] = []


class MemoryConfig(BaseModel):
    enabled: bool = True
    extractionIntervalMinutes: int = 20
    moodExtractionIntervalMinutes: int = 5
    extractionProvider: str = "openrouter"
    extractionModel: str = "deepseek/deepseek-v4-flash"
    orchestratorProvider: str = "openrouter"
    orchestratorModel: str = "deepseek/deepseek-v4-flash"
    maxMessagesPerExtraction: int = 50
    minMessagesForExtraction: int = 5
    maxExtractionWaitMinutes: int = 60
    minMessageLength: int = 10
    maxMemoriesPerUser: int = 50
    maxInjectionCount: int = 10
    enabledCategories: list[str] = Field(default_factory=lambda: ["identity", "trait", "preference", "opinion", "relationship", "mood", "fact"])
    embeddingModel: str = "openai/text-embedding-3-small"
    embeddingDimensions: int = 1536
    maxToolRounds: int = 8
    maxToolCallsPerBatch: int = 40
    maxAddsPerUserPerBatch: int = 10
    dedupeThreshold: float = 0.92
    semanticRetrieval: bool = True
    retrievalMinScore: float = 0.35


class EconomyConfig(BaseModel):
    xpEnabled: bool = True
    coinsEnabled: bool = True
    baseXpRange: list[int] = [15, 25]
    imageXpBonus: int = 10
    reactionXp: int = 5
    mentionXpRange: list[int] = [10, 15]
    messageCoinRange: list[float] = [1.0, 3.0]
    imageCoinBonus: float = 3.0
    reactionCoin: float = 1.0
    mentionCoinRange: list[float] = [2.0, 5.0]
    dailyCoinMin: float = 50.0
    dailyCoinMax: float = 100.0
    levelUpAnnounceInChannel: bool = True
    spamCoinThreshold: float = 2.0
    spamCoinPenaltyIncrement: float = 0.2
    spamCoinPenaltyRecovery: float = 0.1
    spamCoinPenaltyMax: float = 1.0
    gamblingMaxCoinflipsPerDay: int = 10
    gamblingMaxDicePerDay: int = 10
    gamblingMaxSlotsPerDay: int = 10
    cardPacksEnabled: bool = True
    tradingEnabled: bool = True
    marketplaceEnabled: bool = False
    marketplaceFeeRate: float = 0.05
    tradeCooldownMinutes: int = 5
    cardSellbackRate: float = 0.1
    cosmeticsShopEnabled: bool = True
    # Independent trading card settings
    bruhCardsEnabled: bool = False
    tradingCardPacksEnabled: bool = True
    tradingCardTradingEnabled: bool = True
    tradingCardMarketEnabled: bool = False
    tradingCardMarketFeeRate: float = 0.05
    tradingCardSellbackRate: float = 1.0
    tradingCardMaxActiveListings: int = 20


class ReputationConfig(BaseModel):
    enabled: bool = False
    minMessageLength: int = 3
    minMessagesForExtraction: int = 10
    maxMessagesPerExtraction: int = 30
    maxExtractionWaitMinutes: int = 60
    extractionIntervalMinutes: int = 15
    extractionProvider: str = "openrouter"
    extractionModel: str = ""
    maxToolRounds: int = 3
    maxToolCallsPerBatch: int = 10
    minConfidence: float = 0.85
    warningThreshold: int = -5
    blockThreshold: int = -10
    blockDurationHours: int = 168
    noticeCooldownHours: int = 24


class DiscordScrapeBotConfig(BaseModel):
    databaseName: str = ""
    collectionName: str = ""


class BaseConfig(BaseModel):
    """Secrets from YAML - never changes."""

    devDiscordToken: str
    prodDiscordToken: str
    encryptionKey: str
    adminApiKey: str
    adminApiKeyProd: str
    ollamaEndpoint: str

    mongoUri: str
    mongoDbName: str
    mongoConfigCollectionName: str = "config"
    mongoImageLimitsCollectionName: str = "ImageLimits"
    mongoMorningConfigsCollectionName: str = "MorningConfigs"
    mongoCooldownCollectionName: str = "Cooldowns"
    mongoAIUsageCollectionName: str = "AIUsage"
    mongoAIUsageTrackingCollectionName: str = "AIUsageTracking"
    mongoChatThreadsCollectionName: str = "ChatThreads"
    mongoUserMemoriesCollectionName: str = "UserMemories"
    mongoUserProfilesCollectionName: str = "UserProfiles"
    mongoUserInventoryCollectionName: str = "UserInventory"
    mongoTransactionLedgerCollectionName: str = "TransactionLedger"
    mongoCardPacksCollectionName: str = "CardPacks"
    mongoTradeListingsCollectionName: str = "TradeListings"
    mongoTradingCardCollectionsCollectionName: str = "TradingCardCollections"
    mongoTradingCardMarketListingsCollectionName: str = "TradingCardMarketListings"
    mongoTradingCardSetsCollectionName: str = "TradingCardSets"
    mongoTradingCardCatalogCollectionName: str = "TradingCardCatalog"
    mongoTradingCardPacksCollectionName: str = "TradingCardPacks"
    mongoTradingCardAssetsBucketName: str = "TradingCardAssets"
    mongoShopItemsCollectionName: str = "ShopItems"
    mongoGuildMembersCollectionName: str = "GuildMembers"
    mongoMemoryQueueCollectionName: str = "MemoryExtractionQueue"
    mongoReputationQueueCollectionName: str = "ReputationQueue"
    mongoReputationCollectionName: str = "UserReputation"
    mongoReputationEventsCollectionName: str = "ReputationEvents"
    mongoDiscordScrapeBot: DiscordScrapeBotConfig = Field(default_factory=DiscordScrapeBotConfig)


class DynamicConfig(BaseModel):
    """Dynamic config stored in MongoDB."""

    guildId: str
    guildName: str = ""
    guildIcon: str = ""
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
    mongoMessagesDbName: str = "DiscordScrapeBot"
    mongoMessagesCollectionName: str = "Messages"
    mongoMorningConfigsCollectionName: str = "MorningConfigs"
    mongoImageLimitsCollectionName: str = "ImageLimits"
    mongoChatThreadsCollectionName: str = "ChatThreads"
    memoryConfig: MemoryConfig = Field(default_factory=MemoryConfig)
    economyConfig: EconomyConfig = Field(default_factory=EconomyConfig)
    reputationConfig: ReputationConfig = Field(default_factory=ReputationConfig)


class ConfigService:
    ENCRYPTED_PROVIDERS = [
        "openai",
        "antropic",
        "google",
        "elevenlabs",
        "realTimeConfig",
        "openrouter",
        "mesh_router",
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
        logger.info(f"Connected to MongoDB: {self.base.mongoDbName} (env={self.environment})")

        await self._ensure_config_indexes()

        logger.info(f"Config initialized: env={self.environment.upper()}")

    def col(self, base_name: str):
        """Get a MongoDB collection reference with per-environment namespacing.

        The 'config' collection is the only one SHARED across environments.
        All other collections (UserProfiles, AIUsage, UserMemories, etc.)
        get an environment suffix (e.g. _dev, _prod) to isolate data
        between development and production bot instances.
        """
        if base_name == "config":
            name = "config"
        else:
            name = f"{base_name}_{self.environment}"
        return self.db[name]

    async def _ensure_config_indexes(self):
        try:
            await self.col("config").create_index([("guildId", 1)], unique=True)
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
        collection = self.col(self.base.mongoConfigCollectionName)
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
        self._clean_secret_strs(data)

        coll = self.col(self.base.mongoConfigCollectionName)
        await coll.replace_one({"guildId": guild_id}, data, upsert=True)
        logger.info(f"Saved config for guild {guild_id} (v{config.configVersion})")

    def _clean_secret_strs(self, d: any):
        """Recursively convert all SecretStr objects to plain strings."""
        if isinstance(d, dict):
            for k, v in d.items():
                if hasattr(v, "get_secret_value"):
                    d[k] = v.get_secret_value()
                else:
                    self._clean_secret_strs(v)
        elif isinstance(d, list):
            for i, v in enumerate(d):
                if hasattr(v, "get_secret_value"):
                    d[i] = v.get_secret_value()
                else:
                    self._clean_secret_strs(v)

    def _encrypt(self, config_dict: dict):
        ai = config_dict.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            p_data = ai.get(provider)
            if p_data and isinstance(p_data, dict):
                key = p_data.get("apiKey", "")
                if hasattr(key, "get_secret_value"):
                    key = key.get_secret_value()
                key = str(key)
                if key and not key.startswith("gAAAA"):
                    p_data["apiKey"] = self.cipher.encrypt(key.encode()).decode()
                else:
                    p_data["apiKey"] = key

    def _decrypt(self, config_dict: dict):
        ai = config_dict.get("aiConfig", {})
        for provider in self.ENCRYPTED_PROVIDERS:
            p_data = ai.get(provider)
            if p_data and isinstance(p_data, dict):
                key = p_data.get("apiKey", "")
                if hasattr(key, "get_secret_value"):
                    key = key.get_secret_value()
                key = str(key)
                p_data["apiKey"] = key
                if key:
                    try:
                        p_data["apiKey"] = self.cipher.decrypt(key.encode()).decode()
                    except Exception as e:
                        logger.warning(f"Failed to decrypt {provider} for guild {config_dict.get('_id')}: {e}")

    async def reload_if_changed(self):
        """Checks all cached guilds for version updates in one query."""
        if not self._configs:
            return

        coll = self.col(self.base.mongoConfigCollectionName)
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
