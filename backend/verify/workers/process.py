"""Queue consumer and IMAP poller. Locally the API can process inline; in Azure
this process is a Container Apps replica scaled by KEDA on queue depth."""

from __future__ import annotations

import asyncio

from verify.api.app import _read, llm, settings, store
from verify.services.mail_poll import poll_loop


async def run() -> None:
    print(f"VeriFY worker in {settings.env} (queue={settings.queue_backend}, mailbox={settings.imap_username})")
    if settings.imap_username and settings.imap_app_password:
        await poll_loop(settings, store=store, read=_read, llm=llm)
        return
    while True:
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run())
