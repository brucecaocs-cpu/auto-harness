"""任务1 端到端验证：跑测试 query，核对工具调用与 CSV 产物。

需 .env 配置 LLM_API_KEY。模型服务直连（无需代理）。
用法：python scripts/verify_task1.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from harness.agent import AgentLoop
from harness.config import load_settings
from harness.data_tools import build_data_tools
from harness.dataset import Dataset
from harness.provider import OpenAICompatProvider
from harness.tools import ToolRegistry

FUNCTIONAL = [
    "帮我找出闹钟相关的100条现网query",
    "根据类别采样1k现网样本",
    "筛选出top10类别的200条样本",
]
EFFECT = [
    "给我50条天气相关的query",
    "每个类别最多采5条，总共来30条样本",
]


def _csv_names(out_dir: Path) -> set[str]:
    return {p.name for p in out_dir.glob("*.csv")}


async def run_query(loop: AgentLoop, out_dir: Path, q: str) -> tuple[str, list[str]]:
    before = _csv_names(out_dir)
    loop.reset()
    answer = await loop.run(q)
    produced = sorted(_csv_names(out_dir) - before)
    info = []
    for name in produced:
        try:
            n = len(pd.read_csv(out_dir / name, encoding="utf-8-sig"))
        except Exception:
            n = "?"
        info.append(f"{name}({n}行)")
    return answer, info


async def main() -> None:
    s = load_settings()
    out_dir = s.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ds = Dataset(s.csv_path)
    registry = ToolRegistry()
    for t in build_data_tools(ds, out_dir):
        registry.register(t)
    provider = OpenAICompatProvider(s.base_url, s.api_key, s.model)
    loop = AgentLoop(provider, registry, max_iterations=s.max_iterations)
    try:
        for group, qs in (("功能验证（3条测试query）", FUNCTIONAL), ("效果验证（变异query）", EFFECT)):
            print("=" * 72)
            print(group)
            print("=" * 72)
            for q in qs:
                print(f"\n[Q] {q}")
                try:
                    answer, info = await run_query(loop, out_dir, q)
                except Exception as e:
                    answer, info = f"[异常] {type(e).__name__}: {e}", []
                print(f"[A] {answer}")
                print(f"[CSV] {', '.join(info) if info else '(无新文件)'}")
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
