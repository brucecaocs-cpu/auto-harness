"""OpenAI 兼容 provider（适配精简自 nanobot providers/openai_compat_provider）。非流式 chat + function calling。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 180.0, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            transport=transport,
        )

    async def chat(self, messages, tools=None, temperature=0.1, max_tokens=4096) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
                                   "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        resp = await self._client.post(f"{self.base_url}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        msg = choice.get("message", {})
        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
        return LLMResponse(content=msg.get("content") or "", tool_calls=calls,
                           finish_reason=choice.get("finish_reason", "stop"))

    async def aclose(self) -> None:
        await self._client.aclose()
