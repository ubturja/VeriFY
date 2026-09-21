"""Queue consumer and IMAP poller. Locally the API can process inline; in Azure
this process is a Container Apps replica scaled by KEDA on queue depth.

Iterates every mailbox registered in the tenant registry so a single worker
serves every reviewer that has signed in.
"""

from __future__ import annotations

import asyncio

from verify.api.app import _read, llm, settings, tenants
from verify.services.mail_poll import poll_loop


async def run() -> None:
    mailboxes = [tenant.email for tenant in tenants.all() if tenant.imap_password_encrypted]
    print(
        f"VeriFY worker in {settings.env} "
        f"(queue={settings.queue_backend}, mailboxes={mailboxes or 'none'})"
    )
    await poll_loop(settings, registry=tenants, read=_read, llm=llm)


if __name__ == "__main__":
    asyncio.run(run())
