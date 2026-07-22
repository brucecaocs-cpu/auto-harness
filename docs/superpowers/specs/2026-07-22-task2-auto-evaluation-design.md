# 任务 2 设计：自动化评估（query+response → 评估）

日期：2026-07-22 ｜ 状态：已对齐（用户授权自主推进，范围采用推荐方案）

## 1. 范围

一期任务 2：**自动化评估**。输入一条 `query` + 一条 `response`（手机助手 Agent 的回答），自动产出评估结论：rubric 各维度打分、总分、对错判定、理由。整合为 harness Agent 的一个工具，用户自然语言触发。

成功标准：对给定 query+response，Agent 能返回结构化评估（JSON），维度分合理、理由可读，端到端跑通。

## 2. 关键决策

| 编号 | 决策 | 说明 |
|---|---|---|
| E1 | 单裁判 rubric 评估 | 借鉴 auto_eval_agent 的 `rubric_judge`，自研最小评估。不做多裁判集成/元评测/成对比较/Web 查证（最小功能化）。 |
| E2 | 整合为 harness 工具 `evaluate_response` | 复用 task-1 的 AgentLoop/ToolRegistry/provider。评估 LLM = glm-5.2（与数据集 Agent 同一模型服务）。 |
| E3 | 评估引擎 = LLM + 结构化 JSON 输出 | prompt 要求先 `<analysis>` 后输出 JSON；健提取（容忍 ```json 围栏/多余文本），失败重试修复一次。 |
| E4 | rubric 维度默认 5 维 | 准确性/完整性/相关性/有用性/安全性，各 1–5 分（沿用 auto_eval demo 维度）。可选自定义。 |
| E5 | reference 可选 | 有参考答案时一并提供给裁判辅助判断；无则盲评。 |
| E6 | 验证 | 单测（JSON 提取/prompt/解析/工具）+ 端到端（对样例 query+response 出评估）。 |
| E7 | 本期不做 | 多裁判 ensemble、元评测、pairwise、Web 检索查证、批量评估、评估报告、Web 台。 |

## 3. 集成架构

```
用户自然语言 → CLI → AgentLoop → 识别评估意图 → evaluate_response 工具
                                            └─→ evaluate.py（judge）
                                                 └─→ provider.chat(glm-5.2) → JSON verdict
```

- `evaluate_response` 是注册进 ToolRegistry 的普通 Tool，与 6 个数据工具并列。
- 数据工具与评估工具可组合：先 `sample_queries` 取样，再对若干 query+response 调用 `evaluate_response`（后续接被测 Agent 的 response 来源）。

## 4. 评估输出（Verdict JSON）

```json
{
  "rubric": {"准确性": 5, "完整性": 4, "相关性": 5, "有用性": 4, "安全性": 5},
  "total": 4.6,
  "correctness": "right",
  "rationale": "……",
  "analysis": "……"
}
```

- `correctness` ∈ {right, wrong, partial, unclear}
- `total` = 各维度均分（1–5）

## 5. 模块

| 文件 | 职责 |
|---|---|
| `src/harness/evaluate.py` | rubric judge：构造 prompt、调 provider、解析 verdict（含 JSON 提取与修复重试） |
| `src/harness/eval_tools.py` | `EvaluateResponseTool` + `build_eval_tools(provider)` |
| `src/harness/cli.py` | 注册评估工具；`agent.py` system prompt 补评估说明 |
| `tests/test_evaluate.py` | JSON 提取 / prompt / evaluate 解析（FakeProvider） |
| `tests/test_eval_tools.py` | 工具行为（FakeProvider） |
| `scripts/verify_task2.py` | 端到端：样例 query+response → 评估 |

## 6. 模型与凭证

复用 `.env` 的 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（glm-5.2）。无新增凭证。

## 7. 不做（Out of Scope）

多裁判集成、元评测（reference 校验裁判）、成对比较、Web 检索查证、批量评估、报告生成、Web UI。
