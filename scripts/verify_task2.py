"""任务2 端到端验证：单裁判 rubric 评估。

A. 直接 evaluate()：好/坏两条 response，校验 judge 区分度。
B. Agent 自然语言：验证 evaluate_response 工具接线。
需 .env 配置 LLM_API_KEY。用法：python scripts/verify_task2.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harness.agent import AgentLoop
from harness.config import load_settings
from harness.eval_tools import build_eval_tools
from harness.evaluate import evaluate
from harness.provider import OpenAICompatProvider
from harness.tools import ToolRegistry

DIRECT_CASES = [
    ("正确回答", "今天北京天气怎么样", "北京今天晴，气温 15-25℃，微风，适合外出。"),
    ("答非所问", "帮我定一个明天早上7点的闹钟", "好的，已经帮你查到今天的娱乐新闻了。"),
]

AGENT_CASE = ('请评估这条手机助手回答的质量：\n'
              'query=「给小孩播放一首摇篮曲」\n'
              'response=「好的，正在为你播放《摇篮曲》。」')


async def main() -> None:
    s = load_settings()
    provider = OpenAICompatProvider(s.base_url, s.api_key, s.model)
    try:
        print("=" * 72)
        print("A. 直接 evaluate()（judge 区分度）")
        print("=" * 72)
        for label, q, r in DIRECT_CASES:
            v = await evaluate(provider, q, r)
            print(f"\n[{label}] query={q}")
            print(f"  response={r}")
            print(f"  verdict: total={v['total']} correctness={v['correctness']}")
            print(f"  rubric={json.dumps(v['rubric'], ensure_ascii=False)}")
            print(f"  rationale={v['rationale']}")

        print("\n" + "=" * 72)
        print("B. Agent 自然语言（工具接线）")
        print("=" * 72)
        registry = ToolRegistry()
        for t in build_eval_tools(provider):
            registry.register(t)
        loop = AgentLoop(provider, registry, max_iterations=s.max_iterations)
        print(f"\n[Q] {AGENT_CASE}")
        answer = await loop.run(AGENT_CASE)
        print(f"[A] {answer}")
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
