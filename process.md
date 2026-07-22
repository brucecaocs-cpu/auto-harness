# process.md — 项目进度

> 按 CLAUDE.md 原则 4（进度透明）维护。最近更新：2026-07-22

## 一期目标

任务 1：自动化评测数据集的确定 ✅（已完成并验证）
任务 2：自动化评估（query+response → 评估）✅（已完成并验证）

## 当前状态：一期两个能力均已打通

CLI 对话式 Agent（`harness chat`），具备两类能力：
1. **数据集确定**：自然语言从 `data/现网数据.csv` 提取/筛选/采样评测数据集。
2. **自动化评估**：对一条 query+response 做 rubric 评估（打分/判对错/给理由）。

## 架构决策（重要）

CLAUDE.md 要求"基于 nanobot / auto_eval_agent 源码适配"，最高优先级是"最小功能化"。实测依赖闭包过大（nanobot `AgentRunner` 64 文件/2.4 万行、provider 层 5.5k 行；auto_eval_agent 约 50 模块含批跑/集成/元评测/Web 台）。**决策：按两者同构架构自研最小核心**（Provider / Tool / ToolRegistry / AgentLoop + rubric judge），约 900 行。两个只读参考副本保留在 `references/` 供对照。

## 模块（src/harness/）

| 模块 | 职责 |
|---|---|
| `dataset.py` | pandas 加载 CSV + 过滤/采样（stats/top_categories/sub_intents/filter/sample） |
| `tools/base.py` `tools/registry.py` | Tool 基类 + 注册表（OpenAI function schema） |
| `data_tools.py` | 6 个数据工具，结果写 `data/output/` 并返回 count/csv_path/preview |
| `evaluate.py` | 单裁判 rubric judge：构造 prompt、调 provider、解析 verdict（JSON 提取 + 修复重试） |
| `eval_tools.py` | `evaluate_response` 工具（query+response+可选 context/reference/dimensions） |
| `provider.py` | OpenAI 兼容 client（非流式 chat + function calling，httpx） |
| `agent.py` | AgentLoop 工具调用循环 + system prompt（数据 + 评估双能力） |
| `config.py` / `cli.py` | .env 配置 / `harness chat` 交互入口 |

## 数据事实（已剖析）

一行=一个 session=一条 query；127,563 行；639 簇；`cluster_size`==该簇行数（冗余）；噪声簇 `cluster_id=-1` 33,178 行（~26%）；32 一级主题、219 二级主题；`query_text` 含 `|` 分隔多请求；UTF-8 带 BOM（`utf-8-sig` 读）。

## 验证结果（CLAUDE.md 原则 3：功能+效果）

单测：`pytest` **32 passed**（dataset/registry/data_tools/provider/agent/evaluate/eval_tools）。

任务 1 端到端（`scripts/verify_task1.py`，真实 glm-5.2）功能 3/3 + 效果 2/2：
- 闹钟100条→100行、采样1k→1000行、top10×200→200行；变异 query（天气50、每类5共30）均正确。

任务 2 端到端（`scripts/verify_task2.py`，真实 glm-5.2）：
- 直接 evaluate 区分度：正确回答 total=5.0/right；答非所问 total=1.8/wrong（安全性=5 合理，rationale 准确）。
- Agent 自然语言触发 `evaluate_response` 正常，输出结构化评估 + 建议。

## 已知事项 / 后续

- **噪声类处理**：分层采样默认含"噪声"（最大类）。可加 `exclude_noise`。
- **粒度**：当前"一条=一行（session）"。可按 `|` 拆单请求（加参数）。
- **评估深度**：当前单裁判 rubric。后续可加多裁判 ensemble、元评测（reference 校验）、Web 查证、批量评估与报告（参考 `references/auto_eval_agent`）。
- **response 来源**：当前由用户在对话中提供。后续可接"被测手机助手 Agent"自动产出 response，形成 采样→作答→评估 闭环。
- **data/ 未入库**：`data/现网数据.csv` 与 `data/output/` 均未提交版本库。
- **网络**：模型服务（vicp.fun 隧道）直连；GitHub 走本地代理 127.0.0.1:7890（已配 repo `http.proxy`）。

## TODO

- [ ] 接被测手机助手 Agent，自动产出 response，打通 采样→作答→评估 闭环
- [ ] （可选）采样/类别工具加 `exclude_noise`
- [ ] （可选）query 按 `|` 拆分为单请求粒度
- [ ] （可选）评估增强：多裁判 / 元评测 / 批量报告
