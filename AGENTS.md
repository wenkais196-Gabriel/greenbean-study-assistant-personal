# GreenBean Study Assistant 项目说明

## 交流约定

- 除非用户另有明确指示，回答和项目说明都使用中文。
- 改动前先阅读相关目录和测试，优先沿用现有分层、命名和占位结构。
- 不要回滚用户已有改动；如果发现工作区有无关改动，保持原样。
- **本仓库是上游仓库的个人 fork 续作，上游已停止推进**：不向上游提交 PR，也不同步
  （sync）上游改动，一切改动只在本地 `origin` 上推进。

## 项目定位

GreenBean Study Assistant 是面向在法国学习的中文学生的 AI 课程资料助手。上游仓库为
[`GreenBeanICE/greenbean-study-assistant`](https://github.com/GreenBeanICE/greenbean-study-assistant)（MIT）。
**本仓库是该上游的个人 fork 续作**：上游自 2026-06 起停止推进，本 fork 在其基础上独立继续开发。

当前施工重心是打通「解析 → 切块 → 检索 → Agent → 带引用回答」这条链路，落点在三处：

- `backend-python/app/rag/`：全文占位，检索、上下文组装、索引构建都要在这里实现。
- `backend-python/app/tools/`：全文占位，面向 Agent 的工具定义与实现。
- `backend-python/app/agents/`：可运行，但都是单轮"拼 prompt → 调一次 provider → 解析 JSON"，
  没有 tool calling、没有多步编排、没有检索闭环；`ChatAgent` 目前用的是硬编码 mock 上下文。

上游团队已完成、可直接复用的部分：文档解析器、文档摄取管线、持久化层、领域实体和前端
工作区界面。改动这些代码时保持其原有分层与命名，不要顺手重写。

## 技术栈

- 前端：React 19、TypeScript、Vite 7、Vitest、Testing Library、jsdom。
- 桌面端：Tauri 2、Rust 2021、`tauri-plugin-opener`。
- Python 后端：Python 3.12 兼容测试环境、Pydantic v2、pytest、pytest-cov。
- 质量与覆盖率：GitHub Actions 分别跑前端、Python、Rust 测试并产出覆盖率报告。本 fork
  已移除 SonarQube 扫描（fork 中没有 `SONAR_TOKEN`，上游的 `sonar` job 必然失败）。

## 目录结构

- `src/`：前端代码。`App.tsx` 是 SplashScreen → WorkspacePage 的入口切换；`features/` 采用按业务功能分组的结构。
- `src/features/home/`：启动闪屏。（上游曾把 `App.tsx` 放在 Tauri 官方 greet 示例上，现已替换。）
- `src/features/workspace/`：主学习工作区。`components/left/FileManager.tsx`、`components/left/SectionTree.tsx`、`components/center/DocumentViewer.tsx`、`components/right/ChatPanel.tsx` 及其测试都在这里，是前端覆盖率的主要来源。
- `src/features/document/`：文档上传、列表、详情、文档单元展示的前端占位。
- `src/features/section/`：章节树和章节内容展示的前端占位。
- `src/features/analysis/`：分析目标、分析类型和分析结果展示的前端占位。
- `src/features/chat/`：继续追问、消息列表和 Prompt 上下文面板的前端占位。
- `src/features/export/`：导出入口占位。
- `src/lib/`：前端通用库。`title.ts` 目前只有 `normalizeTitle`，有对应 Vitest 测试。
- `src-tauri/`：Tauri 桌面端。当前实际注册的 command 只有 `greet`，其他 commands、DTO、services、db、errors 模块均为后续扩展占位。
- `backend-python/app/`：Python 后端主体，按 `api`、`schemas`、`services`、`repositories`、`entities`、`enums`、`parsers`、`rag`、`tools`、`agents`、`prompts`、`providers`、`utils`、`config`、`db` 分层。
- `backend-python/tests/`：Python 测试，分 `unit/`（`agents`、`api`、`entities`、`parsers`、`prompts`、`providers`、`services`、`utils`）与 `integration/`（`api`、`document`、`persistence`）两层，共用 `conftest.py` 和 `fixtures/`。
- `data/`：本地数据目录。只应保留 `.gitkeep`，数据库和用户上传文件不应提交。
- `coverage/`：测试覆盖率输出目录，不应提交。
- `.github/workflows/quality.yml`：CI 分前端、Python、Rust 三个 job 跑测试并上传覆盖率 artifact。（fork 中已删除上游的 SonarQube 扫描 job 与 `.github/dependabot.yml`。）

## 主要领域模型

- `Workspace`：工作区，默认类型包括 `course`、`admin`、`internship`、`language`、`other`，也允许自定义类型。
- `DocumentRecord`：上传文档记录，包含工作区、标题、原始文件名、文件类型、本地路径、hash、状态和页数。
- `DocumentUnit`：上传文件经过第一道解析和标准化后的统一原文单元。不同文件格式应先被拆成一致的 `DocumentUnit` 结构，例如 PDF 的每一页、PPT 的每一张 slide。保存顺序、正文、页码或页序、字符范围、token 数、解析元数据和原始布局/OCR 信息。
- `Section`：基于 `DocumentUnit` 切分和组织出来的结构索引树，通常表现为带索引的树形 JSON，用于后续 PageIndex、章节导航和结构化上下文准备。
- `SectionUnitLink`：章节和内容单元的多对多关联，要求持久化层保证同章节内关联和排序唯一。
- `Chunk`：基于 `DocumentUnit` 切分出来的 RAG 语义片段，用于向量化、语义检索和上下文拼接；`Chunk` 应能追溯回来源 `DocumentUnit`。
- `EmbeddingVector`：`Chunk` 的语义向量，校验 `vector` 长度必须等于 `vector_dimension`，并且必须关联到已存在的 `Chunk`。
- `AnalysisResult`：AI 分析结果，支持全文分析和章节分析；章节分析必须有 `section_id`，全文分析不能设置 `section_id`。
- `ChatSession` / `ChatMessage`：工作区或文档范围内的会话和消息，消息角色为 `user` 或 `agent`。

## 后端设计意图

- `api/` 负责接口控制器，后续可接 FastAPI 或其他 Python Web 框架。
- `schemas/` 负责请求和响应 Pydantic 结构。
- `services/` 组织业务流程，例如文档摄取、切块、Embedding、章节、分析、聊天、导出。
- `repositories/` 负责实体持久化读写。
- `parsers/` 负责 PDF、图片 OCR、纯文本等输入解析。
- `rag/` 负责页面索引、向量索引、检索、重排和上下文构建。
- `tools/` 面向 Agent 暴露文档检索、Chunk 搜索、章节上下文、已有分析结果、测验和 Todo 生成能力。
- `agents/` 负责编排分析、聊天、学习助手和待办生成任务。
- `providers/` 是 LLM provider 抽象层（`base` / `registry` / `openai_compat_provider`），阶段 2 要在这里扩展 tool calling。
- `prompts/` 集中维护分析、聊天和 Todo 的提示词模板。

## 前端与桌面端设计意图

- 前端使用 feature-first 目录，新增 UI 时优先放入对应 `src/features/<feature>/` 下，再把跨功能代码沉淀到 `src/lib`、`src/components` 或 `src/types`。
- `vite.config.ts` 为 Tauri 开发固定使用 `5173` 端口，并忽略监听 `src-tauri`。
- `src-tauri/tauri.conf.json` 的产品名为 `greenbean-study-assistant`，应用标识为 `com.greenbean.study`，开发时会先运行 `npm run dev`。
- Tauri 当前只暴露 greet 示例。后续实现桌面能力时，应优先补齐 `src-tauri/src/commands`、`dto`、`services`、`errors` 的占位模块，而不是把逻辑堆在 `lib.rs`。
- Tauri 桌面壳暂时保留但不投入：单人维护成本高（打包、三平台、`src-tauri/gen`），且对当前目标（检索 + Agent + 评测）没有加分。是否删除留到阶段 1 结束后再定。

## 常用命令

```bash
npm ci
npm run dev
npm run build
npm run test:frontend
npm run test:python
npm run test:rust
npm run test:all
npm run test:coverage:sonar
npm run tauri -- dev
```

Python 依赖安装：

```bash
cd backend-python
python -m venv .venv
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## 测试与质量

- 前端测试使用 Vitest，配置在 `vitest.config.ts`，覆盖率输出到 `coverage/frontend`。
- Python 测试使用 pytest，`backend-python/tests/conftest.py` 会把 `backend-python` 加入 `sys.path`。
- ⚠️ **提交前请跑 CI 的同一命令**：`pytest --cov=app --cov-config=tests/.coveragerc`（或 `npm run test:python:coverage`）。
  `tests/.coveragerc` 里 `fail_under = 100`，只跑 `pytest tests` **不会**发现覆盖率不足 ——
  已因此让 4 个 commit 在 CI 的 Python job 变红（前端与 Rust job 一直是绿的）。
- `npm run test:python` 经 `scripts/run-pytest.cjs` 转发，会优先使用 `backend-python/.venv` 里的解释器；也可用 `PYTHON` 环境变量指定。
- Rust 测试在 `src-tauri` 内执行 `cargo test`；覆盖率脚本依赖 `cargo llvm-cov`。
- CI 使用 Node.js 22、Python 3.12，并在 Linux 上安装 Tauri 所需系统依赖。
- `sonar-project.properties` 是上游遗留的 SonarQube 配置，本 fork 不再运行扫描，保留仅供参考。
- 图片 OCR 解析器的测试使用 mock，不需要本机安装 Tesseract 引擎。

## 当前注意事项

- 很多模块是占位文件，不要误认为功能已完成。实现功能时应同时补测试。
- `rag/`、`tools/`、`services/chunk_service.py`、`services/embedding_service.py` 在覆盖率报告里显示为 0 行，这是预期现状，不是遗漏。
- Python 实体和测试中的部分中文描述当前呈现为乱码，疑似历史编码问题。除非任务要求修复编码，否则不要顺手大范围改写，以免扩大变更。
- `planning/` 是本地私有的规划与决策记录（已加入 `.gitignore`），不要提交到仓库，也不要把它当作公开文档改写。
- `data/*.db`、`data/uploads/*`、`coverage/`、`node_modules/`、Python 缓存和 Rust `target/` 都应保持未跟踪。
- `src-tauri/Cargo.lock` 已被跟踪；作为桌面应用，继续保留锁文件。
- 新增 Tauri command 时要同步更新 `invoke_handler`、必要的 DTO、权限能力和前端调用封装。
- 新增 Python 实体时优先使用 Pydantic v2、UUID 字符串 ID、UTC 时间戳，并把跨字段约束写成模型校验。

## 代码质量

- 不能只靠"测试通过 + 覆盖率达标"判断改动质量，要一并检查重复字面量、重复代码和类型注解正确性。
- 避免重复字面量和重复代码；同一语义且会同步变化的内容应提取常量或共享实现，但不要过度抽象。
- 类型注解应使用工具支持的类型表达，不要把不支持下标的运行时类写成 `Class[Type]`。
- 交付前清理新增的重复代码与坏味道；确需保留时说明理由。
