import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.trading_card_publisher import TradingCardPublisher


async def fix():
    pub = TradingCardPublisher(env='prod')
    await pub.connect()
    cr = await pub.catalog_col.update_many({}, {'$set': {'released': True}})
    pr = await pub.packs_col.update_many({}, {'$set': {'released': True}})
    print(f'Cards fixed: {cr.modified_count}, Packs fixed: {pr.modified_count}')
    await pub.close()


asyncio.run(fix())
