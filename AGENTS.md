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

**2026-09-12 更新：阶段 1 主链路已闭合**（上传 → 解析 → 落库 → 切块 → 向量化 → 检索 → 带来源回答），
并补上了上传进度反馈、结构化 trace 与可重复的检索评测。

**2026-09-13 更新：链路从"能跑"到"界面能用"**（三批）：

- **前端接真实问答**：`src/lib/apiClient.ts`（统一 base URL / JSON / 错误映射，`upload.ts` 已复用它）
  + `src/features/chat/api/chatApi.ts`（`POST /api/chat`，snake_case → camelCase）；
  `ChatPanel` 渲染答案的来源条目（页码 / 文档）并可点击高亮，后端错误（503 未配模型、连不上后端）**显示出来**。
  `ChatResponse.usage` 回传回答那次的 token 用量，面板按真实值累加（provider 不回传时为 `null`）。
- **会话与消息落库**：`ChatSessionService` 在回答成功后落 `chat_sessions` / `chat_messages`，
  `GET /api/chat/sessions/{session_id}/messages` 回读；回答失败**不落库**。
- **模型配置接 HTTP**：`/api/providers`（列表 / 单个 / 新增 / 更新 / 删除 / 激活 / 当前激活），
  界面「设置」齿轮打开 `ProviderPanel`。响应**永不包含 `api_key`**；重名 → 409。

各处现状：

- `backend-python/app/rag/`：**已实现**（`retriever` / `context_builder` / `vector_index_builder`）；
  46 条 golden set 实测 **HitRate@5 90.0% / @20 97.5% / MRR 0.845**（[`docs/eval-report-golden.md`](docs/eval-report-golden.md)）。
  ⚠️ 这个数字与此前 12 条的 66.7% **口径不同、不可直接比较**（判定方式、数据集、`chunk_size` 都变了）。
- `backend-python/app/tools/`：6 个工具**已实现、且已接生产对象**（2026-09-13）——
  `app/tools/adapters.py` 提供检索适配器（含 workspace 过滤）与 session 作用域仓储代理，
  `app/tools/factory.py` 的 `build_tools()` 是唯一装配入口；规格
  [`docs/specs/us-stage2-tools-wiring.md`](docs/specs/us-stage2-tools-wiring.md)。
- `backend-python/app/agents/`：`RouterAgent`（三分类 + 降级，降级与否记在 `degraded`）与 `ChatAgent`
  **已接真实检索上下文**（由 `ChatService` 注入，不再是 mock）；阶段 2 起支持**有界工具循环**
  （模型自主调用检索工具，失败/超时降级直答），规格
  [`docs/specs/us-stage2-agent-tool-loop.md`](docs/specs/us-stage2-agent-tool-loop.md)。
- `src/features/workspace/`：三栏界面已接真实问答（`WorkspacePage` → `chatApi` → 后端），
  但**中间的文档正文与左侧文件列表仍是本地 mock** —— 接真数据需要新的"文档单元内容查询"接口（后端暂无）。
- 可观测性：结构化 trace 已落地（`agent_traces` 表 + `GET /api/traces/{trace_id}`）。
- 评测：`eval/` 有 46 条 golden set 与 L1 跑分脚本；**L2 生成层（引用准确率 / 拒答正确率）尚未做**，
  需要 LLM provider key。

闭环规格：`docs/specs/us-stage1-ingest.md`、`us-stage1-chat.md`、`us-stage1-upload-async.md`、`us-stage1-trace.md`、
`us-stage1-ui-integration.md`（界面接入：前端真实问答 / 会话持久化 / 模型配置）、
`us-stage2-tools-wiring.md`（Agent 工具接生产对象）、
`us-stage2-agent-tool-loop.md`（Agent 工具循环与降级）。

**生产向量配置（2026-09-12 起）**：`intfloat/multilingual-e5-large`（1024 维，序列上限 512 token）。
e5 系列要求 query / passage 前缀，由 `settings.EMBEDDING_QUERY_PREFIX` / `EMBEDDING_PASSAGE_PREFIX` 配置；
**换模型会改维度，必须重建 vec0 索引**（`init_db` 在维度不一致时会明确报错）。

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
- `src/features/workspace/`：主学习工作区。`components/left/FileManager.tsx`、`components/left/SectionTree.tsx`、`components/center/DocumentViewer.tsx`、`components/right/ChatPanel.tsx` 及其测试都在这里，是前端覆盖率的主要来源。页面级测试按主题分文件：`WorkspacePage.test.tsx`（reducer 与布局）、`WorkspacePage.chat.test.tsx`（问答接入）、`WorkspacePage.settings.test.tsx`（模型配置入口）。
- `src/features/chat/`：`api/chatApi.ts` + 测试（问答协议封装，**已接生产**）；`components/`、`pages/` 仍是占位。
- `src/features/provider/`：`api/providerApi.ts` + `components/ProviderPanel.tsx`（模型配置面板，**已接生产**）。
- `src/features/document/`：文档上传、列表、详情、文档单元展示的前端占位。
- `src/features/section/`：章节树和章节内容展示的前端占位。
- `src/features/analysis/`：分析目标、分析类型和分析结果展示的前端占位。
- `src/features/export/`：导出入口占位。
- `src/lib/`：前端通用库。`apiClient.ts`（base URL / JSON 请求 / `ApiError` 错误映射，**新代码走它**）、`title.ts`（`normalizeTitle`）、`upload.ts`（上传 + 进度轮询，复用 `apiClient`），均有对应 Vitest 测试。
- `src-tauri/`：Tauri 桌面端。当前实际注册的 command 只有 `greet`，其他 commands、DTO、services、db、errors 模块均为后续扩展占位。
- `backend-python/app/`：Python 后端主体，按 `api`、`schemas`、`services`、`repositories`、`entities`、`enums`、`parsers`、`rag`、`tools`、`agents`、`prompts`、`providers`、`utils`、`config`、`db` 分层。
- `backend-python/tests/`：Python 测试，分 `unit/`（`agents`、`api`、`entities`、`parsers`、`prompts`、`providers`、`services`、`tools`、`utils`）与 `integration/`（`api`、`document`、`persistence`）两层，共用 `conftest.py` 和 `fixtures/`。
- `docs/`：公开文档。`specs/` 放各批 US 规格（chunking / vector-index / embedding / retrieval / ingest / chat / upload-async / trace / ui-integration）；根目录放实验与诊断报告（`eval-report.md`、`eval-report-golden.md`、`retrieval-diagnosis.md`）。
- `eval/`：L1 检索评测（`golden_set.jsonl` + `run_eval.py`）。**零 LLM 成本、完全可重复**，走生产链路并自带口径自检；判定口径与已知局限见 [`eval/README.md`](eval/README.md)。
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
- `ChatSession` / `ChatMessage`：工作区或文档范围内的会话和消息，消息角色为 `user` 或 `agent`。**已接生产写入**：`ChatSessionService` 负责落库，助手消息的来源存成 `source_context_json = {"sources": [...]}`。
- `IngestJob`：一次上传摄取任务（`queued → running → succeeded / failed`），承载阶段进度与可序列化摘要；**落库**而非放内存，以便重启后仍可查。
- `AgentTrace`：一条结构化 span（属性对齐 OTel `gen_ai.*`，本项目扩展用 `greenbean.*` 前缀）；一次提问或一次上传的 span 共享同一个 `trace_id`。

## 后端设计意图

- `api/` 负责接口控制器，后续可接 FastAPI 或其他 Python Web 框架。
- `schemas/` 负责请求和响应 Pydantic 结构。
- `services/` 组织业务流程，例如文档摄取、切块、Embedding、章节、分析、聊天、导出。
- `repositories/` 负责实体持久化读写。
- `parsers/` 负责 PDF、图片 OCR、纯文本等输入解析。
- `rag/` 负责页面索引、向量索引、检索、重排和上下文构建。
- `tools/` 面向 Agent 暴露文档检索、Chunk 搜索、章节上下文、已有分析结果、测验和 Todo 生成能力。
- `agents/` 负责编排分析、聊天、学习助手和待办生成任务。
- `providers/` 是 LLM provider 抽象层（`base` / `registry` / `openai_compat_provider`），已支持 OpenAI function calling 口径的 `tools` / `tool_calls`。
- `prompts/` 集中维护分析、聊天和 Todo 的提示词模板。

## 前端与桌面端设计意图

- 前端使用 feature-first 目录，新增 UI 时优先放入对应 `src/features/<feature>/` 下，再把跨功能代码沉淀到 `src/lib`、`src/components` 或 `src/types`。
- 协议封装统一放 `src/features/<feature>/api/`：`upload.ts` / `chatApi.ts` / `providerApi.ts` 都走 `src/lib/apiClient.ts`，不要再各自复制 base URL 或错误解析。
- 后端字段是 snake_case 时，**要么整体沿用 snake_case（`upload.ts` 的 `IngestJob`、`providerApi.ts`）**，
  **要么在 api 层一次性转成 camelCase（`chatApi.ts` 的来源条目）** —— 二选一，别让组件同时见两套命名。
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

L1 检索评测（走生产链路，零 LLM 成本；需要指定含 PDF 的语料目录）：

```bash
python eval/run_eval.py --docs-dir "<语料目录>" --out docs/eval-report-golden.md
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
- ⚠️ `tsc --noEmit` **当前不是绿的**：`App.test.tsx`、`DocumentViewer.tsx`、`WorkspacePage.tsx` 等**未改动**文件上有既存的
  `noUnusedLocals` 报错。CI 只跑 vitest、不跑 tsc，所以这些错误不影响流水线 —— 但新增代码别再往上加新的。
- ⚠️ **mock `framer-motion` 时组件类型必须缓存**：如果 `motion` 的 Proxy 每次 `get` 都返回新函数，
  React 会认为组件类型变了 → 卸载并重建整棵子树 → DOM 节点被替换，
  于是"先 `fireEvent.change` 再 `fireEvent.keyDown`"会作用在**已脱离文档的旧节点**上，交互静默失效
  （表现为"点了发送什么都没发生"，很难查）。`WorkspacePage.chat.test.tsx` / `WorkspacePage.settings.test.tsx`
  里的 mock 是正确写法；`WorkspacePage.test.tsx`（上游遗留）仍是每次新建，改动它时要当心。

## 当前注意事项

- 后端主链路（`rag/`、`tools/`、`services/`、`api/`）已实现，且**上传（异步 + 进度）与问答（带来源）两条闭环已打通**，
  问答链路还接了会话落库与模型配置接口；
  **仍为占位的**只有：
  `agents/{study,todo}_agent.py`、`api/{analysis,export,section}_controller.py`、
  `rag/{page_index_builder,reranker}.py`、`services/{document_unit,export,prompt_context,section}_service.py`、
  `repositories/prompt_context_repository.py`、`entities/prompt_context.py`、若干 `schemas/*` 与 `enums/*`。
  动手前先确认，不要按文件名假设已完成；实现功能时应同时补测试。
- ⚠️ **SQLite 只允许一个写者**（本 fork 已踩过两次）：**不要在数据库事务内部去写别的表**
  （上传任务进度、trace、会话消息都算），否则必然 `database is locked`，而且加 `busy_timeout` 也救不了
  —— 持锁的就是同一个线程。解法是把耗时计算挪到事务之外，让写操作各自成事务。
  见 [`docs/specs/us-stage1-upload-async.md`](docs/specs/us-stage1-upload-async.md) §3.2、
  [`docs/specs/us-stage1-trace.md`](docs/specs/us-stage1-trace.md) §3.4，
  以及 `ChatService.answer()`（回答成功之后才落库，且自成事务）。
- 新增表都遵循"纯新增 + `CREATE TABLE IF NOT EXISTS`"：`ingest_jobs`、`agent_traces`；
  `chat_sessions` / `chat_messages` 是上游就建好的表，本批才真正写入。旧库启动时会自动补建；
  换 embedding 模型仍需重建 vec0 索引，这几张表不受影响。
- ⚠️ **`provider_configs.api_key` 目前是明文存 SQLite**，响应层不返回它（`ProviderConfigResponse` 没有该字段），
  但库里和日志里是明文 —— 自己机器上 demo 可接受，**别把带 key 的 `data/*.db` 提交或外发**。
  加密存储尚未做。
- 默认工作区 `"default"` 在前端（`chatApi.ts` 的 `DEFAULT_WORKSPACE_ID`）与后端
  （`chat_session_service.py` 的 `DEFAULT_WORKSPACE_ID`）各有一份常量：**改一处必须改另一处**，
  否则历史会话会归到两个不同的工作区。
- 会话 ID 存在浏览器 `localStorage`（`src/features/chat/sessionStore.ts`，键 `greenbean.chat.session_id`）：
  打开工作区时按它回读后端历史（`GET /api/chat/sessions/{id}/messages`）。
  **存储不可用时降级为内存会话**（隐私模式会直接抛异常，不能让它把界面搞崩）；读取以持久化存储为准，
  内存值只在存储不可用时兜底。界面上目前没有"新建会话"入口 —— 要开新会话得清掉这个键。
- ⚠️ `WorkspacePage` 的测试注意：页面**挂载即拉一次历史**，所以断言不能再拿 `fetchMock.mock.calls[0]`
  当"提问那次调用"，要按 URL / method 找（见 `WorkspacePage.chat.test.tsx` 的 `findAskCall`）。
- `src/lib/apiClient.ts` 是**唯一的 HTTP 层**：它把 `fetch` 的任何 reject 统一包成 `ApiError`（带 HTTP 状态码，
  网络不通时 `status = 0`），`upload.ts` 的 `readJob` 也用同一个错误类型。所以调用方拿到的一定是 `Error` ——
  组件里再写 `e instanceof Error ? e.message : "…"` 时，后半截是**不可达的防御分支**，不必为它硬凑测试；
  要区分"没配模型(503) / 会话不存在(404) / 后端没起来(0)"读 `ApiError.status` 即可。
- `eval/` 是评测集的家：改动检索 / 切块 / embedding 模型后应跑一次
  `python eval/run_eval.py --docs-dir "<含 PDF 的语料目录>"`。它走**生产链路**并自带口径自检
  （关键词是否真出现在期望页、no_answer 是否其实有答案）—— 首轮报告正是在这两点上栽过。
- `backend-python/tests/.coveragerc` 里 `fail_under = 100`：**覆盖率是硬门槛**。只跑 `pytest tests` 看不出问题，
  提交前请跑 `pytest --cov=app --cov-config=tests/.coveragerc`（或 `npm run test:python:coverage`）。
  本仓库**不使用** `pragma: no cover` 豁免 —— 未覆盖的分支要写测试，或说明为什么它是不可达的防御分支。
  （**依赖注入函数如 `get_provider_controller` 也会计入覆盖率**：测试里通常被 `dependency_overrides` 盖掉，
  所以需要单写一个用例直接调它。）
- Python 实体和测试中的部分中文描述当前呈现为乱码，疑似历史编码问题。除非任务要求修复编码，否则不要顺手大范围改写，以免扩大变更。
  （在 Windows 控制台里跑 pytest 时，中文输出显示为乱码也是同一个原因，**不代表文件内容坏了**。）
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
- 既有测试需要按新行为更新时（例如新增约束导致老用例的 mock 缺 `get_by_name`），
  **同时补上覆盖新行为的用例**，不要只把断言改松。
