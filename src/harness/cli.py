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
                loop.reset()
                print("(会话已清空)")
                continue
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
