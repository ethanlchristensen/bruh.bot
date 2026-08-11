"""
Import existing local card sets into MongoDB GridFS.
Uses the shared TradingCardPublisher for all Mongo operations.

Usage:
    poetry run python tools/migrate_trading_card_sets.py --set void_archive --env dev
    poetry run python tools/migrate_trading_card_sets.py --all --env prod
    poetry run python tools/migrate_trading_card_sets.py --all --env prod --replace --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from tools.trading_card_publisher import TradingCardPublisher

logger = logging.getLogger("migrate_tcards")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "bot" / "assets" / "trading_cards"
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


async def migrate_set(pub: TradingCardPublisher, set_id: str, dry_run: bool, replace: bool):
    set_dir = ASSETS_DIR / set_id
    json_path = set_dir / "set.json"
    if not json_path.exists():
        logger.error(f"set.json not found for '{set_id}' at {json_path}")
        return False

    data = json.loads(json_path.read_text(encoding="utf-8"))
    cards = data.get("cards", [])
    packs = data.get("packs", [])

    if not cards:
        logger.error(f"No cards in set '{set_id}'")
        return False

    logger.info(f"Processing '{set_id}' — {len(cards)} cards, {len(packs)} packs")

    if not dry_run:
        await pub.upsert_set(set_id, {
            "display_name": data.get("display_name", set_id),
            "description": data.get("description", ""),
            "base_prompt": data.get("base_prompt", ""),
            "rarity_themes": data.get("rarity_themes", {}),
            "status": "ready",
            "released": True,
            "version": data.get("version", 1),
        })

    # Base template
    for ext in (".png", ".jpg"):
        bt = set_dir / f"base_template{ext}"
        if bt.exists():
            if not dry_run:
                await pub.upload_asset(f"{set_id}_base_template", bt.read_bytes(), f"image/{ext[1:]}", replace=replace)
                logger.info("  Base template uploaded")
            break

    stats = {"uploaded": 0, "skipped": 0, "missing": 0, "conflict": 0, "invalid": 0}

    for card in cards:
        card_id = card.get("card_id")
        if not card_id:
            stats["invalid"] += 1
            continue
        if card.get("rarity", "") not in ("basic", "common", "rare", "epic", "legendary", "diamond", "platinum"):
            stats["invalid"] += 1
            continue

        if not dry_run:
            await pub.upsert_card({**card, "asset_status": "pending", "released": True})

        art_path = card.get("art_path", "")
        fname = Path(art_path).name if art_path else ""
        art_data = None
        ct = "image/png"

        for ext in SUPPORTED_EXTS:
            for candidate in (set_dir / fname, set_dir / fname.replace(".png", ext)):
                if candidate.exists():
                    art_data = candidate.read_bytes()
                    ct = "image/png" if candidate.suffix == ".png" else "image/jpeg"
                    break
            if art_data:
                break

        if not art_data:
            stats["missing"] += 1
            logger.warning(f"  Missing art: {card_id}")
            continue

        if dry_run:
            stats["uploaded"] += 1
        else:
            sha = TradingCardPublisher.compute_sha256(art_data)
            try:
                result = await pub.upload_asset(card_id, art_data, ct, checksum=sha, replace=replace)
            except FileExistsError:
                stats["conflict"] += 1
                logger.warning(f"  Conflict: {card_id}. Use --replace to overwrite.")
                continue
            if result == "skipped":
                stats["skipped"] += 1
            else:
                stats["uploaded"] += 1

    # Packs
    for pk in packs:
        if not pk.get("pack_id"):
            continue
        if not dry_run:
            await pub.upsert_pack({**pk, "released": True})
            logger.info(f"  Pack upserted: {pk['pack_id']}")

    logger.info(f"\n--- {set_id} ---")
    logger.info(f"  Art uploaded: {stats['uploaded']}  skipped: {stats['skipped']}  missing: {stats['missing']}  conflict: {stats['conflict']}")
    return stats["missing"] == 0


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--set")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    if not args.set and not args.all:
        parser.print_help()
        sys.exit(1)

    pub = TradingCardPublisher(env=args.env)
    await pub.connect()

    if args.all and ASSETS_DIR.exists():
        set_ids = [d.name for d in ASSETS_DIR.iterdir() if d.is_dir() and (d / "set.json").exists()]
    elif args.set:
        set_ids = [args.set]
    else:
        logger.error("No sets found.")
        await pub.close()
        sys.exit(1)

    ok = 0
    for sid in sorted(set_ids):
        if await migrate_set(pub, sid, args.dry_run, args.replace):
            ok += 1

    logger.info(f"Done. {ok}/{len(set_ids)} sets OK.")
    await pub.close()


if __name__ == "__main__":
    asyncio.run(main())