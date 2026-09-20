"""Microsoft Graph adapter.

Implemented as a documented contract for Averis's Outlook tenant. The live
demo uses IMAP or the hackathon inbox. Wiring requires an Entra app in that tenant.
"""

from __future__ import annotations

from collections.abc import Iterable

from verify.domain.models import EmailMessage
from verify.providers.base import MailSource


class GraphMailSource(MailSource):
    name = "graph"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, mailbox: str) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.mailbox = mailbox

    def emails(self) -> Iterable[EmailMessage]:
        raise NotImplementedError(
            "Graph ingest is enabled in Averis's tenant. Configure AZURE_AD_* and a mailbox."
        )
