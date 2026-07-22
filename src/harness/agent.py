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
