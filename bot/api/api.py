import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from bson import Int64, ObjectId
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.services.config_service import get_config_service

logger = logging.getLogger("api")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

app = FastAPI(title="Bot Config API", description="API for managing dynamic bot configuration", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5175",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config_service = get_config_service()


class DeleteUserMessagesConfig(BaseModel):
    enabled: bool
    userIds: list[str]


class UpdateConfigRequest(BaseModel):
    invisible: bool | None = None
    mentionCooldown: int | None = None
    adminIds: list[str] | None = None
    cooldownBypassList: list[str] | None = None
    globalBlockList: list[str] | None = None
    mongoMessagesDbName: str | None = None
    mongoMessagesCollectionName: str | None = None
    allowedBotsToRespondTo: list[str] | None = None
    deleteUserMessages: DeleteUserMessagesConfig | None = None
    usersToId: dict[str, str] | None = None
    idToUsers: dict[str, str] | None = None
    memoryConfig: dict | None = None
    economyConfig: dict | None = None


class UpdateAIProviderRequest(BaseModel):
    provider: Literal["ollama", "openrouter", "mesh_router"]
    apiKey: str | None = None
    preferredModel: str | None = None
    endpoint: str | None = None
    voice: str | None = None
    orchestratorProvider: Literal["ollama", "openrouter", "mesh_router"] | None = None
    orchestratorModel: str | None = None
    systemPrompt: str | None = None
    realtimePrompt: str | None = None
    boostImagePrompts: bool | None = None
    maxDailyImages: int | None = None
    imageGenProvider: Literal["google", "openrouter"] | None = None
    imageGenModel: str | None = None
    maxRequestsPerMinute: int | None = None
    maxRequestsPerHour: int | None = None
    aiUsageLimitEnabled: bool | None = None


class AddAdminRequest(BaseModel):
    userId: str


class ConfigResponse(BaseModel):
    success: bool
    version: int
    config: dict | None = None
    message: str | None = None
    changed: bool | None = None


async def get_guild_id(x_guild_id: str = Header(default="default")):
    """Get guild ID from header."""
    return x_guild_id


# Auth dependency
async def verify_admin(x_admin_key: str = Header(...)):
    """Verify admin API key."""
    # Ensure service is initialized
    if config_service.base is None:
        environment = os.getenv("ENVIRONMENT", "dev")
        await config_service.initialize(environment)

    expected_key = config_service.api_admin_key

    if not expected_key:
        raise HTTPException(status_code=500, detail="API not configured")

    if x_admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return True


@app.on_event("startup")
async def startup():
    """Initialize config service on startup."""
    environment = os.getenv("ENVIRONMENT", "dev")
    await config_service.initialize(environment)
    logger.info(f"Config API started (env={environment})")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "config-api"}


@app.get("/config", response_model=ConfigResponse)
async def get_config(guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Get current dynamic config."""
    try:
        config_obj = await config_service.get_config(guild_id)

        # Return config without sensitive data
        data = config_obj.model_dump()

        # Mask API keys
        if "aiConfig" in data:
            for provider in ["openai", "antropic", "google", "elevenlabs", "realTimeConfig", "openrouter", "mesh_router"]:
                if provider in data["aiConfig"] and data["aiConfig"][provider]:
                    p_data = data["aiConfig"][provider]
                    if isinstance(p_data, dict):
                        key = p_data.get("apiKey", "")
                        if key:
                            # Convert to string if it's a SecretStr
                            actual_key = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key)
                            data["aiConfig"][provider]["apiKey"] = ("*" * (len(actual_key) - 4)) + actual_key[-4:] if len(actual_key) > 4 else "***"

        return ConfigResponse(success=True, version=config_obj.configVersion, config=data)

    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.patch("/config", response_model=ConfigResponse)
async def update_config(updates: UpdateConfigRequest, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Update dynamic config."""
    try:
        logger.info(f"Updating config for guild {guild_id} with updates: {updates}")

        # Convert to dict and filter None values
        update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        await config_service.update(guild_id, update_dict)

        # Fetch updated config to get version
        new_config = await config_service.get_config(guild_id)

        return ConfigResponse(success=True, message="Config updated", version=new_config.configVersion)

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/config/reload", response_model=ConfigResponse)
async def reload_config(guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Force reload config from MongoDB."""
    try:
        await config_service.reload_if_changed()
        # Even if reload_if_changed checks all, we return context for current guild
        config_obj = await config_service.get_config(guild_id)

        return ConfigResponse(success=True, version=config_obj.configVersion, message="Config reload check complete")

    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.patch("/config/ai-provider", response_model=ConfigResponse)
async def update_ai_provider(data: UpdateAIProviderRequest, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Update AI provider settings."""
    try:
        config_obj = await config_service.get_config(guild_id)

        # Prepare updates
        ai_config_dict = config_obj.aiConfig.model_dump()
        ai_config_dict["preferredAiProvider"] = data.provider

        # Update provider-specific settings in the dict
        # We need to ensure the provider dict exists
        if data.provider not in ai_config_dict or ai_config_dict[data.provider] is None:
            # Should be initialized by default_factory, but safe check
            pass  # Pydantic defaults handles this usually

        if data.apiKey is not None:
            # If the API key is masked (consists of or contains asterisks), do not overwrite the existing one
            if "*" in data.apiKey:
                pass
            else:
                ai_config_dict[data.provider]["apiKey"] = data.apiKey
        if data.preferredModel is not None:
            ai_config_dict[data.provider]["preferredModel"] = data.preferredModel
        if data.endpoint is not None:
            ai_config_dict[data.provider]["endpoint"] = data.endpoint
        if data.voice is not None:
            ai_config_dict[data.provider]["voice"] = data.voice

        # Handle Orchestrator-specific updates
        if data.orchestratorProvider is not None:
            ai_config_dict["orchestrator"]["preferredAiProvider"] = data.orchestratorProvider
        if data.orchestratorModel is not None:
            ai_config_dict["orchestrator"]["preferredModel"] = data.orchestratorModel

        # Handle Prompt-specific updates
        if data.systemPrompt is not None:
            ai_config_dict["systemPrompt"] = data.systemPrompt
        if data.realtimePrompt is not None:
            ai_config_dict["realtimePrompt"] = data.realtimePrompt

        # Handle Image Generation updates
        if "imageGeneration" not in ai_config_dict or ai_config_dict["imageGeneration"] is None:
            ai_config_dict["imageGeneration"] = {}

        if data.boostImagePrompts is not None:
            ai_config_dict["boostImagePrompts"] = data.boostImagePrompts
            ai_config_dict["imageGeneration"]["boostImagePrompts"] = data.boostImagePrompts
        if data.maxDailyImages is not None:
            ai_config_dict["imageGeneration"]["maxDailyImages"] = data.maxDailyImages
        if data.imageGenProvider is not None:
            ai_config_dict["imageGeneration"]["preferredAiProvider"] = data.imageGenProvider
            ai_config_dict["imageGeneration"]["preferredAiProvidder"] = data.imageGenProvider
        if data.imageGenModel is not None:
            ai_config_dict["imageGeneration"]["preferredModel"] = data.imageGenModel

        # Handle AI Usage Limits updates
        if "usageLimits" not in ai_config_dict or ai_config_dict["usageLimits"] is None:
            ai_config_dict["usageLimits"] = {}

        if data.aiUsageLimitEnabled is not None:
            ai_config_dict["usageLimits"]["enabled"] = data.aiUsageLimitEnabled
        if data.maxRequestsPerMinute is not None:
            ai_config_dict["usageLimits"]["maxRequestsPerMinute"] = data.maxRequestsPerMinute
        if data.maxRequestsPerHour is not None:
            ai_config_dict["usageLimits"]["maxRequestsPerHour"] = data.maxRequestsPerHour

        await config_service.update(guild_id, {"aiConfig": ai_config_dict})

        new_config = await config_service.get_config(guild_id)

        return ConfigResponse(success=True, message=f"AI provider updated to {data.provider}", version=new_config.configVersion)

    except Exception as e:
        logger.error(f"Error updating AI provider: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/config/admins", response_model=ConfigResponse)
async def add_admin(data: AddAdminRequest, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Add admin user ID."""
    try:
        config_obj = await config_service.get_config(guild_id)

        if data.userId in config_obj.adminIds:
            raise HTTPException(status_code=400, detail="User already admin")

        admins = config_obj.adminIds.copy()
        admins.append(data.userId)

        await config_service.update(guild_id, {"adminIds": admins})

        new_config = await config_service.get_config(guild_id)

        return ConfigResponse(success=True, message=f"Added admin {data.userId}", version=new_config.configVersion)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/config/admins/{user_id}", response_model=ConfigResponse)
async def remove_admin(user_id: str, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Remove admin user ID."""
    try:
        config_obj = await config_service.get_config(guild_id)

        if user_id not in config_obj.adminIds:
            raise HTTPException(status_code=404, detail="User not admin")

        admins = [uid for uid in config_obj.adminIds if uid != user_id]

        if not admins:
            raise HTTPException(status_code=400, detail="Cannot remove last admin")

        await config_service.update(guild_id, {"adminIds": admins})

        new_config = await config_service.get_config(guild_id)

        return ConfigResponse(success=True, message=f"Removed admin {user_id}", version=new_config.configVersion)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/config/version")
async def get_version(guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Get current config version."""
    try:
        config_obj = await config_service.get_config(guild_id)
        return {"version": config_obj.configVersion, "lastUpdated": config_obj.lastUpdated}
    except Exception as e:
        logger.error(f"Error getting version: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/config/models")
async def get_models(provider: str, endpoint: str | None = None, image_gen: bool = False, structured_outputs: bool = False, refresh: bool = False, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Fetch available models for a provider using MeshGateway."""
    try:
        if refresh:
            from bot.services.ai.gateway.providers.openrouter_provider import OpenRouterAdapter

            OpenRouterAdapter.invalidate_model_cache()
        config_obj = await config_service.get_config(guild_id)
        ai_cfg = config_obj.aiConfig
        provider_cfg = getattr(ai_cfg, provider, None) or ai_cfg.openrouter

        api_key = ""
        if provider_cfg:
            try:
                api_key = provider_cfg.get_api_key()
            except Exception:
                pass

        if not endpoint:
            endpoint = ""
            if provider == "ollama" and provider_cfg:
                endpoint = getattr(provider_cfg, "endpoint", "")

        has_key = bool(api_key and api_key.strip())

        from bot.services.ai.gateway.gateway import get_mesh_gateway

        gateway = get_mesh_gateway()
        models = await gateway.get_models(provider, credentials={"api_key": api_key, "endpoint": endpoint})

        if image_gen:
            model_ids = [m.id for m in models if m.capabilities.image_gen]
        elif structured_outputs:
            model_ids = [m.id for m in models if m.capabilities.json_mode]
        else:
            model_ids = [m.id for m in models]

        logger.info(f"/config/models provider={provider} guild={guild_id} has_key={has_key} key_len={len(api_key) if has_key else 0} count={len(model_ids)}")

        return {"success": True, "models": model_ids, "has_api_key": has_key, "model_count": len(model_ids)}
    except Exception as e:
        logger.warning(f"Error getting models for provider {provider}: {e}")
        return {"success": False, "models": [], "error": str(e)}


@app.get("/guilds")
async def get_guilds(authorized: bool = Depends(verify_admin)):
    """Get list of available guild IDs and names from MongoDB."""
    try:
        collection = config_service.col(config_service.base.mongoConfigCollectionName)
        guilds = await collection.find({}, {"guildId": 1, "guildName": 1, "guildIcon": 1, "_id": 0}).to_list(length=None)
        guild_list = [{"id": g["guildId"], "name": g.get("guildName", g["guildId"]), "icon": g.get("guildIcon", "")} for g in guilds if "guildId" in g]
        return {"success": True, "guilds": guild_list}
    except Exception as e:
        logger.error(f"Error getting guilds: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


class MemoryItem(BaseModel):
    id: str
    guild_id: str
    user_id: str
    memory: str
    category: str
    confidence: float
    created_by: str
    created_at: str | None = None
    updated_at: str | None = None
    expires_at: str | None = None
    source_message_id: str | None = None
    target_user_id: str | None = None
    ttl_days: int | None = None
    is_permanent: bool = False
    is_expired: bool = False


class MemoriesResponse(BaseModel):
    success: bool
    user_id: str
    memories: list[MemoryItem]
    count: int


class DeleteMemoryResponse(BaseModel):
    success: bool
    message: str


class UsersResponse(BaseModel):
    success: bool
    users: list[dict]


@app.get("/users", response_model=UsersResponse)
async def get_users(
    guild_id: str = Depends(get_guild_id),
    authorized: bool = Depends(verify_admin),
):
    try:
        collection = config_service.col(config_service.base.mongoUserMemoriesCollectionName)
        pipeline = [
            {"$match": {"guild_id": Int64(int(guild_id))}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        config_obj = await config_service.get_config(guild_id)
        id_to_users = getattr(config_obj, "idToUsers", {})
        member_names = await _resolve_member_names(guild_id)

        users = []
        async for doc in collection.aggregate(pipeline):
            user_id = str(doc["_id"])
            member = member_names.get(user_id, {})
            username = member.get("username") or id_to_users.get(user_id) or None
            users.append(
                {
                    "id": user_id,
                    "username": username or f"User {user_id}",
                    "avatar_url": member.get("avatar_url", ""),
                    "memory_count": doc["count"],
                }
            )

        return UsersResponse(success=True, users=users)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


CATEGORY_TTL_DAYS: dict[str, int | None] = {
    "identity": None,
    "trait": None,
    "preference": 90,
    "opinion": 30,
    "relationship": None,
    "mood": 7,
    "fact": 90,
    "admin": None,
}


def _format_memory_doc(doc: dict) -> MemoryItem:
    category = doc.get("category", "fact")
    ttl_days = CATEGORY_TTL_DAYS.get(category)
    is_permanent = ttl_days is None
    expires_at = doc.get("expires_at")

    expires_at_str = None
    if expires_at:
        if isinstance(expires_at, datetime):
            expires_at_str = expires_at.isoformat()
        else:
            expires_at_str = str(expires_at)

    is_expired = False
    if isinstance(expires_at, datetime):
        aware = expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
        is_expired = aware < datetime.now(UTC)

    return MemoryItem(
        id=str(doc["_id"]),
        guild_id=str(doc.get("guild_id", 0)),
        user_id=str(doc.get("user_id", 0)),
        memory=doc.get("memory", ""),
        category=category,
        confidence=float(doc.get("confidence", 0.5)),
        created_by=doc.get("created_by", "unknown"),
        created_at=doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", "")),
        updated_at=doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), datetime) else str(doc.get("updated_at", "")),
        expires_at=expires_at_str,
        source_message_id=str(doc["source_message_id"]) if doc.get("source_message_id") else None,
        target_user_id=str(doc["target_user_id"]) if doc.get("target_user_id") else None,
        ttl_days=ttl_days,
        is_permanent=is_permanent,
        is_expired=is_expired,
    )


@app.get("/memories/{user_id}", response_model=MemoriesResponse)
async def get_user_memories(
    user_id: str,
    guild_id: str = Depends(get_guild_id),
    authorized: bool = Depends(verify_admin),
):
    try:
        collection = config_service.col(config_service.base.mongoUserMemoriesCollectionName)
        query = {"guild_id": Int64(int(guild_id)), "user_id": Int64(int(user_id))}
        cursor = collection.find(query).sort("created_at", -1)

        memories = []
        async for doc in cursor:
            memories.append(_format_memory_doc(doc))

        return MemoriesResponse(
            success=True,
            user_id=user_id,
            memories=memories,
            count=len(memories),
        )
    except Exception as e:
        logger.error(f"Error fetching memories for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/memories/{memory_id}", response_model=DeleteMemoryResponse)
async def delete_memory(
    memory_id: str,
    guild_id: str = Depends(get_guild_id),
    authorized: bool = Depends(verify_admin),
):
    try:
        collection = config_service.col(config_service.base.mongoUserMemoriesCollectionName)
        result = await collection.delete_one({"_id": ObjectId(memory_id), "guild_id": Int64(int(guild_id))})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Memory not found")

        return DeleteMemoryResponse(success=True, message=f"Memory {memory_id} deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/usage/leaderboard")
async def get_usage_leaderboard(days: int | None = None, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Get the AI usage leaderboard for a guild."""
    try:
        collection_name = config_service.base.mongoAIUsageTrackingCollectionName
        collection = config_service.col(collection_name)

        match: dict = {"guild_id": Int64(int(guild_id))}
        end_date = date.today().isoformat()
        if days is not None:
            start = datetime.now(UTC) - timedelta(days=days)
            match["date"] = {"$gte": start.date().isoformat(), "$lte": end_date}

        config_obj = await config_service.get_config(guild_id)
        id_to_users = getattr(config_obj, "idToUsers", {})
        member_names = await _resolve_member_names(guild_id)

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$user_id",
                    "total_requests": {"$sum": "$total_requests"},
                    "total_input_tokens": {"$sum": "$total_input_tokens"},
                    "total_output_tokens": {"$sum": "$total_output_tokens"},
                    "total_cost": {"$sum": "$total_cost"},
                    "models_used": {"$mergeObjects": "$models_used"},
                },
            },
            {"$sort": {"total_cost": -1}},
            {"$limit": 25},
        ]

        leaderboard = []
        async for doc in collection.aggregate(pipeline):
            uid = str(doc["_id"])
            member = member_names.get(uid, {})
            username = member.get("username") or id_to_users.get(uid) or f"User {uid}"
            leaderboard.append(
                {
                    "user_id": uid,
                    "username": username,
                    "avatar_url": member.get("avatar_url", ""),
                    "total_requests": doc["total_requests"],
                    "total_input_tokens": doc["total_input_tokens"],
                    "total_output_tokens": doc["total_output_tokens"],
                    "total_cost": round(doc["total_cost"], 6),
                    "models_used": doc.get("models_used", {}),
                }
            )

        summary_pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": "$total_requests"},
                    "total_cost": {"$sum": "$total_cost"},
                },
            },
        ]
        summary = {"total_requests": 0, "total_cost": 0}
        async for doc in collection.aggregate(summary_pipeline):
            summary = {"total_requests": doc["total_requests"], "total_cost": round(doc["total_cost"], 6)}

        return {"success": True, "guild_id": guild_id, "days": days, "leaderboard": leaderboard, "summary": summary}
    except Exception as e:
        logger.error(f"Error getting usage leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/usage/user/{user_id}")
async def get_user_usage(user_id: str, days: int | None = None, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    """Get AI usage for a specific user."""
    try:
        collection_name = config_service.base.mongoAIUsageTrackingCollectionName
        collection = config_service.col(collection_name)

        match: dict = {"guild_id": Int64(int(guild_id)), "user_id": Int64(int(user_id))}
        end_date = date.today().isoformat()
        if days is not None:
            start = datetime.now(UTC) - timedelta(days=days)
            match["date"] = {"$gte": start.date().isoformat(), "$lte": end_date}

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$user_id",
                    "total_requests": {"$sum": "$total_requests"},
                    "total_input_tokens": {"$sum": "$total_input_tokens"},
                    "total_output_tokens": {"$sum": "$total_output_tokens"},
                    "total_cost": {"$sum": "$total_cost"},
                    "models_used": {"$mergeObjects": "$models_used"},
                },
            },
        ]

        async for doc in collection.aggregate(pipeline):
            return {
                "success": True,
                "guild_id": guild_id,
                "user_id": user_id,
                "days": days,
                "usage": {
                    "user_id": user_id,
                    "total_requests": doc["total_requests"],
                    "total_input_tokens": doc["total_input_tokens"],
                    "total_output_tokens": doc["total_output_tokens"],
                    "total_cost": round(doc["total_cost"], 6),
                    "models_used": doc.get("models_used", {}),
                },
            }

        return {
            "success": True,
            "guild_id": guild_id,
            "user_id": user_id,
            "days": days,
            "usage": {"user_id": user_id, "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost": 0, "models_used": {}},
        }
    except Exception as e:
        logger.error(f"Error getting user usage: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/economy/leaderboard")
async def get_economy_leaderboard(sort_by: str = "xp", limit: int = 25, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    try:
        from bot.services.mongo_economy_service import MongoEconomyService

        if config_service.db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")

        service = MongoEconomyService.__new__(MongoEconomyService)
        service.bot = type("obj", (), {"config_service": config_service})()
        service.collection = config_service.col(config_service.base.mongoUserProfilesCollectionName)
        service.logger = logging.getLogger("api.economy")

        entries = await service.get_leaderboard(int(guild_id), sort_by=sort_by, limit=limit)
        member_names = await _resolve_member_names(guild_id)

        result = []
        for entry in entries:
            uid = str(entry["user_id"])
            member = member_names.get(uid, {})
            result.append(
                {
                    "user_id": uid,
                    "username": member.get("username", f"User {uid}"),
                    "avatar_url": member.get("avatar_url", ""),
                    "xp": entry["xp"],
                    "level": entry["level"],
                    "bruh_coins": entry["bruh_coins"],
                    "total_messages": entry["total_messages"],
                    "rank": entry["rank"],
                }
            )

        return {"success": True, "guild_id": guild_id, "sort_by": sort_by, "leaderboard": result}
    except Exception as e:
        logger.error(f"Error getting economy leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/economy/profile/{user_id}")
async def get_economy_profile(user_id: str, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    try:
        from bot.services.mongo_economy_service import MongoEconomyService

        if config_service.db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")

        service = MongoEconomyService.__new__(MongoEconomyService)
        service.bot = type("obj", (), {"config_service": config_service})()
        service.collection = config_service.col(config_service.base.mongoUserProfilesCollectionName)
        service.logger = logging.getLogger("api.economy")

        profile = await service.get_profile(int(guild_id), int(user_id))
        rank = await service.get_rank(int(guild_id), int(user_id))

        if profile:
            profile["user_id"] = str(profile.get("user_id", user_id))
            profile["rank"] = rank

        return {"success": True, "guild_id": guild_id, "profile": profile}
    except Exception as e:
        logger.error(f"Error getting economy profile: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


class UpdateEconomyProfileRequest(BaseModel):
    xp: int | None = None
    bruh_coins: float | None = None
    level: int | None = None


@app.put("/economy/profile/{user_id}")
async def update_economy_profile(user_id: str, data: UpdateEconomyProfileRequest, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    try:
        from bot.services.mongo_economy_service import MongoEconomyService

        if config_service.db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")

        service = MongoEconomyService.__new__(MongoEconomyService)
        service.bot = type("obj", (), {"config_service": config_service})()
        service.collection = config_service.col(config_service.base.mongoUserProfilesCollectionName)
        service.logger = logging.getLogger("api.economy")

        if data.xp is not None:
            await service.set_xp(int(guild_id), int(user_id), data.xp)
        if data.bruh_coins is not None:
            await service.set_coins(int(guild_id), int(user_id), data.bruh_coins)
        if data.level is not None:
            await service.set_level(int(guild_id), int(user_id), data.level)

        profile = await service.get_profile(int(guild_id), int(user_id))
        if profile:
            profile["user_id"] = str(profile.get("user_id", user_id))

        return {"success": True, "guild_id": guild_id, "profile": profile}
    except Exception as e:
        logger.error(f"Error updating economy profile: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/economy/rank/{user_id}")
async def get_economy_rank(user_id: str, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    try:
        from bot.services.mongo_economy_service import MongoEconomyService

        if config_service.db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")

        service = MongoEconomyService.__new__(MongoEconomyService)
        service.bot = type("obj", (), {"config_service": config_service})()
        service.collection = config_service.col(config_service.base.mongoUserProfilesCollectionName)
        service.logger = logging.getLogger("api.economy")

        rank = await service.get_rank(int(guild_id), int(user_id))

        return {"success": True, "guild_id": guild_id, "user_id": user_id, "rank": rank}
    except Exception as e:
        logger.error(f"Error getting economy rank: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _resolve_member_names(guild_id: str, member_collection=None) -> dict[str, dict]:
    if member_collection is None and config_service.db is not None:
        member_collection = config_service.col(config_service.base.mongoGuildMembersCollectionName)
    if member_collection is None:
        return {}
    result = {}
    cursor = member_collection.find(
        {"guild_id": Int64(int(guild_id))},
        {"user_id": 1, "display_name": 1, "username": 1, "global_name": 1, "avatar_url": 1, "_id": 0},
    )
    async for doc in cursor:
        uid = str(doc["user_id"])
        result[uid] = {
            "username": doc.get("display_name") or doc.get("username", ""),
            "avatar_url": doc.get("avatar_url", ""),
        }
    return result


@app.get("/members")
async def get_members(search: str | None = None, guild_id: str = Depends(get_guild_id), authorized: bool = Depends(verify_admin)):
    try:
        if config_service.db is None:
            raise HTTPException(status_code=503, detail="Database not initialized")
        collection = config_service.col(config_service.base.mongoGuildMembersCollectionName)
        query: dict = {"guild_id": Int64(int(guild_id))}
        if search:
            query["$text"] = {"$search": search}
        cursor = collection.find(query, {"_id": 0}).limit(2000)
        members = []
        async for doc in cursor:
            members.append(
                {
                    "user_id": str(doc["user_id"]),
                    "username": doc.get("username", ""),
                    "display_name": doc.get("display_name", ""),
                    "global_name": doc.get("global_name"),
                    "avatar_url": doc.get("avatar_url", ""),
                }
            )
        return {"success": True, "guild_id": guild_id, "members": members, "count": len(members)}
    except Exception as e:
        logger.error(f"Error getting members: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", 5000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False, log_level="info")
