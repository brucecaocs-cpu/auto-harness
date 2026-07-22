import json

import pytest

from harness.tools import Tool, ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "回显文本"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, text: str) -> str:
        return json.dumps({"echo": text}, ensure_ascii=False)


@pytest.mark.asyncio
async def test_register_and_schema():
    reg = ToolRegistry()
    reg.register(EchoTool())
    defs = reg.get_definitions()
    assert defs[0]["type"] == "function"
    assert defs[0]["function"]["name"] == "echo"


@pytest.mark.asyncio
async def test_execute_ok():
    reg = ToolRegistry()
    reg.register(EchoTool())
    out = await reg.execute("echo", {"text": "hi"})
    assert json.loads(out)["echo"] == "hi"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    reg = ToolRegistry()
    out = await reg.execute("nope", {})
    assert "unknown tool" in json.loads(out)["error"]


@pytest.mark.asyncio
async def test_execute_bad_args():
    reg = ToolRegistry()
    reg.register(EchoTool())
    out = await reg.execute("echo", {"wrong": 1})
    assert "error" in json.loads(out)
