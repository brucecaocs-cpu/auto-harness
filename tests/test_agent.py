import json

import pytest

from harness.agent import AgentLoop
from harness.provider import LLMResponse, ToolCall
from harness.tools import Tool, ToolRegistry


class FakeProvider:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def chat(self, messages, tools=None, **kw):
        self.calls += 1
        return self.script.pop(0)


class AddTool(Tool):
    name = "add"
    description = "加法"
    parameters = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}

    async def execute(self, a: int, b: int) -> str:
        return json.dumps({"sum": a + b})


@pytest.mark.asyncio
async def test_tool_call_loop():
    reg = ToolRegistry()
    reg.register(AddTool())
    provider = FakeProvider([
        LLMResponse(content="", tool_calls=[ToolCall(id="c1", name="add", arguments={"a": 2, "b": 3})], finish_reason="tool_calls"),
        LLMResponse(content="2+3=5", tool_calls=[], finish_reason="stop"),
    ])
    loop = AgentLoop(provider, reg, max_iterations=5)
    out = await loop.run("算一下 2+3")
    assert out == "2+3=5"
    assert provider.calls == 2
    assert any(m.get("role") == "tool" and json.loads(m["content"])["sum"] == 5 for m in loop.messages)


@pytest.mark.asyncio
async def test_direct_answer_no_tool():
    reg = ToolRegistry()
    provider = FakeProvider([LLMResponse(content="你好", tool_calls=[], finish_reason="stop")])
    loop = AgentLoop(provider, reg)
    assert await loop.run("hi") == "你好"


@pytest.mark.asyncio
async def test_max_iterations_guard():
    reg = ToolRegistry()
    reg.register(AddTool())
    provider = FakeProvider([LLMResponse(content="", tool_calls=[ToolCall(id="c", name="add", arguments={"a": 1, "b": 1})]) for _ in range(10)])
    loop = AgentLoop(provider, reg, max_iterations=3)
    out = await loop.run("x")
    assert "最大" in out
