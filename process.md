# process.md — 项目进度

> 按 CLAUDE.md 原则 4（进度透明）维护。最近更新：2026-07-22

## 一期目标

任务 1：自动化评测数据集的确定 ✅（已完成并验证）
任务 2：自动化评估（整合 auto_eval_agent）⬜（未开始）

## 当前状态：任务 1 完成

CLI 对话式 Agent，用自然语言从 `data/现网数据.csv` 提取/筛选/采样评测数据集，跑通全部测试 query。

### 架构决策（重要）

CLAUDE.md 要求"直接基于 nanobot 源码修改适配"，同时最高优先级是"最小功能化"。实测 nanobot 依赖闭包：
- `AgentRunner` 闭包：**64 文件 / 24,597 行**（工具自动发现拉入全部工具、provider 注册表拉入全部 provider、还有 cli service / subagent / config / security 等）
- OpenAI provider 层闭包：8 文件 / 5,481 行

全量复制严重违背最小功能化。**决策：按 nanobot 同构架构（Provider / Tool / ToolRegistry / AgentLoop）自研最小核心**，只保留任务 1 必需，约 800 行。nanobot 只读副本保留在 `references/nanobot/` 供后续对照。

### 模块（src/harness/）

| 模块 | 职责 |
|---|---|
| `dataset.py` | pandas 加载 CSV + 过滤/采样（stats/top_categories/sub_intents/filter/sample） |
| `tools/base.py` `tools/registry.py` | Tool 基类 + 注册表（OpenAI function schema） |
| `data_tools.py` | 6 个 LLM 工具，结果写 `data/output/` 并返回 count/csv_path/preview |
| `provider.py` | OpenAI 兼容 client（非流式 chat + function calling，httpx） |
| `agent.py` | AgentLoop 工具调用循环 + system prompt |
| `config.py` / `cli.py` | .env 配置 / `harness chat` 交互入口 |

### 数据事实（已剖析）

一行=一个 session=一条 query；127,563 行；639 簇；`cluster_size`==该簇行数（冗余）；噪声簇 `cluster_id=-1` 33,178 行（~26%）；32 一级主题、219 二级主题；`query_text` 含 `|` 分隔多请求；UTF-8 带 BOM（`utf-8-sig` 读）。

### 验证结果（CLAUDE.md 原则 3：功能+效果）

单测：`pytest` **23 passed**（dataset/registry/data_tools/provider/agent）。

端到端（真实 glm-5.2，`scripts/verify_task1.py`）：
- 功能验证 3/3：
  - 闹钟100条 → `filter(keyword="闹钟",limit=100)` → 100 行 ✓
  - 采样1k → `sample(stratified,n=1000,top_k=20)` → 1000 行 ✓
  - top10×200 → `sample(stratified,top_k=10,per_category=20)` → 200 行 ✓
- 效果验证 2/2：天气50条（50 行）、每类5条共30条（30 行）✓
- Agent 能主动提示"分层采样默认含噪声类"，推理合理。

## 已知事项 / 后续

- **噪声类处理**：分层采样默认把"噪声"（最大类，~26%）计入。后续可在 `sample`/`top_categories` 加 `exclude_noise` 选项。
- **粒度**：当前"一条=一行（session）"。若需按 `|` 拆单请求，再加参数。
- **data/ 未入库**：`data/现网数据.csv`（11MB 真实数据）与 `data/output/`（产物）均未提交版本库。
- **网络**：模型服务（vicp.fun 隧道）直连即可；GitHub 需走本地代理 127.0.0.1:7890（已配 repo `http.proxy`）。

## TODO

- [ ] 任务 2：整合 auto_eval_agent 实现自动化评估（query+response → 评估）
- [ ] （可选）采样/类别工具加 `exclude_noise`
- [ ] （可选）query 按 `|` 拆分为单请求粒度
