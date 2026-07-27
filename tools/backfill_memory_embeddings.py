"""
One-shot script to backfill missing embeddings on existing user memories.
Uses direct yaml + motor access — no bot imports needed.

Usage:
  python tools/backfill_memory_embeddings.py --guild ID [--env dev|prod] [--dry-run]
  python tools/backfill_memory_embeddings.py --guild ID --env prod
"""

import argparse
import asyncio
import logging
import os
import sys

import httpx
import yaml
from bson import Int64
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backfill")

BATCH_SIZE = 50
CONFIG_PATH = "config/base_config.yaml"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guild", type=int, required=True, help="Guild ID to backfill memories for")
    parser.add_argument("--env", type=str, default=None, help="Environment: dev or prod (default: $ENVIRONMENT or dev)")
    parser.add_argument("--dry-run", action="store_true", help="Count missing without embedding")
    args = parser.parse_args()

    env = args.env or os.getenv("ENVIRONMENT", "dev").lower()
    if env not in ("dev", "prod"):
        logger.error(f"Unknown environment: {env}. Must be 'dev' or 'prod'")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f)

    client = AsyncIOMotorClient(raw["mongoUri"])
    db = client[raw["mongoDbName"]]

    base_collection_name = raw.get("mongoUserMemoriesCollectionName", "UserMemories")
    collection_name = f"{base_collection_name}_{env}"
    collection = db[collection_name]
    config_collection = db["config"]

    logger.info(f"Environment: {env}, DB: {raw['mongoDbName']}, Collection: {collection_name}")

    config_doc = await config_collection.find_one({"guildId": str(args.guild)})
    if not config_doc:
        logger.error(f"No config found for guild {args.guild}")
        sys.exit(1)

    memory_config = config_doc.get("memoryConfig", {})
    if not memory_config.get("enabled", True):
        logger.info("Memory extraction is disabled for this guild. Aborting.")
        return

    embedding_model = memory_config.get("embeddingModel") or "openai/text-embedding-3-small"
    embedding_dimensions = memory_config.get("embeddingDimensions") or 1536

    ai_config = config_doc.get("aiConfig", {})
    openrouter_cfg = ai_config.get("openrouter", {})
    api_key = openrouter_cfg.get("apiKey", "")

    if api_key:
        cipher = Fernet(raw["encryptionKey"].encode())
        try:
            api_key = cipher.decrypt(api_key.encode()).decode()
        except Exception:
            pass

    if not api_key:
        logger.error("No OpenRouter API key configured for this guild")
        sys.exit(1)

    query = {
        "guild_id": Int64(args.guild),
        "$or": [
            {"embedding": {"$exists": False}},
            {"embedding": None},
            {"embedding_model": {"$ne": embedding_model}},
        ],
    }

    total_missing = await collection.count_documents(query)
    logger.info(f"Found {total_missing} memories missing embeddings in guild {args.guild}")

    if args.dry_run or total_missing == 0:
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mesh.etchris.dev",
        "X-Title": "bruh.bot",
    }

    processed = 0
    cursor = collection.find(query).batch_size(BATCH_SIZE)

    while True:
        batch = []
        async for doc in cursor:
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                break

        if not batch:
            break

        texts = [doc["memory"] for doc in batch]

        try:
            async with httpx.AsyncClient(http2=True) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    json={"model": embedding_model, "input": texts, "dimensions": embedding_dimensions},
                    headers=headers,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()

            embeddings = [entry["embedding"] for entry in data.get("data", [])]

            for doc, emb in zip(batch, embeddings):
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": emb, "embedding_model": embedding_model}},
                )
                processed += 1

            logger.info(f"Embedded {processed}/{total_missing} memories...")

        except Exception as e:
            logger.error(f"Batch failed: {e}")
            break

    logger.info(f"Done. Embedded {processed} memories.")


if __name__ == "__main__":
    asyncio.run(main())