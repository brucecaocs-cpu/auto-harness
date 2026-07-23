import json
from types import SimpleNamespace

import pytest

from harness.data_tools import build_data_tools
from harness.dataset import Dataset


class _FakeProvider:
    async def chat(self, messages, **kw):
        return SimpleNamespace(content='{"categories": ["闹钟与提醒", "系统设置与开关控制"], "sub_intents": ["设置闹钟提醒"]}')


@pytest.mark.asyncio
async def test_find_relevant_categories(sample_csv, tmp_path):
    ds = Dataset(sample_csv)
    provider = _FakeProvider()
    tools = {t.name: t for t in build_data_tools(ds, tmp_path / "out", provider)}
    assert "find_relevant_categories" in tools
    out = json.loads(await tools["find_relevant_categories"].execute(topic="闹钟"))
    assert "闹钟与提醒" in out["categories"]
    assert "设置闹钟提醒" in out["sub_intents"]


def test_no_provider_no_tool(sample_csv, tmp_path):
    ds = Dataset(sample_csv)
    tools = {t.name: t for t in build_data_tools(ds, tmp_path / "out")}
    assert "find_relevant_categories" not in tools
