# Changelog

本文件记录**本 fork** 的变更（格式：[Keep a Changelog](https://keepachangelog.com/)；
版本号遵循 [SemVer](https://semver.org/)，与 `planning/` 的里程碑对齐，见 [`docs/versioning.md`](docs/versioning.md)）。

> **归属说明**：本仓库是 [`GreenBeanICE/greenbean-study-assistant`](https://github.com/GreenBeanICE/greenbean-study-assistant)（MIT）的
> 个人 fork 续作。**上游历史不在此重复**（fork 点 = 上游 `5e79877`）；
> 本文件从本 fork 的第一个提交（`f0c5f28`）开始记录。我在上游的原始贡献是 PR
> [#26](https://github.com/GreenBeanICE/greenbean-study-assistant/pull/26)（48 files / +5466 行：多格式解析器与摄取管线）。

## [Unreleased]

### Added
- 版本管理方案与公开路线图：[`docs/versioning.md`](docs/versioning.md)、[`docs/roadmap.md`](docs/roadmap.md)、本文件。

## [0.1.0] - 2026-09-14

**工程 MVP**：上传 → 解析 → 落库 → 切块 → 向量化 → 检索 → 带来源回答，界面接真实数据，
指标与成本可量化、可复现。

### Added

**检索链路**
- 文档切块（`ChunkService`：段落优先 + 窗口回退 + overlap，纯函数）
- 向量索引（`embedding_index` vec0 虚拟表 + 双写 `embedding_vectors`）
- 向量化（`EmbeddingService`，本地 `fastembed`，可注入模型；超长文本截断）
- 语义召回与上下文组装（`rag/retriever` + `rag/context_builder`，输出 `[来源 N]` 标记块）
- 摄取闭环（落库 → 切块 → 向量化，`app/db/runtime` 统一装配）
- 问答闭环（`ChatService` 路由 → 检索 → 预算裁剪 → Agent；`POST /api/chat`）

**Agent 与工具**
- 六个工具接生产对象（`tools/adapters.py` 检索适配 + workspace 过滤；`tools/factory.py` 统一装配）
- Agent 有界工具循环（模型自主调用检索工具，失败/超时/轮数用尽 → 降级直答）
- 六个工具按 **MCP 协议**暴露（stdio server，`mcp` SDK 2.x）

**可观测性与配置**
- 结构化 trace（`agent_traces` 表，字段对齐 OTel `gen_ai.*`；问答与上传双链路）
- 模型配置接 HTTP（`/api/providers` 列表/新增/更新/删除/激活；响应**不回传 `api_key`**）

**前端**
- 工作区接真实数据：文档列表（`GET /api/documents`）、逐页正文（`.../units`）、来源点击跳原文页
- 会话与消息落库 + 刷新后按 `localStorage` 会话 ID 自动恢复历史
- 回答正文里的 `[来源 N]` 可点击跳转（序号越界时不伪装成可点击）
- 上传进度条（异步受理 202 + 轮询 `ingest_jobs` 状态）

**评测与账本**
- L1 检索评测（46 条私人语料 + 30 条**自产可分发**合成语料；`run_eval.py` 走生产链路 + 口径自检）
- L2 生成层评测（引用准确率 / 拒答双口径 / 工具循环 / 延迟·token；两套语料各一份报告）
- 评测门禁进 CI（每 push 用真 e5-large 跑冒烟集，自检失败 exit 2）
- 成本与延迟账本（单次提问 ≈ ¥0.01；L2 全量 < ¥1；L1 零 LLM 成本）

### Changed
- 生产 embedding 切到 `intfloat/multilingual-e5-large`（1024 维，内建 query/passage 前缀）
- `RETRIEVAL_TOP_K` 5 → 20；上下文加 `CONTEXT_MAX_CHARS` 预算
- 解析阶段还原 PDF 被拆裂的法语重音（`PDFParser` 1.1.0）

### Fixed
- `init_db` 的 sqlite-vec 加载**从未真正生效**（测试被假 loader 掩盖）
- 前端 `api_mode` 写成 `openai_compat`（下划线）而后端枚举是 `openai-compat` → 保存配置必然 422
- `ProviderRegistry` 进程内单例重启后为空 → "界面显示已激活、问答 503"（`lifespan` 恢复）
- 提示词教模型写 `[p.12]` 而上下文里是 `[来源 N]` → 引用率 35% → 100%
- 文档滚动定位查询 `id="block-…"` 而实际属性是 `data-block-id`（定位从未生效）
- L2 报告把样本数硬编码成 46 条（跑 30 条语料时报告一生成就是错的）
- 上游带进仓库的真实课件 fixture 替换为**自产**合成语料（去掉著作权风险）

### Docs
- `docs/specs/`：13 份 US 规格；`docs/`：检索诊断、四份评测报告、成本账本、demo 分镜
- `AGENTS.md` / `README.md` 与当前状态对齐，并沉淀踩坑记录（SQLite 单写者、契约不一致等）

[Unreleased]: https://github.com/wenkais196-Gabriel/greenbean-study-assistant-personal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wenkais196-Gabriel/greenbean-study-assistant-personal/releases/tag/v0.1.0
