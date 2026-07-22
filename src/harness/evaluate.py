"""单裁判 rubric 评估（借鉴 auto_eval_agent judges/rubric_judge 的最小实现）。"""
from __future__ import annotations

import json
import re
from typing import Any

DEFAULT_DIMENSIONS = ["准确性", "完整性", "相关性", "有用性", "安全性"]
CORRECTNESS = ("right", "wrong", "partial", "unclear")


def extract_json(text: str) -> dict[str, Any]:
    """从模型输出中提取 JSON 对象（容忍 ```json 围栏与前缀/后缀文本）。"""
    if not text:
        raise ValueError("empty output")
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        candidate = m.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found")
        candidate = text[start:end + 1]
    return json.loads(candidate)


def _extract_analysis(text: str) -> str:
    m = re.search(r"<analysis>(.*?)</analysis>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def build_judge_prompt(query, response, context=None, reference=None, dimensions=None) -> list[dict[str, str]]:
    dims = dimensions or DEFAULT_DIMENSIONS
    system = (
        "你是手机助手回答质量的专业评测裁判。请对给定的用户 query 和助手 response 做客观评估。"
        "先输出 <analysis>你的分析</analysis>，再输出一个严格的 JSON 对象，此外不要任何多余文本。"
    )
    dims_desc = "、".join(f"{d}(1-5)" for d in dims)
    parts = [f"【用户 query】\n{query}", f"\n【助手 response】\n{response}"]
    if context:
        parts.append(f"\n【背景 context】\n{context}")
    if reference:
        parts.append(f"\n【参考答案 reference】\n{reference}")
    parts.append(
        f"\n请按维度打分（整数 1-5）：{dims_desc}。"
        "并给出 correctness（right/wrong/partial/unclear）与 rationale（中文简述理由）。"
        '输出 JSON：{"rubric": {"维度": 分, ...}, "correctness": "...", "rationale": "..."}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(parts)}]


def _verdict_from(data: dict[str, Any], dimensions) -> dict[str, Any]:
    dims = dimensions or DEFAULT_DIMENSIONS
    raw = data.get("rubric", {}) or {}
    scores = {d: int(raw[d]) for d in dims if isinstance(raw.get(d), (int, float))}
    total = round(sum(scores.values()) / len(scores), 2) if scores else 0.0
    correctness = data.get("correctness", "unclear")
    if correctness not in CORRECTNESS:
        correctness = "unclear"
    return {"rubric": scores, "total": total, "correctness": correctness,
            "rationale": data.get("rationale", "")}


async def evaluate(provider, query, response, context=None, reference=None, dimensions=None) -> dict[str, Any]:
    messages = build_judge_prompt(query, response, context, reference, dimensions)
    resp = await provider.chat(messages)
    try:
        data = extract_json(resp.content)
        analysis = _extract_analysis(resp.content)
    except (ValueError, json.JSONDecodeError):
        repair = messages + [
            {"role": "assistant", "content": resp.content},
            {"role": "user", "content": "请只输出一个合法 JSON 对象（不要 <analysis>、不要多余文本），字段：rubric/correctness/rationale。"},
        ]
        resp2 = await provider.chat(repair)
        data = extract_json(resp2.content)
        analysis = _extract_analysis(resp2.content)
    verdict = _verdict_from(data, dimensions)
    verdict["analysis"] = analysis
    return verdict
