"""
Seed play-to-earn game data (hangman words, wordle words, trivia questions)
into MongoDB so the answer key is not shipped in the public repo.

The bot loads this data from the EarnGamesData_<env> collection at startup
(see bot/services/earn_games_service.py).  Keep the source JSON files local
and gitignored — only this script needs them.

Usage:
    poetry run python tools/seed_earn_games.py --env dev
    poetry run python tools/seed_earn_games.py --env prod --data-dir bot/data
"""

import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_earn_games")

# Matches BaseConfig.mongoEarnGamesDataCollectionName
COLLECTION_BASE = "EarnGamesData"

DATA_FILES = {
    "hangman_words": "hangman_words.json",
    "wordle_words": "wordle_words.json",
    "trivia_questions": "trivia_questions.json",
}

WORDLE_WORD_LENGTH = 5


def validate_trivia(items: list[dict]):
    for i, q in enumerate(items):
        options = q.get("options")
        answer = q.get("answer")
        if not q.get("q") or not isinstance(options, list) or len(options) != 4 or not isinstance(answer, int) or not 0 <= answer < 4:
            raise ValueError(f"Invalid trivia question at index {i}: {q}")


def validate_words(items: list[str], *, length: int | None = None):
    for i, word in enumerate(items):
        if not isinstance(word, str) or not word.isalpha():
            raise ValueError(f"Invalid word at index {i}: {word!r}")
        if length is not None and len(word) != length:
            raise ValueError(f"Word {word!r} is not {length} letters")


async def seed(env: str, data_dir: Path, config_path: Path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    mongo_uri = cfg.get("mongoUri")
    db_name = cfg.get("mongoDbName", "bruhbot")
    if not mongo_uri:
        raise ValueError("mongoUri not found in config")

    client = AsyncIOMotorClient(mongo_uri)
    col = client[db_name][f"{COLLECTION_BASE}_{env}"]
    await col.create_index("dataset", unique=True)

    now = datetime.now(UTC)
    for dataset, filename in DATA_FILES.items():
        path = data_dir / filename
        if not path.exists():
            logger.warning("Skipping %s: file not found at %s", dataset, path)
            continue

        items = json.loads(path.read_text(encoding="utf-8"))
        if dataset == "trivia_questions":
            validate_trivia(items)
        elif dataset == "wordle_words":
            validate_words(items, length=WORDLE_WORD_LENGTH)
        else:
            validate_words(items)

        await col.update_one(
            {"dataset": dataset},
            {"$set": {"dataset": dataset, "items": items, "updated_at": now}},
            upsert=True,
        )
        logger.info("Seeded %s: %d items", dataset, len(items))

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Seed play-to-earn game data into MongoDB")
    parser.add_argument("--env", default="dev", choices=["dev", "prod"], help="Environment to seed (default: dev)")
    parser.add_argument("--data-dir", default="bot/data", help="Directory containing the JSON data files (default: bot/data)")
    parser.add_argument("--config", default="config/base_config.yaml", help="Path to the base config YAML (default: config/base_config.yaml)")
    args = parser.parse_args()

    asyncio.run(seed(args.env, Path(args.data_dir), Path(args.config)))


if __name__ == "__main__":
    main()
