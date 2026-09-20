from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from typing import Any

from pydantic import BaseModel

from verify.domain.models import EmailMessage


class LLMCallMeta(BaseModel):
    provider: str
    model: str
    task: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        images: list[bytes] | None = None,
    ) -> tuple[BaseModel, LLMCallMeta]:
        raise NotImplementedError


class OCRResult(BaseModel):
    text: str
    confidence: float
    pages: int = 1


class OCRProvider(ABC):
    name: str

    @abstractmethod
    async def read_image(self, payload: bytes, filename: str) -> OCRResult:
        raise NotImplementedError


class MailSource(ABC):
    name: str

    @abstractmethod
    def emails(self) -> Iterable[EmailMessage]:
        raise NotImplementedError

    async def watch(self) -> AsyncIterator[EmailMessage]:
        for email in self.emails():
            yield email


class BlobStore(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get(self, key: str) -> bytes:
        raise NotImplementedError


class QueueMessage(BaseModel):
    id: str
    body: dict[str, Any]


class Queue(ABC):
    @abstractmethod
    async def send(self, queue_name: str, body: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        raise NotImplementedError
