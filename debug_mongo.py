import asyncio

import yaml
from bson import Int64
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    with open("config/base_config.yaml") as f:
        raw = yaml.safe_load(f)
    client = AsyncIOMotorClient(raw["mongoUri"])
    db = client[raw["mongoDbName"]]
    guild = 1069835760859107368

    for env in ("prod",):
        coll_name = f"{raw.get('mongoUserMemoriesCollectionName', 'UserMemories')}_{env}"
        coll = db[coll_name]
        total = await coll.count_documents({})
        print(f"env={env} collection={coll_name} total_docs={total}")

        if total > 0:
            doc = await coll.find_one({})
            print(f"  sample doc keys: {list(doc.keys())}")
            gid = doc.get("guild_id")
            print(f"  guild_id value={gid} type={type(gid).__name__} repr={repr(gid)}")

            by_int64 = await coll.count_documents({"guild_id": Int64(guild)})
            by_int = await coll.count_documents({"guild_id": guild})
            no_embed = await coll.count_documents({"guild_id": Int64(guild), "embedding": {"$exists": False}})
            embed_null = await coll.count_documents({"guild_id": Int64(guild), "embedding": None})
            print(f"  by_Int64={by_int64} by_int={by_int} no_embed={no_embed} embed_null={embed_null}")

            if by_int64 > 0:
                mem = await coll.find_one({"guild_id": Int64(guild)})
                emb = mem.get("embedding", "<<MISSING>>")
                print(f"  memory: {mem.get('memory', 'N/A')[:80]}")
                print(f"  embedding: {emb if isinstance(emb, str) else type(emb).__name__ + ' len=' + str(len(emb) if emb else 0) if emb else repr(emb)}")


asyncio.run(main())
