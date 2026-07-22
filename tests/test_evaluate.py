import json
from types import SimpleNamespace

import pytest

from harness import evaluate as ev


def test_extract_json_plain():
    assert ev.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fence():
    assert ev.extract_json('一些前言\n```json\n{"a": 2}\n```\n收尾') == {"a": 2}


def test_extract_json_with_analysis_prefix():
    text = '<analysis>这是分析</analysis>\n{"rubric": {"准确性": 5}, "correctness": "right"}'
    data = ev.extract_json(text)
    assert data["correctness"] == "right"


def test_extract_json_invalid_raises():
    with pytest.raises((ValueError, json.JSONDecodeError)):
        ev.extract_json("完全没有 JSON")


def test_build_prompt_includes_key_parts():
    msgs = ev.build_judge_prompt("今天天气", "晴天", reference="参考", dimensions=["准确性", "相关性"])
    user = msgs[1]["content"]
    assert "今天天气" in user and "晴天" in user and "参考" in user
    assert "准确性" in user and "相关性" in user


class _StubProvider:
    def __init__(self, *contents):
        self._contents = list(contents)
        self.calls = 0

    async def chat(self, messages, **kw):
        self.calls += 1
        return SimpleNamespace(content=self._contents.pop(0))


@pytest.mark.asyncio
async def test_evaluate_parses_verdict():
    content = ('<analysis>回答正确且完整</analysis>\n'
               '{"rubric": {"准确性": 5, "完整性": 4, "相关性": 5, "有用性": 4, "安全性": 5}, '
               '"correctness": "right", "rationale": "命中要点"}')
    p = _StubProvider(content)
    v = await ev.evaluate(p, "q", "r")
    assert v["correctness"] == "right"
    assert v["rubric"]["准确性"] == 5
    assert v["total"] == 4.6
    assert v["rationale"] == "命中要点"
    assert "正确" in v["analysis"]


@pytest.mark.asyncio
async def test_evaluate_coerces_bad_correctness():
    content = '{"rubric": {"准确性": 3}, "correctness": "banana", "rationale": "x"}'
    p = _StubProvider(content)
    v = await ev.evaluate(p, "q", "r", dimensions=["准确性"])
    assert v["correctness"] == "unclear"
    assert v["total"] == 3.0


@pytest.mark.asyncio
async def test_evaluate_repairs_malformed():
    bad = "rubric: 准确性5分，correctness right（非JSON）"
    good = '{"rubric": {"准确性": 5}, "correctness": "right", "rationale": "ok"}'
    p = _StubProvider(bad, good)
    v = await ev.evaluate(p, "q", "r", dimensions=["准确性"])
    assert p.calls == 2
    assert v["correctness"] == "right"
