import logging
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bot.services.config_service import get_config_service

logger = logging.getLogger("api.config")

app = FastAPI(
    title="Bot Config API",
    description="API for managing dynamic bot configuration",
    version="1.0.0"
)

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

config = get_config_service()

class DeleteUserMessagesConfig(BaseModel):
    enabled: bool
    userIds: list[int]


class UpdateConfigRequest(BaseModel):
    invisible: bool | None = None
    mentionCooldown: int | None = None
    adminIds: list[int] | None = None
    cooldownBypassList: list[int] | None = None
    globalBlockList: list[int] | None = None
    promptsPath: str | None = None
    mongoMessagesDbName: str | None = None
    mongoMessagesCollectionName: str | None = None
    allowedBotsToRespondTo: list[int] | None = None
    deleteUserMessages: DeleteUserMessagesConfig | None = None


class UpdateAIProviderRequest(BaseModel):
    provider: Literal["ollama", "openai", "antropic", "google"]
    apiKey: str | None = None
    preferredModel: str | None = None
    endpoint: str | None = None
    voice: str | None = None


class AddAdminRequest(BaseModel):
    userId: int


class ConfigResponse(BaseModel):
    success: bool
    version: int
    config: dict | None = None
    message: str | None = None
    changed: bool | None = None


# Auth dependency
async def verify_admin(x_admin_key: str = Header(...)):
    """Verify admin API key."""
    expected_key = config.api_admin_key
    
    if not expected_key:
        raise HTTPException(status_code=500, detail="API not configured")
    
    if x_admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return True


@app.on_event("startup")
async def startup():
    """Initialize config service on startup."""
    environment = os.getenv("ENVIRONMENT", "dev")
    config = get_config_service()
    await config.initialize(environment)
    logger.info(f"Config API started (env={environment})")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "config-api"}


@app.get("/config", response_model=ConfigResponse)
async def get_config(authorized: bool = Depends(verify_admin)):
    """Get current dynamic config."""
    try:
        config = get_config_service()
        
        if not config.dynamic:
            raise HTTPException(status_code=500, detail="Config not initialized")
        
        # Return config without sensitive data
        data = config.dynamic.model_dump()
        
        # Mask API keys
        if "aiConfig" in data:
            for provider in ["openai", "antropic", "google", "elevenlabs", "realTimeConfig"]:
                if provider in data["aiConfig"] and data["aiConfig"][provider]:
                    key = data["aiConfig"][provider].get("apiKey", "")
                    if key:
                        data["aiConfig"][provider]["apiKey"] = "***" + key[-4:] if len(key) > 4 else "***"
        
        return ConfigResponse(
            success=True,
            version=config._version,
            config=data
        )
    
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/config", response_model=ConfigResponse)
async def update_config(
    updates: UpdateConfigRequest,
    authorized: bool = Depends(verify_admin)
):
    """Update dynamic config."""
    try:
        config = get_config_service()
        
        if not config.dynamic:
            raise HTTPException(status_code=500, detail="Config not initialized")
        
        # Convert to dict and filter None values
        update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        await config.update(update_dict)
        
        return ConfigResponse(
            success=True,
            message="Config updated",
            version=config._version
        )
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/config/reload", response_model=ConfigResponse)
async def reload_config(authorized: bool = Depends(verify_admin)):
    """Force reload config from MongoDB."""
    try:
        config = get_config_service()
        
        changed = await config.reload_if_changed()
        
        return ConfigResponse(
            success=True,
            changed=changed,
            version=config._version,
            message="Config reloaded" if changed else "No changes detected"
        )
    
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/config/ai-provider", response_model=ConfigResponse)
async def update_ai_provider(
    data: UpdateAIProviderRequest,
    authorized: bool = Depends(verify_admin)
):
    """Update AI provider settings."""
    try:
        config = get_config_service()
        
        updates = {
            "aiConfig": config.dynamic.aiConfig.model_dump()
        }
        updates["aiConfig"]["preferredAiProvider"] = data.provider
        
        # Update provider-specific settings
        if data.apiKey is not None:
            updates["aiConfig"][data.provider]["apiKey"] = data.apiKey
        if data.preferredModel is not None:
            updates["aiConfig"][data.provider]["preferredModel"] = data.preferredModel
        if data.endpoint is not None:
            updates["aiConfig"][data.provider]["endpoint"] = data.endpoint
        if data.voice is not None:
            updates["aiConfig"][data.provider]["voice"] = data.voice
        
        await config.update(updates)
        
        return ConfigResponse(
            success=True,
            message=f"AI provider updated to {data.provider}",
            version=config._version
        )
    
    except Exception as e:
        logger.error(f"Error updating AI provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/config/admins", response_model=ConfigResponse)
async def add_admin(
    data: AddAdminRequest,
    authorized: bool = Depends(verify_admin)
):
    """Add admin user ID."""
    try:
        config = get_config_service()
        
        if data.userId in config.dynamic.adminIds:
            raise HTTPException(status_code=400, detail="User already admin")
        
        admins = config.dynamic.adminIds.copy()
        admins.append(data.userId)
        
        await config.update({"adminIds": admins})
        
        return ConfigResponse(
            success=True,
            message=f"Added admin {data.userId}",
            version=config._version
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/config/admins/{user_id}", response_model=ConfigResponse)
async def remove_admin(
    user_id: int,
    authorized: bool = Depends(verify_admin)
):
    """Remove admin user ID."""
    try:
        config = get_config_service()
        
        if user_id not in config.dynamic.adminIds:
            raise HTTPException(status_code=404, detail="User not admin")
        
        admins = [uid for uid in config.dynamic.adminIds if uid != user_id]
        
        if not admins:
            raise HTTPException(status_code=400, detail="Cannot remove last admin")
        
        await config.update({"adminIds": admins})
        
        return ConfigResponse(
            success=True,
            message=f"Removed admin {user_id}",
            version=config._version
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config/version")
async def get_version(authorized: bool = Depends(verify_admin)):
    """Get current config version."""
    config = get_config_service()
    return {
        "version": config._version,
        "lastUpdated": config.dynamic.lastUpdated
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", 5000))
    uvicorn.run(
        "config_api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )