# GreenBean Study Assistant（个人续作版）

面向在法国学习的中国学生的 **本地课程资料问答助手**：把课程 PDF / PPT / Word / 图片
解析成统一结构，再基于这些资料回答问题，答案带页码引用。

> 上游简介：An AI course material assistant for Chinese-speaking students studying in France.

## 这是 fork 续作，不是原创项目

- **上游**：[`GreenBeanICE/greenbean-study-assistant`](https://github.com/GreenBeanICE/greenbean-study-assistant)（MIT，`Copyright (c) 2026 绿豆冰`）
- **我在上游的原始贡献**：多格式文档解析器（PDF / PPT / Word / 纯文本 / 图片 OCR）、
  文档摄取管线 `backend-python/app/services/document_ingest_service.py`、
  `PageIndex` 统一结构及其测试套件、相关技术文档。
  对应上游 PR [#26](https://github.com/GreenBeanICE/greenbean-study-assistant/pull/26)（48 files，+5466 行）。
- **本 fork 中由我继续推进的部分**：文档切块与向量检索链路、问答闭环与前端接入、
  模型配置接口、评测集与产品文档。进度见下方「开发路线」。
- 本仓库为个人学习与求职用途，**不向上游提交 PR**，完整 git 历史予以保留。

## 当前状态

这是一个**仍在施工中**的仓库，请勿把占位文件当作已完成功能。

| 层 | 状态 |
|---|---|
| 文档解析（`app/parsers/`）、文档摄取（`app/services/`）、持久化（`app/db/`、`app/repositories/`）、实体（`app/entities/`） | 已实现，有测试覆盖 |
| 前端工作区界面（`src/features/workspace/`） | 已实现，有测试覆盖 |
| 检索链路（`app/rag/`）、切块与向量化（`app/services/chunk_service.py`、`embedding_service.py`） | 已实现，有测试覆盖 |
| 上传（异步受理 + 进度轮询）与问答闭环（`POST /api/documents/upload`、`POST /api/chat`） | 已实现，有测试覆盖 |
| 前端接入真实问答 + **历史恢复**（`src/lib/apiClient.ts`、`chat/`、`sessionStore.ts`、来源高亮、失败可见） | 已实现，有测试覆盖 |
| 会话与消息持久化（`chat_sessions` / `chat_messages`、`GET /api/chat/sessions/{id}/messages`） | 已实现，有测试覆盖；刷新后按本地会话 ID **自动恢复** |
| 模型配置（`/api/providers` 列表 / 新增 / 更新 / 删除 / 激活，界面「设置」面板） | 已实现，有测试覆盖；**响应不回传 `api_key`**，重名回 409 |
| 结构化 trace（`agent_traces`，字段对齐 OTel `gen_ai.*`） | 已实现 |
| L1 检索评测（`eval/`） | 已实现：46 条 golden set，零 LLM 成本、完全可重复 |
| Agent 工具（`app/tools/`） | 已实现，但**尚未接生产对象**（每个工具 docstring 里写了待办） |
| Agent 编排（`app/agents/`） | **单轮**：路由 → 检索 → 带来源回答；tool calling / 多步编排待阶段 2 |
| 生成层评测（L2：引用准确率 / 拒答正确率） | 未做 —— 需要 LLM provider key |

实测基线（本机 Windows / Python 3.12 / Node 24）：

- Python：`450 passed`，覆盖率 `100%`（`fail_under=100` 硬门槛）
- 前端：`289 passed`（19 个测试文件）
- 检索（L1，40 条可评测）：HitRate@5 `90.0%`、@20 `97.5%`、MRR `0.845`
  —— 见 [`docs/eval-report-golden.md`](docs/eval-report-golden.md)、[`eval/README.md`](eval/README.md)

## 快速开始

```bash
git clone https://github.com/wenkais196-Gabriel/greenbean-study-assistant-personal.git
cd greenbean-study-assistant-personal

# 前端
npm ci

# 后端
cd backend-python
python -m venv .venv
.venv/Scripts/activate        # Windows (Git Bash)；macOS / Linux 用 source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## 测试

```bash
npm run test:frontend          # Vitest
npm run test:python            # pytest（scripts/run-pytest.cjs 会优先使用 backend-python/.venv）
```

覆盖率报告：

```bash
npm run test:frontend:coverage
npm run test:python:coverage
```

> 图片 OCR 解析器的测试使用 mock，**不需要**本机安装 Tesseract 引擎。

## 技术栈

- 前端：React 19、TypeScript、Vite 7、Vitest、Testing Library
- 桌面端：Tauri 2、Rust 2021（保留，暂不投入）
- 后端：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、SQLite
- 解析：PyMuPDF、python-docx、python-pptx、pytesseract、Pillow
- LLM：`openai` / `anthropic` SDK，自建 provider 抽象层

## 开发路线

1. **阶段 0 · 干净 fork 与全绿** ✅：本机跑通全部测试，CI 无 SonarQube 依赖，归属说明就位。
2. **阶段 1 · 检索与问答闭环** ✅：上传 → 解析 → 落库 → 切块 → 向量化 → 检索 → 带来源回答；
   前端已接真实链路（来源高亮、失败可见、会话持久化），模型可在界面「设置」里配置。
3. **阶段 2 · Agent 化**（进行中）：`providers/base.py` 支持 tool calling，`chunk_search` /
   `document_retrieval` / `section_context` 等工具由 Agent 自主调用，带失败降级与引用回溯；
   并把 `tools/` 通过 MCP server 暴露出去。
4. **阶段 3 · 评测与产品化**：真实 LLM 基线（质量 / TTFT / token 成本）、L2 生成层指标
   （引用准确率 / 拒答正确率）、评测门禁进 CI、引用可跳到原文页。
5. **阶段 4 · 包装**：README 终稿、架构图、demo 录屏、技术笔记。

## 许可

MIT，见 [LICENSE](LICENSE)。原始版权归上游作者所有，本 fork 的修改同样以 MIT 发布。
