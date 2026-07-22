# 任务 1 实现计划：自动化评测数据集的确定

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 CLI 对话式 Agent，用自然语言从 `data/现网数据.csv` 提取/采样评测数据集，跑通三条测试 query。

**Architecture:** 基于 nanobot 的 Agent 架构（Provider / Tool / ToolRegistry / AgentLoop），但**精简适配**而非全量复制——经测量 `AgentRunner` 依赖闭包达 64 文件/24.6k 行、provider 层 8 文件/5.5k 行，全量复制违背 CLAUDE.md 最高优先级"最小功能化"。因此按 nanobot 同构架构自研最小核心，只保留任务 1 必需：OpenAI 兼容 provider（非流式 + function calling）、工具注册表、pandas 数据工具、工具调用循环、CLI。

**Tech Stack:** Python 3.11+ / httpx / pandas / pydantic（可选）/ python-dotenv / pytest + pytest-asyncio

**数据事实（已剖析确认）：** 一行=一个 session=一条 query；127,563 行；639 簇；`cluster_size`==该簇行数（冗余）；噪声簇 `cluster_id=-1` 33,178 行；32 一级主题、219 二级主题；`query_text` 含 `|` 分隔多请求。UTF-8 带 BOM，用 `encoding="utf-8-sig"` 读。

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `src/harness/__init__.py`
- Create: `.env.example`

- [ ] **Step 1: pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "auto-harness"
version = "0.1.0"
description = "harness 反馈与自进化平台（一期：自动化评测数据集的确定）"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pandas>=2.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[project.scripts]
harness = "harness.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 包骨架 + .env.example**

`src/harness/__init__.py`：`"""auto-harness agent framework (nanobot-derived, minimal)."""\n__version__ = "0.1.0"`

`.env.example`：
```
LLM_API_KEY=your-key-here
LLM_BASE_URL=http://1239mxgn96959.vicp.fun:4009
LLM_MODEL=glm-5.2
```

- [ ] **Step 3: 安装依赖（editable + dev）**

Run: `python -m pip install -e "D:\auto-harness[dev]"`
Expected: 安装成功，`harness` 命令可用、`pytest`/`pandas`/`httpx` 可导入。

- [ ] **Step 4: Commit**

`git add pyproject.toml src/harness/__init__.py .env.example` → commit `chore: scaffold auto-harness package`

---

### Task 2: Dataset 数据访问层（TDD）

**Files:**
- Create: `src/harness/dataset.py`
- Test: `tests/test_dataset.py`
- Create: `tests/conftest.py`（小型合成 CSV fixture，不用真实 12MB 数据）

`tests/conftest.py`：
```python
import pandas as pd
import pytest

@pytest.fixture()
def sample_csv(tmp_path):
    df = pd.DataFrame([
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "设置闹钟", "query_text": "帮我定个闹钟|明天早上7点"},
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "设置闹钟", "query_text": "闹钟响了"},
        {"cluster_id": 1, "cluster_size": 3, "top_category": "闹钟", "sub_intent": "关闭闹钟", "query_text": "关掉闹钟"},
        {"cluster_id": 2, "cluster_size": 2, "top_category": "天气", "sub_intent": "查询天气", "query_text": "今天天气怎么样"},
        {"cluster_id": 2, "cluster_size": 2, "top_category": "天气", "sub_intent": "查询天气", "query_text": "明天会下雨吗"},
        {"cluster_id": -1, "cluster_size": 0, "top_category": "噪声", "sub_intent": "噪声", "query_text": "随便聊聊"},
    ])
    p = tmp_path / "data.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p
```

- [ ] **Step 1: 写失败测试** `tests/test_dataset.py`

```python
from harness.dataset import Dataset

def test_stats(sample_csv):
    ds = Dataset(sample_csv)
    s = ds.stats()
    assert s["total_rows"] == 6
    assert s["n_clusters"] == 3  # 含 -1
    assert s["n_categories"] == 3
    assert s["noise_rows"] == 1

def test_top_categories(sample_csv):
    ds = Dataset(sample_csv)
    top = ds.top_categories(2)
    assert top[0]["top_category"] == "闹钟" and top[0]["rows"] == 3
    assert top[1]["top_category"] == "天气" and top[1]["rows"] == 2

def test_sub_intents_filtered(sample_csv):
    ds = Dataset(sample_csv)
    ints = ds.sub_intents(category="闹钟")
    names = {i["sub_intent"] for i in ints}
    assert names == {"设置闹钟", "关闭闹钟"}

def test_filter_keyword(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.filter(keyword="闹钟")
    assert len(out) == 3

def test_filter_category_and_limit(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.filter(category="闹钟", limit=2)
    assert len(out) == 2

def test_sample_random_count(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(4, strategy="random")
    assert len(out) == 4

def test_sample_stratified_top_k(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(2, strategy="stratified_by_category", top_k=2, per_category=1)
    cats = set(r["top_category"] for r in out)
    assert len(out) == 2 and cats == {"闹钟", "天气"}

def test_sample_caps_at_available(sample_csv):
    ds = Dataset(sample_csv)
    out = ds.sample(999, strategy="random")
    assert len(out) == 6
```

- [ ] **Step 2: 跑测试确认失败** `pytest tests/test_dataset.py -v` → ImportError（harness.dataset 不存在）

- [ ] **Step 3: 实现** `src/harness/dataset.py`

```python
"""数据访问层：加载并对 现网数据.csv 做过滤/采样。粒度：一行=一个 session=一条 query。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_COLS = ["cluster_id", "cluster_size", "top_category", "sub_intent", "query_text"]


class Dataset:
    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self.df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        self.df["cluster_size"] = pd.to_numeric(self.df["cluster_size"], errors="coerce").fillna(0).astype(int)

    def stats(self) -> dict[str, int]:
        return {
            "total_rows": int(len(self.df)),
            "n_clusters": int(self.df["cluster_id"].nunique()),
            "n_categories": int(self.df["top_category"].nunique()),
            "n_intents": int(self.df["sub_intent"].nunique()),
            "noise_rows": int((self.df["cluster_id"] == -1).sum()),
        }

    def top_categories(self, n: int) -> list[dict[str, Any]]:
        g = self.df.groupby("top_category").agg(rows=("query_text", "size"), clusters=("cluster_id", "nunique"))
        g = g.sort_values("rows", ascending=False).head(max(0, int(n)))
        return [{"top_category": idx, "rows": int(r.rows), "clusters": int(r.clusters)} for idx, r in g.iterrows()]

    def sub_intents(self, category: str | None = None) -> list[dict[str, Any]]:
        df = self.df if category is None else self.df[self.df["top_category"] == category]
        g = df.groupby(["top_category", "sub_intent"]).size().reset_index(name="rows")
        g = g.sort_values("rows", ascending=False)
        return [{"top_category": r.top_category, "sub_intent": r.sub_intent, "rows": int(r.rows)} for r in g.itertuples()]

    def filter(self, category=None, sub_intent=None, cluster_id=None, keyword=None, limit=None) -> list[dict[str, Any]]:
        df = self.df
        if category is not None:
            df = df[df["top_category"] == category]
        if sub_intent is not None:
            df = df[df["sub_intent"] == sub_intent]
        if cluster_id is not None:
            df = df[df["cluster_id"] == int(cluster_id)]
        if keyword:
            df = df[df["query_text"].str.contains(keyword, case=False, na=False, regex=False)]
        if limit is not None:
            df = df.head(max(0, int(limit)))
        return df[_COLS].to_dict(orient="records")

    def sample(self, n, strategy="random", category=None, sub_intent=None, top_k=None, per_category=None) -> list[dict[str, Any]]:
        df = self.df
        if category is not None:
            df = df[df["top_category"] == category]
        if sub_intent is not None:
            df = df[df["sub_intent"] == sub_intent]
        n = int(n)
        if strategy == "random":
            k = min(n, len(df))
            out = df.sample(n=k, random_state=42) if k > 0 else df.head(0)
            return out[_COLS].to_dict(orient="records")
        if strategy == "top_by_cluster_size":
            out = df.sort_values("cluster_size", ascending=False).head(n)
            return out[_COLS].to_dict(orient="records")
        if strategy == "stratified_by_category":
            if top_k is not None:
                keep = [c["top_category"] for c in self.top_categories(int(top_k))]
                df = df[df["top_category"].isin(keep)]
            if per_category is not None:
                per = int(per_category)
                out = df.groupby("top_category", group_keys=False).apply(
                    lambda g: g.sample(n=min(per, len(g)), random_state=42), include_groups=False
                )
            else:
                counts = df["top_category"].value_counts()
                total = int(counts.sum()) or 1
                parts = []
                for cat, cnt in counts.items():
                    take = max(1, round(n * cnt / total))
                    g = df[df["top_category"] == cat]
                    parts.append(g.sample(n=min(take, len(g)), random_state=42))
                out = pd.concat(parts) if parts else df.head(0)
                out = out.head(n)
            return out[_COLS].to_dict(orient="records")
        raise ValueError(f"unknown strategy: {strategy}")
```

- [ ] **Step 4: 跑测试确认通过** `pytest tests/test_dataset.py -v` → 全 PASS

- [ ] **Step 5: Commit** `feat: add Dataset data-access layer`

---

### Task 3: 工具框架（Tool 基类 + Registry）（TDD）

**Files:**
- Create: `src/harness/tools/__init__.py`
- Create: `src/harness/tools/base.py`
- Create: `src/harness/tools/registry.py`
- Test: `tests/test_registry.py`

`src/harness/tools/__init__.py`：`from .base import Tool\nfrom .registry import ToolRegistry\n__all__ = ["Tool", "ToolRegistry"]`

- [ ] **Step 1: 写失败测试** `tests/test_registry.py`

```python
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
    reg = ToolRegistry(); reg.register(EchoTool())
    out = await reg.execute("echo", {"text": "hi"})
    assert json.loads(out)["echo"] == "hi"

@pytest.mark.asyncio
async def test_execute_unknown_tool():
    reg = ToolRegistry()
    out = await reg.execute("nope", {})
    assert "unknown tool" in json.loads(out)["error"]

@pytest.mark.asyncio
async def test_execute_bad_args():
    reg = ToolRegistry(); reg.register(EchoTool())
    out = await reg.execute("echo", {"wrong": 1})
    assert "error" in json.loads(out)
```

- [ ] **Step 2: 跑测试确认失败** → ImportError

- [ ] **Step 3: 实现** `src/harness/tools/base.py`

```python
"""Tool 基类（对齐 nanobot tools/base 的最小形态）。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        ...

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }
```

`src/harness/tools/registry.py`

```python
"""ToolRegistry（对齐 nanobot tools/registry 的最小形态）。"""
from __future__ import annotations
import json
from typing import Any
from .base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def tool_names(self) -> list[str]:
        return list(self._tools)

    def get_definitions(self) -> list[dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        try:
            return await tool.execute(**(arguments or {}))
        except TypeError as e:
            return json.dumps({"error": f"bad arguments for {name}: {e}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
```

- [ ] **Step 4: 跑测试确认通过** → 全 PASS

- [ ] **Step 5: Commit** `feat: add Tool base + ToolRegistry`

---

### Task 4: 数据工具（6 个 LLM 工具）（TDD）

**Files:**
- Create: `src/harness/data_tools.py`
- Test: `tests/test_data_tools.py`

工具把 `Dataset` 包成 LLM 可调用的 Tool；`filter`/`sample` 结果**全量写入 `output_dir`**，返回 JSON 含 `count`/`csv_path`/`preview`（截断，避免爆 token）。

- [ ] **Step 1: 写失败测试** `tests/test_data_tools.py`

```python
import json
import pytest
from harness.dataset import Dataset
from harness.data_tools import build_data_tools

@pytest.fixture()
def tools(sample_csv, tmp_path):
    ds = Dataset(sample_csv)
    return {t.name: t for t in build_data_tools(ds, tmp_path / "out")}

@pytest.mark.asyncio
async def test_dataset_stats(tools):
    out = json.loads(await tools["dataset_stats"].execute())
    assert out["total_rows"] == 6

@pytest.mark.asyncio
async def test_list_top_categories(tools):
    out = json.loads(await tools["list_top_categories"].execute(n=1))
    assert out["categories"][0]["top_category"] == "闹钟"

@pytest.mark.asyncio
async def test_filter_writes_csv(tools, tmp_path):
    out = json.loads(await tools["filter_queries"].execute(keyword="闹钟", limit=100))
    assert out["count"] == 3
    assert out["csv_path"] and (tmp_path / "out" / out["csv_path"]).exists() is False  # csv_path 是绝对路径
    import os; assert os.path.exists(out["csv_path"])

@pytest.mark.asyncio
async def test_sample_random(tools):
    out = json.loads(await tools["sample_queries"].execute(strategy="random", n=4))
    assert out["count"] == 4

@pytest.mark.asyncio
async def test_sample_stratified_top10(tools):
    out = json.loads(await tools["sample_queries"].execute(strategy="stratified_by_category", n=2, top_k=2, per_category=1))
    assert out["count"] == 2

@pytest.mark.asyncio
async def test_get_cluster(tools):
    out = json.loads(await tools["get_cluster"].execute(cluster_id=1))
    assert out["cluster_id"] == 1 and out["rows"] == 3
```

- [ ] **Step 2: 跑测试确认失败** → ImportError

- [ ] **Step 3: 实现** `src/harness/data_tools.py`

```python
"""把 Dataset 包装成 LLM 可调用工具。结果全量写 output_dir，返回 count/csv_path/preview。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .dataset import Dataset
from .tools import Tool

_PREVIEW = 20


def _payload(count: int, csv_path: str, preview_rows: list[dict[str, Any]]) -> str:
    return json.dumps({"count": count, "csv_path": csv_path, "preview": preview_rows}, ensure_ascii=False)


def _write(rows: list[dict[str, Any]], output_dir: Path, tag: str) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{tag}_{int(time.time())}.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


class _DatasetStats(Tool):
    name = "dataset_stats"
    description = "返回数据集概览：总行数、簇数、一/二级主题数、噪声行数。"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, ds: Dataset): self.ds = ds
    async def execute(self) -> str:
        return json.dumps(self.ds.stats(), ensure_ascii=False)


class _ListTopCategories(Tool):
    name = "list_top_categories"
    description = "按样本量返回 top N 一级主题及行数/簇数。"
    parameters = {"type": "object", "properties": {"n": {"type": "integer", "description": "返回前 N 个"}}, "required": ["n"]}

    def __init__(self, ds: Dataset): self.ds = ds
    async def execute(self, n: int) -> str:
        return json.dumps({"categories": self.ds.top_categories(n)}, ensure_ascii=False)


class _ListSubIntents(Tool):
    name = "list_sub_intents"
    description = "返回二级主题及行数，可按一级主题过滤。"
    parameters = {"type": "object", "properties": {"category": {"type": "string", "description": "可选，一级主题"}}}

    def __init__(self, ds: Dataset): self.ds = ds
    async def execute(self, category: str | None = None) -> str:
        return json.dumps({"sub_intents": self.ds.sub_intents(category)}, ensure_ascii=False)


class _FilterQueries(Tool):
    name = "filter_queries"
    description = "按一级主题/二级主题/簇 id/关键词过滤 query，结果写 CSV 并返回预览。"
    parameters = {"type": "object", "properties": {
        "category": {"type": "string"}, "sub_intent": {"type": "string"},
        "cluster_id": {"type": "integer"}, "keyword": {"type": "string", "description": "query_text 包含的子串"},
        "limit": {"type": "integer", "description": "最多返回多少条"}}}

    def __init__(self, ds: Dataset, out: Path): self.ds, self.out = ds, out
    async def execute(self, category=None, sub_intent=None, cluster_id=None, keyword=None, limit=None) -> str:
        rows = self.ds.filter(category, sub_intent, cluster_id, keyword, limit)
        path = _write(rows, self.out, "filter")
        return _payload(len(rows), path, rows[:_PREVIEW])


class _SampleQueries(Tool):
    name = "sample_queries"
    description = "采样 query。strategy: random / top_by_cluster_size / stratified_by_category（可配 top_k、per_category）。结果写 CSV 并返回预览。"
    parameters = {"type": "object", "properties": {
        "strategy": {"type": "string", "enum": ["random", "top_by_cluster_size", "stratified_by_category"]},
        "n": {"type": "integer", "description": "采样总条数"},
        "category": {"type": "string"}, "sub_intent": {"type": "string"},
        "top_k": {"type": "integer", "description": "仅 stratified：限定 top-k 一级主题"},
        "per_category": {"type": "integer", "description": "仅 stratified：每个主题采多少条"}},
        "required": ["strategy", "n"]}

    def __init__(self, ds: Dataset, out: Path): self.ds, self.out = ds, out
    async def execute(self, strategy, n, category=None, sub_intent=None, top_k=None, per_category=None) -> str:
        rows = self.ds.sample(n, strategy, category, sub_intent, top_k, per_category)
        path = _write(rows, self.out, f"sample_{strategy}")
        return _payload(len(rows), path, rows[:_PREVIEW])


class _GetCluster(Tool):
    name = "get_cluster"
    description = "返回某个簇的详情与样本。"
    parameters = {"type": "object", "properties": {"cluster_id": {"type": "integer"}}, "required": ["cluster_id"]}

    def __init__(self, ds: Dataset): self.ds = ds
    async def execute(self, cluster_id: int) -> str:
        rows = self.ds.filter(cluster_id=cluster_id)
        head = rows[0] if rows else {}
        return json.dumps({"cluster_id": cluster_id, "rows": len(rows),
                           "top_category": head.get("top_category"), "sub_intent": head.get("sub_intent"),
                           "preview": rows[:_PREVIEW]}, ensure_ascii=False)


def build_data_tools(ds: Dataset, output_dir: str | Path) -> list[Tool]:
    out = Path(output_dir)
    return [_DatasetStats(ds), _ListTopCategories(ds), _ListSubIntents(ds),
            _FilterQueries(ds, out), _SampleQueries(ds, out), _GetCluster(ds)]
```

- [ ] **Step 4: 跑测试确认通过** → 全 PASS

- [ ] **Step 5: Commit** `feat: add 6 dataset tools (stats/categories/intents/filter/sample/cluster)`

---

### Task 5: OpenAI 兼容 Provider（TDD）

**Files:**
- Create: `src/harness/provider.py`
- Test: `tests/test_provider.py`

非流式 chat + function calling。用 httpx `MockTransport` 测试请求构造与响应解析，不依赖真实服务。

- [ ] **Step 1: 写失败测试** `tests/test_provider.py`

```python
import json
import httpx
import pytest
from harness.provider import OpenAICompatProvider

def _make(handler):
    transport = httpx.MockTransport(handler)
    return transport

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
    transport = _make(handler)
    p = OpenAICompatProvider("http://x:4009", "k", "glm-5.2", transport=transport)
    resp = await p.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function", "function": {"name": "filter_queries", "description": "", "parameters": {}}}])
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["body"]["model"] == "glm-5.2" and "tools" in captured["body"]
    assert resp.tool_calls[0].name == "filter_queries"
    assert resp.tool_calls[0].arguments == {"keyword": "闹钟", "limit": 100}
    await p.aclose()

@pytest.mark.asyncio
async def test_chat_parses_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "答案"}}]})
    p = OpenAICompatProvider("http://x:4009", "k", "glm-5.2", transport=_make(handler))
    resp = await p.chat([{"role": "user", "content": "hi"}])
    assert resp.content == "答案" and resp.tool_calls == []
    await p.aclose()
```

- [ ] **Step 2: 跑测试确认失败** → ImportError

- [ ] **Step 3: 实现** `src/harness/provider.py`

```python
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
```

- [ ] **Step 4: 跑测试确认通过** → 全 PASS

- [ ] **Step 5: Commit** `feat: add OpenAI-compatible provider (chat + function calling)`

---

### Task 6: AgentLoop 工具调用循环（TDD）

**Files:**
- Create: `src/harness/agent.py`
- Test: `tests/test_agent.py`

用 FakeProvider（脚本化返回）测试：第一轮返回 tool_call → 执行 → 第二轮返回最终文本。

- [ ] **Step 1: 写失败测试** `tests/test_agent.py`

```python
import json
import pytest
from harness.agent import AgentLoop
from harness.provider import LLMResponse, ToolCall
from harness.tools import Tool, ToolRegistry

class FakeProvider:
    def __init__(self, script): self.script = list(script); self.calls = 0
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
    reg = ToolRegistry(); reg.register(AddTool())
    provider = FakeProvider([
        LLMResponse(content="", tool_calls=[ToolCall(id="c1", name="add", arguments={"a": 2, "b": 3})], finish_reason="tool_calls"),
        LLMResponse(content="2+3=5", tool_calls=[], finish_reason="stop"),
    ])
    loop = AgentLoop(provider, reg, max_iterations=5)
    out = await loop.run("算一下 2+3")
    assert out == "2+3=5"
    assert provider.calls == 2
    # 历史里应有 tool 结果
    assert any(m.get("role") == "tool" and json.loads(m["content"])["sum"] == 5 for m in loop.messages)

@pytest.mark.asyncio
async def test_direct_answer_no_tool():
    reg = ToolRegistry()
    provider = FakeProvider([LLMResponse(content="你好", tool_calls=[], finish_reason="stop")])
    loop = AgentLoop(provider, reg)
    assert await loop.run("hi") == "你好"

@pytest.mark.asyncio
async def test_max_iterations_guard():
    reg = ToolRegistry(); reg.register(AddTool())
    provider = FakeProvider([LLMResponse(content="", tool_calls=[ToolCall(id="c", name="add", arguments={"a": 1, "b": 1})]) for _ in range(10)])
    loop = AgentLoop(provider, reg, max_iterations=3)
    out = await loop.run("x")
    assert "最大" in out
```

- [ ] **Step 2: 跑测试确认失败** → ImportError

- [ ] **Step 3: 实现** `src/harness/agent.py`

```python
"""AgentLoop：精简工具调用循环（设计对齐 nanobot agent/runner）。"""
from __future__ import annotations

import json
from typing import Any

from .tools import ToolRegistry

SYSTEM_PROMPT = """你是 auto-harness 的「评测数据集确定」Agent，服务于手机助手业务的评测与研发人员。
你的职责：根据用户的自然语言需求，调用数据工具从现网数据（按簇聚类的真实 query）中提取、筛选、采样评测数据集。

工作准则：
- 先用 dataset_stats / list_top_categories / list_sub_intents 了解数据，再决定 filter/sample 策略。
- 模糊需求（如"X相关"）优先用 keyword 匹配 query_text，或先 list_sub_intents 定位相关主题再 filter。
- 涉及"top N 类别"先 list_top_categories(N) 确认。
- 数据粒度：一条 = 一个 session（query_text 内含 "|" 分隔的多请求）。
- 工具结果已写入 CSV 并附 preview；向用户汇报条数、csv_path 与关键分布，用中文简洁作答。
"""


class AgentLoop:
    def __init__(self, provider, registry: ToolRegistry, max_iterations: int = 10):
        self.provider = provider
        self.registry = registry
        self.max_iterations = max_iterations
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    @staticmethod
    def _assistant_message(resp) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": resp.content or ""}
        if resp.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                for tc in resp.tool_calls
            ]
        return msg

    async def run(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        tools = self.registry.get_definitions()
        for _ in range(self.max_iterations):
            resp = await self.provider.chat(self.messages, tools=tools or None)
            if not resp.tool_calls:
                self.messages.append({"role": "assistant", "content": resp.content})
                return resp.content
            self.messages.append(self._assistant_message(resp))
            for tc in resp.tool_calls:
                result = await self.registry.execute(tc.name, tc.arguments)
                self.messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})
        note = f"已达到最大工具调用次数（{self.max_iterations}），请缩小范围或调整需求后重试。"
        self.messages.append({"role": "assistant", "content": note})
        return note
```

- [ ] **Step 4: 跑测试确认通过** → 全 PASS

- [ ] **Step 5: Commit** `feat: add AgentLoop tool-calling loop`

---

### Task 7: 配置 + CLI

**Files:**
- Create: `src/harness/config.py`
- Create: `src/harness/cli.py`

- [ ] **Step 1: 实现** `src/harness/config.py`

```python
"""配置：从 .env / 环境变量读取。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    api_key: str
    csv_path: Path
    output_dir: Path
    max_iterations: int = 10


def load_settings() -> Settings:
    load_dotenv(_ROOT / ".env")
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未找到 LLM_API_KEY，请在 .env 或环境变量中设置。")
    return Settings(
        base_url=os.environ.get("LLM_BASE_URL", "http://1239mxgn96959.vicp.fun:4009"),
        model=os.environ.get("LLM_MODEL", "glm-5.2"),
        api_key=api_key,
        csv_path=Path(os.environ.get("HARNESS_CSV", str(_ROOT / "data" / "现网数据.csv"))),
        output_dir=Path(os.environ.get("HARNESS_OUTPUT_DIR", str(_ROOT / "data" / "output"))),
        max_iterations=int(os.environ.get("HARNESS_MAX_ITER", "10")),
    )
```

`src/harness/cli.py`

```python
"""CLI 入口：harness chat —— 交互式数据集确定 Agent。"""
from __future__ import annotations

import asyncio

from .agent import AgentLoop
from .config import load_settings
from .data_tools import build_data_tools
from .dataset import Dataset
from .provider import OpenAICompatProvider
from .tools import ToolRegistry

_BANNER = "auto-harness 数据集确定 Agent（输入需求，/exit 退出，/reset 清空会话）"


async def _chat() -> None:
    settings = load_settings()
    ds = Dataset(settings.csv_path)
    registry = ToolRegistry()
    for t in build_data_tools(ds, settings.output_dir):
        registry.register(t)
    provider = OpenAICompatProvider(settings.base_url, settings.api_key, settings.model)
    loop = AgentLoop(provider, registry, max_iterations=settings.max_iterations)
    print(_BANNER)
    try:
        while True:
            try:
                text = input("\n你> ").strip()
            except EOFError:
                break
            if not text:
                continue
            if text in ("/exit", "/quit"):
                break
            if text == "/reset":
                loop.reset(); print("(会话已清空)"); continue
            try:
                answer = await loop.run(text)
            except Exception as e:
                answer = f"[错误] {type(e).__name__}: {e}"
            print(f"\nAgent> {answer}")
    finally:
        await provider.aclose()


def main() -> None:
    asyncio.run(_chat())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 冒烟（不依赖 LLM）** `python -c "import harness.cli, harness.agent, harness.data_tools, harness.provider, harness.dataset; print('imports ok')"` → `imports ok`

- [ ] **Step 3: Commit** `feat: add config + CLI chat entry`

---

### Task 8: 端到端验证（功能 + 效果）

**前置：** `.env` 已配置真实 `LLM_API_KEY`。

- [ ] **Step 1: 跑全量单测** `pytest -v` → 全 PASS

- [ ] **Step 2: 功能验证（三条测试 query，逐条跑 `harness chat`）**
  1. 帮我找出闹钟相关的100条现网query
  2. 根据类别采样1k现网样本
  3. 筛选出top10类别的200条样本
  每条人工核对：工具调用合理、返回条数正确、`csv_path` 已生成且内容命中。

- [ ] **Step 3: 效果验证（变异 query）** 换主题/数量/采样方式 5–8 条；覆盖边界：无结果关键词、请求量>可用量、噪声簇。

- [ ] **Step 4: 更新 `process.md`**（CLAUDE.md 原则 4：进度透明）记录完成项、验证结果、TODO（任务 2）。

- [ ] **Step 5: Commit** `docs: update process.md with task-1 verification results`

---

## Self-Review 记录

- **Spec 覆盖：** D1(AgentLoop/CLI)=Task6/7；D2(精简核心)=整体策略；D3(pandas)=Task2；D4(6 工具)=Task4；D5(输出 CSV+preview)=Task4；D6/D7(provider/config/.env)=Task5/7；D8(验证)=Task8。三条测试 query 映射已内置于工具设计。无缺口。
- **占位符：** 无 TBD/TODO；每步含完整代码与命令。
- **类型一致：** `Dataset.filter/sample` 返回 `list[dict]`，被 data_tools 与测试一致使用；`ToolRegistry.execute(name, args)` 签名一致；`LLMResponse.tool_calls: list[ToolCall]` 在 provider/agent/测试一致；`build_data_tools(ds, output_dir)` 返回 `list[Tool]`，CLI 逐个 register。一致。
