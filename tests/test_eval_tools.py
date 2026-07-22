import json
from types import SimpleNamespace

import pytest

from harness.eval_tools import build_eval_tools


class _StubProvider:
    async def chat(self, messages, **kw):
        return SimpleNamespace(content=(
            '<analysis>分析</analysis>\n'
            '{"rubric": {"准确性": 4, "完整性": 4, "相关性": 5, "有用性": 4, "安全性": 5}, '
            '"correctness": "right", "rationale": "基本正确"}'))


@pytest.mark.asyncio
async def test_evaluate_response_tool():
    tools = {t.name: t for t in build_eval_tools(_StubProvider())}
    assert "evaluate_response" in tools
    out = json.loads(await tools["evaluate_response"].execute(query="定个闹钟", response="好的，已为你设定明天7点的闹钟"))
    assert out["correctness"] == "right"
    assert out["rubric"]["相关性"] == 5
    assert out["total"] == 4.4
    assert out["rationale"]
