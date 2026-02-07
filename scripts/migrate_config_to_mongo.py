"""
Migrate existing config.yaml to MongoDB.
This script reads your current config.yaml and creates the initial MongoDB configuration.
Run this once to set up your MongoDB config collection.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient


async def migrate_config():
    print("=" * 70)
    print("CONFIG MIGRATION TO MONGODB")
    print("=" * 70)

    # Load base config to get MongoDB connection details and encryption key
    base_config_path = "config/base_config.yaml"
    if not os.path.exists(base_config_path):
        print(f"\nError: {base_config_path} not found!")
        print("Please create base_config.yaml with your secrets first.")
        return

    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)

    # Load existing config.yaml
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        print(f"\nError: {config_path} not found!")
        return

    with open(config_path) as f:
        existing_config = yaml.safe_load(f)

    print(f"\n✓ Loaded existing config from {config_path}")

    # Create dynamic config from existing config
    dynamic_config_dict = {
        "adminIds": existing_config.get("adminIds", []),
        "invisible": existing_config.get("invisible", False),
        "aiConfig": existing_config.get("aiConfig", {}),
        "usersToId": existing_config.get("usersToId", {}),
        "idToUsers": existing_config.get("idToUsers", {}),
        "mentionCooldown": existing_config.get("mentionCooldown", 20),
        "cooldownBypassList": existing_config.get("cooldownBypassList", []),
        "promptsPath": existing_config.get("promptsPath", "prompts.json"),
        "mongoMessagesCollectionName": existing_config.get("mongoMessagesCollectionName", "Messages"),
        "mongoMorningConfigsCollectionName": existing_config.get("mongoMorningConfigsCollectionName", "MorningConfigs"),
        "mongoImageLimitsCollectionName": existing_config.get("mongoImageLimitsCollectionName", "ImageLimits"),
        "allowedBotsToRespondTo": existing_config.get("allowedBotsToRespondTo", []),
        "deleteUserMessages": existing_config.get("deleteUserMessages", {"enabled": False, "userIds": []}),
        "globalBlockList": existing_config.get("globalBlockList", []),
        "configVersion": 1,
    }

    # Encrypt API keys
    cipher = Fernet(base_config["encryptionKey"].encode())

    if "aiConfig" in dynamic_config_dict and dynamic_config_dict["aiConfig"]:
        ai_config = dynamic_config_dict["aiConfig"]

        # Encrypt API keys for each provider
        for provider in ["openai", "antropic", "google", "elevenlabs"]:
            if provider in ai_config and ai_config[provider] and "apiKey" in ai_config[provider]:
                api_key = ai_config[provider]["apiKey"]
                if api_key:
                    encrypted_key = cipher.encrypt(api_key.encode()).decode()
                    ai_config[provider]["apiKey"] = encrypted_key
                    print(f"✓ Encrypted {provider} API key")

        # Encrypt realTimeConfig API key
        if "realTimeConfig" in ai_config and ai_config["realTimeConfig"] and "apiKey" in ai_config["realTimeConfig"]:
            api_key = ai_config["realTimeConfig"]["apiKey"]
            if api_key:
                encrypted_key = cipher.encrypt(api_key.encode()).decode()
                ai_config["realTimeConfig"]["apiKey"] = encrypted_key
                print("✓ Encrypted realTimeConfig API key")

    # Connect to MongoDB
    print("\n✓ Connecting to MongoDB...")
    client = AsyncIOMotorClient(base_config["mongoUri"])
    db = client[base_config["mongoDbName"]]
    collection_name = base_config.get("mongoConfigCollectionName", "bot_config")
    collection = db[collection_name]

    # Check if config already exists
    existing_doc = await collection.find_one({"_id": "main"})
    if existing_doc:
        print("\n⚠ WARNING: Configuration already exists in MongoDB!")
        response = input("Do you want to overwrite it? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("Migration cancelled.")
            return

    # Insert/update configuration
    await collection.update_one({"_id": "main"}, {"$set": dynamic_config_dict}, upsert=True)

    print("\n✓ Configuration migrated to MongoDB successfully!")
    print(f"  Database: {base_config['mongoDbName']}")
    print(f"  Collection: {collection_name}")
    print(f"  Version: {dynamic_config_dict['configVersion']}")

    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Update your bot initialization to use the new async config service")
    print("2. Start the config watcher in your bot")
    print("3. Set up the FastAPI endpoints for config management")
    print("4. Build your frontend UI to manage the config")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(migrate_config())
