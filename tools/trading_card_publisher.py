"""
Shared Mongo/GridFS publish layer for trading card sets.
Used by both card_gen.py (direct-to-Mongo) and migrate_trading_card_sets.py (local import).
"""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

logger = logging.getLogger("tcard_publisher")

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


class TradingCardPublisher:
    def __init__(self, config_path: str = "config/base_config.yaml", env: str = "dev"):
        self.env = env
        self.config_path = Path(config_path)
        self.client = None
        self.db = None
        self.sets_col = None
        self.catalog_col = None
        self.packs_col = None
        self.gridfs = None
        self.db_name = ""

    async def connect(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        with open(self.config_path) as f:
            cfg = yaml.safe_load(f)

        mongo_uri = cfg.get("mongoUri")
        self.db_name = cfg.get("mongoDbName", "bruhbot")
        if not mongo_uri:
            raise ValueError("mongoUri not found in config")

        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[self.db_name]
        await self.db.command("ping")
        logger.info(f"Connected to {self.db_name} (env={self.env})")

        self.sets_col = self.db[f"TradingCardSets_{self.env}"]
        self.catalog_col = self.db[f"TradingCardCatalog_{self.env}"]
        self.packs_col = self.db[f"TradingCardPacks_{self.env}"]
        bucket_name = f"TradingCardAssets_{self.env}"
        self.gridfs = AsyncIOMotorGridFSBucket(self.db, bucket_name=bucket_name)

        await self._ensure_indexes()

    async def _ensure_indexes(self):
        try:
            await self.sets_col.create_index("set_id", unique=True, sparse=True)
            await self.catalog_col.create_index("card_id", unique=True, sparse=True)
            await self.catalog_col.create_index("set_id")
            await self.catalog_col.create_index("asset_status")
            await self.packs_col.create_index("pack_id", unique=True, sparse=True)
            await self.db[f"TradingCardAssets_{self.env}.files"].create_index("filename")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    async def close(self):
        if self.client:
            self.client.close()

    # ── Set operations ──
    async def upsert_set(self, set_id: str, data: dict):
        now = datetime.now(UTC)
        doc = {
            "set_id": set_id,
            "display_name": data.get("display_name", set_id),
            "description": data.get("description", ""),
            "base_prompt": data.get("base_prompt", ""),
            "rarity_themes": data.get("rarity_themes", {}),
            "status": data.get("status", "draft"),
            "released": data.get("released", False),
            "version": data.get("version", 1),
            "generation_model": data.get("generation_model", ""),
            "updated_at": now,
        }
        await self.sets_col.replace_one({"set_id": set_id}, doc, upsert=True)

    async def get_set(self, set_id: str) -> dict | None:
        return await self.sets_col.find_one({"set_id": set_id})

    async def publish_set(self, set_id: str):
        now = datetime.now(UTC)
        await self.sets_col.update_one(
            {"set_id": set_id},
            {"$set": {"status": "ready", "released": True, "published_at": now, "updated_at": now}},
        )

    async def archive_set(self, set_id: str):
        await self.sets_col.update_one({"set_id": set_id}, {"$set": {"released": False, "updated_at": datetime.now(UTC)}})
        await self.packs_col.update_many({"set_id": set_id}, {"$set": {"released": False}})

    # ── Card catalog operations ──
    async def upsert_card(self, card: dict):
        now = datetime.now(UTC)
        doc = {
            "card_id": card["card_id"],
            "set_id": card.get("series_id") or card.get("set_id", ""),
            "number": card["number"],
            "name": card["name"],
            "rarity": card["rarity"],
            "description": card.get("description", ""),
            "friendly_description": card.get("friendly_description", ""),
            "friendly_description_status": card.get("friendly_description_status", "pending"),
            "friendly_description_error": card.get("friendly_description_error"),
            "friendly_description_updated_at": card.get("friendly_description_updated_at"),
            "tradable": card.get("tradable", True),
            "released": False,
            "asset_status": card.get("asset_status", "pending"),
            "asset_filename": card.get("asset_filename"),
            "asset_sha256": card.get("asset_sha256"),
            "asset_content_type": card.get("asset_content_type"),
            "asset_error": card.get("asset_error"),
            "asset_attempts": card.get("asset_attempts", 0),
            "asset_updated_at": now,
            "updated_at": now,
        }
        await self.catalog_col.replace_one({"card_id": card["card_id"]}, doc, upsert=True)

    async def get_cards_by_status(self, set_id: str, *statuses: str) -> list[dict]:
        cursor = self.catalog_col.find({"set_id": set_id, "asset_status": {"$in": list(statuses)}}).sort("number", 1)
        return await cursor.to_list(length=200)

    async def get_all_cards(self, set_id: str) -> list[dict]:
        cursor = self.catalog_col.find({"set_id": set_id}).sort("number", 1)
        return await cursor.to_list(length=200)

    async def get_set_status(self, set_id: str) -> dict:
        total = await self.catalog_col.count_documents({"set_id": set_id})
        ready = await self.catalog_col.count_documents({"set_id": set_id, "asset_status": "ready"})
        pending = await self.catalog_col.count_documents({"set_id": set_id, "asset_status": "pending"})
        failed = await self.catalog_col.count_documents({"set_id": set_id, "asset_status": "failed"})
        sd = await self.get_set(set_id)
        return {
            "set_id": set_id,
            "display_name": sd.get("display_name", set_id) if sd else set_id,
            "status": sd.get("status", "unknown") if sd else "unknown",
            "released": sd.get("released", False) if sd else False,
            "total_cards": total,
            "ready": ready,
            "pending": pending,
            "failed": failed,
        }

    # ── Pack operations ──
    async def upsert_pack(self, pack: dict):
        guaranteed = pack.get("guaranteed_rarity")
        doc = {
            "pack_id": pack["pack_id"],
            "set_id": pack.get("series_id") or pack.get("set_id", ""),
            "name": pack["name"],
            "price": pack["price"],
            "cards_per_pack": pack["cards_per_pack"],
            "guaranteed_rarity": guaranteed,
            "description": pack.get("description", ""),
            "released": pack.get("released", False),
        }
        await self.packs_col.replace_one({"pack_id": pack["pack_id"]}, doc, upsert=True)

    # ── GridFS asset operations ──
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    async def get_asset_checksum(self, card_id: str) -> str | None:
        try:
            grid_out = await self.gridfs.open_download_stream_by_name(card_id)
            data = await grid_out.read()
            return self.compute_sha256(data)
        except Exception:
            return None

    async def upload_asset(self, card_id: str, data: bytes, content_type: str = "image/png",
                           metadata: dict | None = None, replace: bool = False, checksum: str | None = None) -> str:
        if not replace:
            existing = await self.get_asset_checksum(card_id)
            new_hash = checksum or self.compute_sha256(data)
            if existing is not None:
                if existing == new_hash:
                    return "skipped"
                raise FileExistsError(f"Asset for {card_id} exists with different checksum. Use replace=True.")

        if replace:
            try:
                await self.gridfs.open_download_stream_by_name(card_id)
                await self.gridfs.delete_many({"filename": card_id})
            except Exception:
                pass

        m = metadata or {}
        m["sha256"] = checksum or self.compute_sha256(data)
        m["content_type"] = content_type

        await self.gridfs.upload_from_stream(card_id, data, metadata=m)
        return "uploaded"

    async def get_asset_bytes(self, card_id: str) -> bytes | None:
        try:
            grid_out = await self.gridfs.open_download_stream_by_name(card_id)
            return await grid_out.read()
        except Exception:
            return None
