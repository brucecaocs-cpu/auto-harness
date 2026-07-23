"""harness 工具 → nanobot Tool 适配层。

让 nanobot 的 agent loop/gateway/WebUI 能发现和使用 auto-harness 的数据集确定 + 自动化评估工具。
通过 nanobot.tools entry point 自动发现（pyproject.toml 注册）。
"""
from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool as NanobotTool, tool_parameters

from harness.config import load_settings
from harness.data_tools import build_data_tools
from harness.dataset import Dataset
from harness.eval_tools import build_eval_tools
from harness.provider import OpenAICompatProvider
from harness.tools import ToolRegistry

_tools: dict[str, Any] = {}
_setup_done = False


def _setup():
    global _setup_done, _tools
    if _setup_done:
        return
    settings = load_settings()
    ds = Dataset(settings.csv_path)
    provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model)
    registry = ToolRegistry()
    for t in build_data_tools(ds, settings.output_dir, provider):
        registry.register(t)
    for t in build_eval_tools(provider):
        registry.register(t)
    _tools = registry._tools  # internal access: name→Tool map
    _setup_done = True


async def _harness_call(name: str, **kwargs: Any) -> str:
    _setup()
    tool = _tools.get(name)
    if tool is None:
        return f"unknown harness tool: {name}"
    return await tool.execute(**kwargs)


class _HarnessAdapter(NanobotTool):
    _hn: str = ""  # harness tool name

    @property
    def name(self) -> str:
        return self._hn

    @property
    def description(self) -> str:
        _setup()
        return _tools[self._hn].description if self._hn in _tools else ""

    @property
    def parameters(self) -> dict[str, Any]:
        _setup()
        return _tools[self._hn].parameters if self._hn in _tools else {}

    async def execute(self, **kwargs: Any) -> str:
        return await _harness_call(self._hn, **kwargs)


# -- 7 个适配工具 --

class DatasetStatsTool(_HarnessAdapter):
    _hn = "dataset_stats"

class ListTopCategoriesTool(_HarnessAdapter):
    _hn = "list_top_categories"

class ListSubIntentsTool(_HarnessAdapter):
    _hn = "list_sub_intents"

class FilterQueriesTool(_HarnessAdapter):
    _hn = "filter_queries"

class SampleQueriesTool(_HarnessAdapter):
    _hn = "sample_queries"

class GetClusterTool(_HarnessAdapter):
    _hn = "get_cluster"

class EvaluateResponseTool(_HarnessAdapter):
    _hn = "evaluate_response"

class FindRelevantCategoriesTool(_HarnessAdapter):
    _hn = "find_relevant_categories"
