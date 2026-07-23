"""批量测试 8 个 harness 工具——基于 nanobot 的 OpenAI-compatible API。

要求 nanobot gateway 已启动（python -m nanobot gateway）。
通过 /v1/chat/completions 发请求，观察工具调用链。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harness.provider import OpenAICompatProvider
from harness.data_tools import build_data_tools
from harness.dataset import Dataset
from harness.eval_tools import build_eval_tools
from harness.config import load_settings


QUERIES = [
    ("dataset_stats", "数据总共有多少条、多少个一级主题和簇？"),
    ("list_top_categories", "样本量最多的前5个一级主题是什么？"),
    ("find_relevant_categories", "有哪些和出行相关的类别？"),
    ("filter_queries", "帮我找出闹钟相关的5条现网query"),
    ("sample_queries", "随机帮我采10条样本"),
    ("get_cluster", "簇id 294 里面有什么内容？"),
    ("evaluate_response", "评估这条回答：query=「帮我定个明天7点的闹钟」response=「好的，已帮你设定明天7:00的闹钟」"),
]


async def run_one(label: str, query: str, provider, tools_schema):
    print(f"\n{'─'*60}")
    print(f"【{label}】{query}")
    print(f"{'─'*60}")
    msgs = [{"role": "system", "content": "你是 auto-harness 的数据评测 Agent。用中文作答，需要时调用工具。"},
            {"role": "user", "content": query}]
    calls = 0
    for _ in range(5):
        resp = await provider.chat(msgs, tools=tools_schema)
        if not resp.tool_calls:
            print(f"  ✅ 完成 (工具调用{calls}次)")
            print(f"  回复: {resp.content[:300]}")
            return
        for tc in resp.tool_calls:
            calls += 1
            fn_name = tc.name
            print(f"  🔧 调用工具: {fn_name}({json.dumps(tc.arguments, ensure_ascii=False)[:120]})")
        msgs.append({"role": "assistant", "content": resp.content or "",
                     "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                                    for tc in resp.tool_calls]})
        for tc in resp.tool_calls:
            # 本地执行 harness 工具（不经过 nanobot 的 websocket 网关）
            result = await _harness_exec(tc.name, tc.arguments)
            print(f"  📤 结果: {result[:120]}")
            msgs.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})
    print(f"  ⚠️ 达到最大轮次")


_tools_cache = None


def _get_registry():
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    s = load_settings()
    ds = Dataset(s.csv_path)
    p = OpenAICompatProvider(s.base_url, s.api_key, s.model)
    reg = type("R", (), {"_t": {}})()
    for t in build_data_tools(ds, s.output_dir, p):
        reg._t[t.name] = t
    for t in build_eval_tools(p):
        reg._t[t.name] = t
    _tools_cache = reg
    return _tools_cache


async def _harness_exec(name, args):
    reg = _get_registry()
    t = reg._t.get(name)
    if t is None:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        return await t.execute(**args)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


async def main():
    print("=" * 60)
    print("auto-harness 批量测试 · 8 工具全量")
    print("=" * 60)
    s = load_settings()
    provider = OpenAICompatProvider(s.base_url, s.api_key, s.model)
    reg = _get_registry()
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
             for t in reg._t.values()]
    print(f"已注册 {len(tools)} 个工具: {[t['function']['name'] for t in tools]}")
    print()

    passed = 0
    for label, query in QUERIES:
        try:
            await run_one(label, query, provider, tools)
            passed += 1
        except Exception as e:
            print(f"  ❌ 失败: {type(e).__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"结果: {passed}/{len(QUERIES)} 通过")
    await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
