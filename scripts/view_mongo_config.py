"""
View the current configuration stored in MongoDB.
Useful for debugging and verifying your config.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

import yaml
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient


async def view_config():
    print("=" * 70)
    print("VIEW MONGODB CONFIGURATION")
    print("=" * 70)

    # Load base config
    base_config_path = "config/base_config.yaml"
    if not os.path.exists(base_config_path):
        print(f"\nError: {base_config_path} not found!")
        return

    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)

    # Connect to MongoDB
    client = AsyncIOMotorClient(base_config["mongoUri"])
    db = client[base_config["mongoDbName"]]
    collection_name = base_config.get("mongoConfigCollectionName", "bot_config")
    collection = db[collection_name]

    # Fetch config
    config_doc = await collection.find_one({"_id": "main"})

    if not config_doc:
        print("\n⚠ No configuration found in MongoDB!")
        print("Run migrate_config_to_mongo.py first.")
        return

    # Remove _id for cleaner display
    config_doc.pop("_id", None)

    print("\nConfiguration from MongoDB:")
    print(f"Database: {base_config['mongoDbName']}")
    print(f"Collection: {collection_name}")
    print(f"Version: {config_doc.get('configVersion', 'unknown')}")
    print(f"Last Updated: {config_doc.get('lastUpdated', 'never')}")

    # Ask if user wants to see encrypted or decrypted
    print("\n" + "-" * 70)
    choice = input("\nShow (e)ncrypted or (d)ecrypted API keys? [e/d]: ").lower()

    if choice == "d":
        # Decrypt API keys
        cipher = Fernet(base_config["encryptionKey"].encode())

        if "aiConfig" in config_doc and config_doc["aiConfig"]:
            ai_config = config_doc["aiConfig"]

            for provider in ["openai", "antropic", "gemini", "elevenlabs"]:
                if provider in ai_config and ai_config[provider] and "apiKey" in ai_config[provider]:
                    encrypted_key = ai_config[provider]["apiKey"]
                    if encrypted_key:
                        try:
                            decrypted_key = cipher.decrypt(encrypted_key.encode()).decode()
                            ai_config[provider]["apiKey"] = decrypted_key
                        except Exception as e:
                            ai_config[provider]["apiKey"] = f"<DECRYPTION ERROR: {e}>"

            if "realTimeConfig" in ai_config and ai_config["realTimeConfig"] and "apiKey" in ai_config["realTimeConfig"]:
                encrypted_key = ai_config["realTimeConfig"]["apiKey"]
                if encrypted_key:
                    try:
                        decrypted_key = cipher.decrypt(encrypted_key.encode()).decode()
                        ai_config["realTimeConfig"]["apiKey"] = decrypted_key
                    except Exception as e:
                        ai_config["realTimeConfig"]["apiKey"] = f"<DECRYPTION ERROR: {e}>"

    # Pretty print the config
    print("\n" + "=" * 70)
    print(json.dumps(config_doc, indent=2, default=str))
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(view_config())
