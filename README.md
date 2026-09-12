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
- **本 fork 中由我继续推进的部分**：文档切块与向量检索链路、Agent 工具调用与编排、
  评测集与产品文档。进度见下方「开发路线」。
- 本仓库为个人学习与求职用途，**不向上游提交 PR**，完整 git 历史予以保留。

## 当前状态

这是一个**仍在施工中**的仓库，请勿把占位文件当作已完成功能。

| 层 | 状态 |
|---|---|
| 文档解析（`app/parsers/`）、文档摄取（`app/services/`）、持久化（`app/db/`、`app/repositories/`）、实体（`app/entities/`） | 已实现，有测试覆盖 |
| 前端工作区界面（`src/features/workspace/`） | 已实现，有测试覆盖 |
| 检索链路（`app/rag/`）、Agent 工具（`app/tools/`）、切块与向量化（`app/services/chunk_service.py`、`embedding_service.py`） | **占位，尚未实现** |
| `ChatAgent` | 使用硬编码的 mock 检索上下文，待接入真实检索 |

实测基线（本机 Windows / Python 3.12 / Node 24）：

- Python：`228 passed`，覆盖率 `100%`
- 前端：`233 passed`（10 个测试文件），语句覆盖率 `96.45%`

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

1. **阶段 0 · 干净 fork 与全绿**：本机跑通全部测试，CI 无 SonarQube 依赖，归属说明就位。
2. **阶段 1 · 检索链路**：切块策略 → 向量化 → 本地向量索引（sqlite-vec / FAISS，不引入额外服务）→ 召回 → 上下文组装，并保留 `document_id` / `page` / `section` 溯源元数据。
3. **阶段 2 · Agent 化**：`providers/base.py` 支持 tool calling，`chunk_search` / `document_retrieval` / `section_context` 三个工具由 Agent 自主调用，带失败降级与 `citations` 引用回溯。
4. **阶段 3 · 评测与产品化**：25 条 golden query 的评测集与跑分脚本、指标报告、可点击引用的最小界面。
5. **阶段 4 · 包装**：README 终稿、架构图、demo 录屏、技术笔记。

## 许可

MIT，见 [LICENSE](LICENSE)。原始版权归上游作者所有，本 fork 的修改同样以 MIT 发布。
