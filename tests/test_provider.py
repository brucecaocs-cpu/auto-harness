import json

import httpx
import pytest

from harness.provider import OpenAICompatProvider


@pytest.mark.asyncio
async def test_chat_parses_tool_calls():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "tool_calls", "message": {
                "content": None,
                "tool_calls": [{"id": "c1", "type": "function",
                                 "function": {"name": "filter_queries", "arguments": '{"keyword":"闹钟","limit":100}'}}]}}]})

    p = OpenAICompatProvider("http://x:4009", "k", "glm-5.2", transport=httpx.MockTransport(handler))
    resp = await p.chat([{"role": "user", "content": "hi"}],
                        tools=[{"type": "function", "function": {"name": "filter_queries", "description": "", "parameters": {}}}])
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["body"]["model"] == "glm-5.2" and "tools" in captured["body"]
    assert resp.tool_calls[0].name == "filter_queries"
    assert resp.tool_calls[0].arguments == {"keyword": "闹钟", "limit": 100}
    await p.aclose()


@pytest.mark.asyncio
async def test_chat_parses_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "答案"}}]})

    p = OpenAICompatProvider("http://x:4009", "k", "glm-5.2", transport=httpx.MockTransport(handler))
    resp = await p.chat([{"role": "user", "content": "hi"}])
    assert resp.content == "答案" and resp.tool_calls == []
    await p.aclose()
