import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.trading_card_publisher import TradingCardPublisher

SETS = [
    'moss_and_sunbeam',
    'protocol_42',
    'prismatic_trench',
    'void_archive',
    'bruh_cards',
]

async def fix():
    pub = TradingCardPublisher(env='prod')
    await pub.connect()
    for set_id in SETS:
        c = await pub.catalog_col.update_many(
            {'set_id': set_id},
            {'$set': {'released': True}},
        )
        p = await pub.packs_col.update_many(
            {'set_id': set_id},
            {'$set': {'released': True}},
        )
        print(f'{set_id}: {c.modified_count} cards, {p.modified_count} packs')
    await pub.close()

asyncio.run(fix())
