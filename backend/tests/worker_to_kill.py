import asyncio
import sys
from app import runtime


async def slow(*args):
    await asyncio.sleep(30)


runtime.execute = slow
asyncio.run(runtime.run_task(sys.argv[1]))
