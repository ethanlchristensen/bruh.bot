import logging
import os
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.services.config_service import get_config_service

logger = logging.getLogger("api.config")

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
    promptsPath: str | None = None
    mongoMessagesDbName: str | None = None
    mongoMessagesCollectionName: str | None = None
    allowedBotsToRespondTo: list[str] | None = None
    deleteUserMessages: DeleteUserMessagesConfig | None = None
    usersToId: dict[str, str] | None = None
    idToUsers: dict[str, str] | None = None


class UpdateAIProviderRequest(BaseModel):
    provider: Literal["ollama", "openai", "antropic", "google"]
    apiKey: str | None = None
    preferredModel: str | None = None
    endpoint: str | None = None
    voice: str | None = None


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
            for provider in ["openai", "antropic", "google", "elevenlabs", "realTimeConfig"]:
                if provider in data["aiConfig"] and data["aiConfig"][provider]:
                    p_data = data["aiConfig"][provider]
                    if isinstance(p_data, dict):
                        key = p_data.get("apiKey", "")
                        if key:
                            data["aiConfig"][provider]["apiKey"] = ("*" * (len(key) - 4)) + key[-4:] if len(key) > 4 else "***"

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
            ai_config_dict[data.provider]["apiKey"] = data.apiKey
        if data.preferredModel is not None:
            ai_config_dict[data.provider]["preferredModel"] = data.preferredModel
        if data.endpoint is not None:
            ai_config_dict[data.provider]["endpoint"] = data.endpoint
        if data.voice is not None:
            ai_config_dict[data.provider]["voice"] = data.voice

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


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", 5000))
    # Ensure correct module path if running directly
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False, log_level="info")
