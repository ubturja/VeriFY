"""Queue consumer entrypoint. Locally the API can process inline; in Azure this
process is a Container Apps replica scaled by KEDA on queue depth."""

from __future__ import annotations

import asyncio

from verify.config import get_settings


async def run() -> None:
    settings = get_settings()
    print(f"VeriFY worker idle in {settings.env} (queue={settings.queue_backend})")
    while True:
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run())
