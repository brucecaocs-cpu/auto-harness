"""评估工具：evaluate_response（query+response → rubric 评估）。"""
from __future__ import annotations

import json

from .evaluate import evaluate
from .tools import Tool


class EvaluateResponseTool(Tool):
    name = "evaluate_response"
    description = "评估一条手机助手 response 的质量：按 rubric 维度打分、判对错、给理由。"
    parameters = {"type": "object", "properties": {
        "query": {"type": "string", "description": "用户请求"},
        "response": {"type": "string", "description": "助手回答"},
        "context": {"type": "string", "description": "可选背景"},
        "reference": {"type": "string", "description": "可选参考答案"},
        "dimensions": {"type": "array", "items": {"type": "string"}, "description": "可选自定义评估维度"}},
        "required": ["query", "response"]}

    def __init__(self, provider):
        self.provider = provider

    async def execute(self, query, response, context=None, reference=None, dimensions=None) -> str:
        verdict = await evaluate(self.provider, query, response, context, reference, dimensions)
        return json.dumps(verdict, ensure_ascii=False)


def build_eval_tools(provider) -> list[Tool]:
    return [EvaluateResponseTool(provider)]
