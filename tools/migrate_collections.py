"""
One-time migration: copies data from unsuffixed collections to _prod suffixed ones.

Run from the project root:
    python tools/migrate_collections.py [--dry-run] [--env prod]

The 'config' collection is shared across environments and is NOT migrated.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("migrate")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# All collections that need environment suffix (does NOT include "config" which is shared)
COLLECTIONS = [
    "UserProfiles",
    "AIUsage",
    "AIUsageTracking",
    "UserMemories",
    "Cooldowns",
    "ChatThreads",
    "GuildMembers",
    "ImageLimits",
    "MorningConfigs",
    "Morningconfigs",  # old casing — migrate to MorningConfigs_{env}
    "ShopItems",
    "UserInventory",
]

MORPH_MAP = {
    "Morningconfigs": "MorningConfigs",  # old casing fix
}


async def migrate_collection(
    client: AsyncIOMotorClient,
    db_name: str,
    src_coll: str,
    dst_coll: str,
    dry_run: bool,
) -> tuple[int, int]:
    db = client[db_name]
    src = db[src_coll]

    src_count = await src.count_documents({})
    if src_count == 0:
        logger.info(f"  {src_coll} → {dst_coll}: empty, skipping")
        return 0, 0

    if dry_run:
        logger.info(f"  {src_coll} → {dst_coll}: [DRY RUN] would copy {src_count:,} docs")
        return src_count, 0

    dst = db[dst_coll]
    copied = 0
    async for doc in src.find({}):
        doc.pop("_id", None)  # let MongoDB assign new _id
        await dst.insert_one(doc)
        copied += 1
        if copied % 1000 == 0:
            logger.info(f"  {src_coll} → {dst_coll}: {copied:,}/{src_count:,}")

    dst_count = await dst.count_documents({})
    logger.info(f"  {src_coll} → {dst_coll}: copied {copied:,} docs (target has {dst_count:,})")
    return src_count, dst_count


async def main():
    parser = argparse.ArgumentParser(description="Migrate MongoDB collections to env-suffixed names")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without doing it")
    parser.add_argument("--env", default="prod", help="Target environment suffix (default: prod)")
    parser.add_argument("--config", default="config/base_config.yaml", help="Path to base config YAML")
    args = parser.parse_args()

    env = args.env.lower()
    dry_run = args.dry_run

    # Read MongoDB connection from base_config.yaml
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    mongo_uri = cfg.get("mongoUri")
    db_name = cfg.get("mongoDbName", "bruhbot")

    if not mongo_uri:
        logger.error("mongoUri not found in config")
        sys.exit(1)

    logger.info(f"Connecting to MongoDB: {db_name} (env={env})")
    if dry_run:
        logger.info("*** DRY RUN — no data will be written ***")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    # Verify connection
    await db.command("ping")
    logger.info("Connected")

    total_src = 0
    total_dst = 0
    errors = []

    for coll in COLLECTIONS:
        dst_name = MORPH_MAP.get(coll, coll)

        # Check if source collection exists
        existing = await db.list_collection_names()
        if coll not in existing:
            logger.info(f"  {coll}: source collection does not exist, skipping")
            continue

        # Target collection name: base name + _env suffix
        target = f"{dst_name}_{env}"

        try:
            src, dst = await migrate_collection(client, db_name, coll, target, dry_run)
            total_src += src
            total_dst += dst
        except Exception as e:
            logger.error(f"  {coll} → {target}: ERROR: {e}")
            errors.append((coll, str(e)))

    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}Migration summary:")
    logger.info(f"  Total source docs: {total_src:,}")
    if not dry_run:
        logger.info(f"  Total target docs: {total_dst:,}")

    if errors:
        logger.error(f"\n{len(errors)} collection(s) had errors:")
        for coll, err in errors:
            logger.error(f"  - {coll}: {err}")
    else:
        logger.info("No errors.")

    logger.info("\nNext steps:")
    logger.info(f"  1. Verify data: check {db_name}.<collection>_{env} in MongoDB Compass/shell")
    logger.info("  2. Once confirmed, the old unsuffixed collections can be dropped:")
    for coll in COLLECTIONS:
        logger.info(f"     db.{coll}.drop()  # after verifying migration")
    logger.info("  3. Restart the bot so it picks up the new collections")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
