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
    path = output_dir / f"{tag}_{int(time.time() * 1000)}.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


class _DatasetStats(Tool):
    name = "dataset_stats"
    description = "返回数据集概览：总行数、簇数、一/二级主题数、噪声行数。"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, ds: Dataset):
        self.ds = ds

    async def execute(self) -> str:
        return json.dumps(self.ds.stats(), ensure_ascii=False)


class _ListTopCategories(Tool):
    name = "list_top_categories"
    description = "按样本量返回 top N 一级主题及行数/簇数。"
    parameters = {"type": "object", "properties": {"n": {"type": "integer", "description": "返回前 N 个"}}, "required": ["n"]}

    def __init__(self, ds: Dataset):
        self.ds = ds

    async def execute(self, n: int) -> str:
        return json.dumps({"categories": self.ds.top_categories(n)}, ensure_ascii=False)


class _ListSubIntents(Tool):
    name = "list_sub_intents"
    description = "返回二级主题及行数，可按一级主题过滤。"
    parameters = {"type": "object", "properties": {"category": {"type": "string", "description": "可选，一级主题"}}}

    def __init__(self, ds: Dataset):
        self.ds = ds

    async def execute(self, category: str | None = None) -> str:
        return json.dumps({"sub_intents": self.ds.sub_intents(category)}, ensure_ascii=False)


class _FilterQueries(Tool):
    name = "filter_queries"
    description = "按一级主题/二级主题/簇 id/关键词过滤 query，结果写 CSV 并返回预览。"
    parameters = {"type": "object", "properties": {
        "category": {"type": "string"}, "sub_intent": {"type": "string"},
        "cluster_id": {"type": "integer"}, "keyword": {"type": "string", "description": "query_text 包含的子串"},
        "limit": {"type": "integer", "description": "最多返回多少条"}}}

    def __init__(self, ds: Dataset, out: Path):
        self.ds, self.out = ds, out

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

    def __init__(self, ds: Dataset, out: Path):
        self.ds, self.out = ds, out

    async def execute(self, strategy, n, category=None, sub_intent=None, top_k=None, per_category=None) -> str:
        rows = self.ds.sample(n, strategy, category, sub_intent, top_k, per_category)
        path = _write(rows, self.out, f"sample_{strategy}")
        return _payload(len(rows), path, rows[:_PREVIEW])


class _GetCluster(Tool):
    name = "get_cluster"
    description = "返回某个簇的详情与样本。"
    parameters = {"type": "object", "properties": {"cluster_id": {"type": "integer"}}, "required": ["cluster_id"]}

    def __init__(self, ds: Dataset):
        self.ds = ds

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
