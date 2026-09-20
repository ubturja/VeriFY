from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel

from verify.providers.base import LLMCallMeta, LLMProvider
from verify.providers.llm.gemini import _UNTRUSTED_WRAP


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, default_model: str) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY is empty.")
        self.api_key = api_key
        self.default_model = default_model

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        images: list[bytes] | None = None,
        model: str | None = None,
    ) -> tuple[BaseModel, LLMCallMeta]:
        chosen = model or self.default_model
        body: dict[str, Any] = {
            "model": chosen,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                },
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": _UNTRUSTED_WRAP + user},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        parsed = schema.model_validate(json.loads(text))
        usage = payload.get("usage") or {}
        meta = LLMCallMeta(
            provider=self.name,
            model=chosen,
            task=task,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )
        return parsed, meta
