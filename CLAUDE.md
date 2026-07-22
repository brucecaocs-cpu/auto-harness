# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目背景

harness 反馈与自进化平台，服务对象为手机助手业务 Agent，提供四个能力：

1. 自动化评测数据集的确定 —— 保障找出问题
2. 自动化评估 —— 发现问题
3. 自动化根因分析 —— 问题定位
4. 自迭代 —— 确定手机助手 Agent 持续进化

**一期范围：只做 1 和 2**（自动化评测数据集的确定 + 自动化评估）。

## 核心设计原则（最高优先级，每次开工先读）

1. **先规划，再开发**：任何非平凡任务都先出方案、对齐后再写代码。
2. **最小功能化设计**：不做过度抽象、不为假想的未来需求设计、不引入当前用不到的依赖。三行重复优于一次过早抽象。
3. **重要模块开发后必须验证**：功能验证 + 效果验证，并基于结果迭代。验证不通过不算完成。
4. **进度透明**：项目进度和 TODO 定期、按需更新到 `process.md`。

## 架构

- 平台本身是一个 Agent 框架，**直接基于 nanobot 源码修改适配**（https://github.com/HKUDS/nanobot），不是作为依赖引入。
- `references/nanobot/` 是 nanobot 的只读参考副本，**任何情况下不要修改、编辑**，也不要让它污染主项目的依赖树。首次需要时执行（一次性）：
  ```bash
  git clone https://github.com/HKUDS/nanobot.git references/nanobot
  ```
  克隆之后复制一份代码到本项目下进行适配修改。
- 自动化评估能力来自 auto_eval_agent（https://github.com/ahsdx/auto_eval_agent）：输入 query + response 后自动进行评估，需将其整合进 auto-harness 的 Agent 架构。

## 一期功能：自动化评测数据集的确定

- 服务对象：评测人员、研发人员。
- 基于 `data/现网数据.csv` 实现自动化数据提取和分析。

**数据字段**：

| 字段 | 说明 |
|---|---|
| cluster_id | query_text 所属的簇 id |
| cluster_size | 簇内样本数量 |
| top_category | 簇对应的一级主题 |
| sub_intent | 簇对应的二级主题（隶属于一级主题） |
| query_text | 用户真实请求 session，"\|" 为分割符号 |

**测试 query 示例**：

- 帮我找出闹钟相关的100条现网query
- 根据类别采样1k现网样本
- 筛选出top10类别的200条样本

## 模型资源

模型服务为 OpenAI 兼容协议：

- Base URL: `http://1239mxgn96959.vicp.fun:4009`
- 可选模型：`glm-5.2` / `glm-5.1`
- API key 放在 `.env` 中（`LLM_API_KEY=...`），代码通过环境变量读取。`.env` 已在 `.gitignore` 中，**任何凭证不得写入代码或提交到版本库**。
