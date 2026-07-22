# 任务 1 设计：自动化评测数据集的确定

日期：2026-07-22 ｜ 状态：已对齐（用户授权自主推进）

## 1. 范围

一期任务 1：**自动化评测数据集的确定**。用户用自然语言提需求，Agent 自动从 `data/现网数据.csv` 提取/采样数据并返回结果。

成功标准（三条测试 query 必须跑通且结果合理）：
- 帮我找出闹钟相关的100条现网query
- 根据类别采样1k现网样本
- 筛选出top10类别的200条样本

## 2. 关键决策

| 编号 | 决策 | 说明 |
|---|---|---|
| D1 | CLI 对话式 Agent（tool-using） | 基于 nanobot agent loop，数据操作暴露为工具，LLM 自主规划调用。否决纯 CLI 子命令与固定意图槽位解析。 |
| D2 | 复制 nanobot 最小核心并适配 | 复制 `agent / providers / config / bus / session + memory / utils` 到 `src/harness/`。不引入 channels / webui / web / api / gateway / apps / audio / cron / triggers / pairing。 |
| D3 | pandas + 结构化工具 | 单机足够。"相关"用关键词 + 类别匹配。不引入 embedding/向量检索（最小功能化）。 |
| D4 | 数据工具集 | 见 §4。覆盖三条测试 query。 |
| D5 | 输出 | 终端表格 + 可选导出 CSV 到 `data/output/`，返回聚合统计。粒度=行（1 session）。 |
| D6 | 模型 | glm-5.2，OpenAI 兼容 provider；key 从 `.env` 的 `LLM_API_KEY` 读。 |
| D7 | 配置 | 精简 schema（模型、CSV 路径、输出目录、base_url），不沿用 nanobot 全量 config。 |
| D8 | 验证 | 功能验证（三条 query 人工核对）+ 效果验证（5–8 条变异 query 看稳定性与边界）。 |
| D9 | 本期不做 | 任务 2 评估、WebUI、多 channel、长期 memory、embedding、数据集版本管理。 |

## 3. 数据

`data/现网数据.csv`：UTF-8 带 BOM，127,580 数据行。

| 字段 | 说明 |
|---|---|
| cluster_id | query_text 所属簇 id（-1 且 cluster_size=0 为噪声） |
| cluster_size | 簇内样本数量 |
| top_category | 簇对应一级主题 |
| sub_intent | 簇对应二级主题（隶属一级主题） |
| query_text | 用户真实请求 session，`\|` 为分隔符 |

**粒度约定（Q1 已定）**：一条 query = 一行（一个 session）。后续如需按 `|` 拆成单请求，再加参数。

## 4. 暴露给 LLM 的数据工具

- `dataset_stats()` — 总行数、簇数、类别数等概览
- `list_top_categories(n)` — 按样本量返回 top N 一级主题及计数
- `list_sub_intents(category=None)` — 二级主题及计数，可按一级主题过滤
- `filter_queries(category=None, sub_intent=None, cluster_id=None, keyword=None, limit=None)` — 多条件过滤
- `sample_queries(strategy, n, category=None, sub_intent=None)` — 策略：`random` / `top_by_cluster_size` / `stratified_by_category`
- `get_cluster(cluster_id)` — 簇详情

测试 query 覆盖：
- 闹钟100条 → `filter_queries(keyword="闹钟", limit=100)`（或先 `list_sub_intents` 定位再 filter）
- 采样1k → `sample_queries(strategy=random, n=1000)`
- top10类别×200条 → `list_top_categories(10)` + `sample_queries(strategy=stratified_by_category, n=200)`

## 5. 架构与目录

```
auto-harness/
├─ src/harness/
│  ├─ agent/        # 适配自 nanobot（loop / runner / tools 注册）
│  ├─ providers/    # OpenAI 兼容（glm）
│  ├─ config/       # 精简配置（pydantic）
│  ├─ data_tools/   # CSV 工具实现（pandas）
│  ├─ session/      # 会话历史（适配自 nanobot）
│  ├─ bus/          # 消息总线（适配自 nanobot，可裁剪）
│  ├─ utils/
│  └─ cli.py        # 入口：harness chat
├─ data/现网数据.csv
├─ tests/           # 数据工具单测（pytest）
├─ pyproject.toml
└─ .env (gitignored)
```

数据流：用户输入 → CLI → agent loop → LLM 决定工具调用 → data_tools 执行（pandas）→ 结果回 LLM → 汇总输出。

## 6. 模型与凭证

- Base URL: `http://1239mxgn96959.vicp.fun:4009`（OpenAI 兼容）
- 模型：`glm-5.2`（备选 `glm-5.1`）
- `.env`：`LLM_API_KEY=...`，代码经环境变量读取；`.env` 已 gitignore，凭证不入库。

## 7. 验证计划

- **功能验证**：三条测试 query 各跑一次，人工核对命中合理性。
- **效果验证**：5–8 条变异 query（换主题/数量/采样方式），覆盖边界：空结果、请求量超过可用量、噪声簇（cluster_id=-1）、非法类别。

## 8. 不做（Out of Scope）

任务 2 自动化评估、WebUI、多 channel、长期 memory、embedding 语义检索、数据集版本管理。
