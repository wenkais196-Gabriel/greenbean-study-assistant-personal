# US · 阶段 2 · Agent 工具接生产对象

> **状态：已实现（2026-09-13）**
> 验收：`build_tools()` 一次产出 6 个工具、全部注入**生产对象**（会话工厂 / 本地嵌入 / 当前激活的 provider）；
> `chunk_search` 能按 workspace 过滤真实检索，`analysis_result` 能按 workspace 查到真实摘要。
> 前置：[`us-stage1-retrieval.md`](us-stage1-retrieval.md)（检索链路）、[`us-stage1-ingest.md`](us-stage1-ingest.md)（数据进得来）、
> [`us-stage1-ui-integration.md`](us-stage1-ui-integration.md)（provider 能在界面里配置并激活）

---

## 1. 这一批补齐的空白

此前 `app/tools/` 的 6 个工具**都写完了、测试也全绿**，但每个 docstring 都留着"接不上生产"的待办
（检索适配器、workspace 过滤、按 workspace 查询的仓储方法）。本批把这些待办清掉。

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/tools/adapters.py` | **不存在** | `ProductionChunkSearcher`（把 `Retriever` 包成工具协议 + workspace 过滤）+ 3 个 session 作用域仓储代理 |
| `app/tools/factory.py` | **不存在** | `build_tools()` / `ToolSet`：一次装配 6 个工具 |
| `app/tools/chunk_search_tool.py` | docstring："两处待办，接生产前必须先解决" | 待办清除；本工具只透传 `workspace_id`，过滤由适配器负责 |
| `app/tools/analysis_result_tool.py` | `getattr(item, "summary", "")` **恒为空串**；docstring 写着接不上生产 | 读实体上的真实 `summary` 字段 |
| `app/tools/quiz_generation_tool.py` | 提示词内联在工具里 | 提示词移到 `app/prompts/quiz_prompts.py` |
| `app/prompts/quiz_prompts.py` | **不存在** | 集中管理 quiz 提示词（与 `todo_prompts.py` 同构，含 system prompt） |
| `app/repositories/embedding_repository.py` | `search_similar(vector, top_k)` | 新增**可选** `workspace_id`（子查询关联过滤） |
| `app/repositories/analysis_result_repository.py` | 只有 `save` / `get_by_id` | 新增 `get_by_workspace_id`（`JOIN document_records`） |
| `app/rag/retriever.py` | `retrieve(repository, query)` | 新增**可选** `workspace_id`，只做透传 |
| `app/entities/analysis_result.py`、`app/db/models.py`、`app/db/init_db.py` | 没有 `summary` | 新增可空 `summary` 字段/列（旧库幂等补列，见 §5） |
| `app/config/settings.py` | — | **没有新增常量** —— 见 §4，过采样并不需要 |

## 2. Acceptance Criteria

- **AC1**：`ProductionChunkSearcher.search(query, workspace_id, top_k)` 满足 `ChunkSearchTool` 的协议，
  返回条目含 `chunk_id` / `text` / `document_id` / `page_number` / `heading_path` / `distance`。
- **AC2**：`workspace_id` 为空 → 不过滤，行为与生产问答链路一致；非空 → 只返回该 workspace 的片段。
- **AC3**：`top_k` 就是"该 workspace 内的前 k 条"（**不需要过采样**，依据见 §4）；`top_k <= 0` 抛 `ValueError`。
- **AC4**：`EmbeddingRepository.search_similar` 的 `workspace_id` 默认 `None` → 现有 `ChatService` 调用**零变化**。
- **AC5**：`AnalysisResultRepository.get_by_workspace_id` 经 `document_records` 关联过滤，**不改表结构**。
- **AC6**：`AnalysisResult` 实体与 `analysis_results` 表新增可空 `summary`；工具返回真实摘要而非空串。
- **AC7**：quiz 提示词集中在 `app/prompts/quiz_prompts.py`。
- **AC8**：`build_tools()` 走 `app/db/runtime` 的 `lazy_session_factory`（构造时不碰磁盘），产出全部 6 个工具。
- **AC9**：`DocumentRetrievalTool` / `SectionContextTool` 注入生产 repository（二者契约本来已满足，无需改工具）。
- **AC10**：`pytest --cov=app --cov-config=tests/.coveragerc` → **479 passed / 100.00%**；前端 293 passed。
- **AC11**：provider 未激活时装配**不失败**，生成类工具被调用时报 `not configured`。

## 3. 分层与"为什么需要适配层"

```
build_tools()                        ← app/tools/factory.py：唯一的生产装配入口
  ├─ ChunkSearchTool  ← ProductionChunkSearcher      ← app/tools/adapters.py
  ├─ DocumentRetrievalTool  ← SessionScopedDocumentRepository
  ├─ SectionContextTool     ← SessionScopedSectionRepository
  ├─ AnalysisResultTool     ← SessionScopedAnalysisResultRepository
  └─ Quiz/TodoGenerationTool ← ProviderRegistry.get_active()（未激活 → None）
```

工具持有的是**长期对象**，而生产的两个现实与之冲突，所以必须有这一层：

1. **生产 repository 绑定单个 session**（`DocumentRepository(session)`），而工具在装配期就要拿到 repository，
   之后每次 `run()` 才真正查库 → `SessionScoped*Repository` 让**每次调用各自开一个 session**，
   调用方不必管理 session 生命周期。
2. **生产 `Retriever.retrieve(repository, query)` 的 `top_k` 在构造期固定**，而工具的 `top_k` 是运行时参数，
   且需要 workspace 过滤 → `ProductionChunkSearcher` 每次检索按 `top_k` 现造一个 `Retriever`（构造是廉价的），
   并复用 `ContextBuilder` 把命中补全为可引用的条目。

`build_tools()` 默认 `session_factory` 用 `lazy_session_factory()`：**构造工具不会创建数据库**，
第一次真正需要会话时才建库 —— `get_ingest_service()` 之类的依赖注入因此没有副作用。

## 4. ⚠️ sqlite-vec 的过滤语义**取决于查询写法**（本批最重要的实测）

设计适配器时唯一的真问题是"按 workspace 过滤后还能不能拿满 `top_k`"。`chunks` 表**没有** workspace 列，
过滤必须经 `document_units → document_records` 关联，所以关键是：**vec0 的 `k` 是在过滤之前还是之后生效？**

实测（sqlite-vec v0.1.9，3 维玩具数据：`c1,c2,c4` 属 workspace B、`c3` 属 A，`c3` 全局排第 4）：

| 写法 | `k=2` 时能否拿到 `c3` | 语义 |
|---|---|---|
| 字面量 `AND chunk_id IN ('c3')` | ❌ 返回空 | **post-filter**（先取 k 条再过滤） |
| **子查询 `AND chunk_id IN (SELECT … WHERE workspace_id = ?)`** | ✅ 拿到 `c3` | **pre-filter**（k 作用在过滤之后） |
| `JOIN … ON chunk_id` + `AND workspace = ?` | ❌ 返回空 | **post-filter** |

**结论与取舍**：生产用的是**子查询**形式 → 是 pre-filter → `top_k` 已经精确地作用于本 workspace 的候选集，
**不需要过采样**（也因此没有引入 `RETRIEVAL_WORKSPACE_OVERFETCH_FACTOR` 之类的常量）。

> ⚠️ **这是实现细节，不是文档化保证**。所以
> `tests/integration/persistence/test_vector_index.py::test_search_similar_filters_by_workspace_before_truncating_to_top_k`
> 专门锁定它：把条件改写成 `JOIN`、或 sqlite-vec 升级后语义变化，这条用例会**先红**。
> 早先的探针用字面量 `IN` 测出的是 post-filter，据此曾误判"必须过采样" —— 教训是
> **探针要跟生产用同一种写法**。

## 5. Schema Change Justification

```
Schema Change Justification:
- User Story requirement: AC6 —— AnalysisResultTool 要返回可展示的摘要；
  此前工具用 getattr(item, "summary", "") 读一个**不存在**的字段，接生产后必然恒为空串。
- Migration required: `ALTER TABLE analysis_results ADD COLUMN summary TEXT`（可空，无默认值）。
  实现方式见 app/db/init_db.py::_ensure_analysis_result_summary —— 先查 PRAGMA table_info，
  缺列才 ALTER（SQLite 的 ADD COLUMN 不支持 IF NOT EXISTS）。与 _ensure_vector_index 同一思路。
  没有引入 Alembic：本项目的"迁移"一直是启动时的幂等建表/补列，保持一致性。
- Backward compatibility: 纯新增**可空**列。新建库直接带该列；旧库首次启动自动补齐；
  已有行的 summary 为 NULL，读出来是 None，工具层用 `item.summary or ""` 兜成空串。
  向量索引（vec0）与其他表**完全不受影响**，不需要重建。
- Data migration needed: 无。历史分析结果没有摘要可比对，NULL 是诚实的表达。
- Tests covering migration:
  test_database_initialization.py::test_analysis_results_table_has_summary_column_for_a_fresh_database（新库带列）
  test_database_initialization.py::test_analysis_result_summary_column_is_added_to_an_existing_database（旧库补列，用 DROP COLUMN 模拟旧库，并断言既有 document_records 数据不动）
  test_sqlite_repositories.py::test_repositories_persist_core_learning_data_after_reconnect（summary 往返持久化）
```

## 6. 验收实测（2026-09-13）

| 项 | 结果 |
|---|---|
| `pytest --cov=app --cov-config=tests/.coveragerc` | **479 passed，覆盖率 100.00%**（`fail_under=100`） |
| 前端 `npm run test:frontend` | **293 passed / 19 文件**（本批未改前端，跑回归确认） |
| 适配器行为（真临时库 + 真 sqlite-vec + 假模型） | workspace 过滤生效；全局第 7 名的本 workspace 片段在 `top_k=1` 时也能召回；空 query **不加载模型**；`top_k<=0` 抛错；索引孤儿命中被跳过 |
| 装配 | 6 个工具全部产出；生产适配器就位；provider 未激活时装配成功、生成类工具报 `not configured` |
| 旧库升级 | 摘掉 `summary` 列后重新初始化 → 自动补列，`document_records` 数据不变 |

## 7. 未做（待办）

1. **MCP server**：本批只做"接生产对象"；把工具经 MCP 暴露出去是下一步（需要新依赖与新的入口进程）。
2. **`analysis_result_tool` 的 `section_id`**：参数仍不参与查询（保留给将来的按小节过滤）。
3. **`quiz` 提示词的行为变化**：本批顺带给 quiz 补了 system prompt（原来只有一条 user message），
   目的是让 provider 输出更贴近可解析的 JSON（现有测试里"带 markdown 围栏 → 解析失败"就是反例）。
   真实 provider 下的效果**未度量** —— 需要 provider key。
4. **`ChatService` 仍未按 workspace 过滤**：`ChatRequest` 有 `workspace_id`，但 `_retrieve` 没传；
   当前只有 `default` 一个工作区，故不在本批范围。要做的话适配器已经就绪。
5. **工具还没有被 Agent 真正调用**：本批只到"工具能接生产、能被装配"，
   自主 tool calling 循环属于阶段 2 的下一块。
