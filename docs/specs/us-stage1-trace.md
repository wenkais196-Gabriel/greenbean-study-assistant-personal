# US · 阶段 1 收尾 ④：结构化 trace（可观测性）

> **状态：已实现（2026-09-12）**
> 依据：`planning/12` §2.3「结构化 trace（字段对齐 `gen_ai.*`）」、`planning/11` §6「可观测性」
> 定位：**阶段 2（Agent + MCP）的前置** —— 没有 trace，多步编排出了问题只能靠 print 猜

---

## 1. 为什么这一批值钱

项目已有一条能跑的链路（上传 → 检索 → 带来源回答），但它的执行信息**散在 print 里**：
路由走了哪条、召回了多少条、上下文多大、每次 LLM 调用花了多久、用了多少 token —— 全都拿不到。

这一批把这些变成**结构化记录**，直接支撑三件事：

1. **阶段 2 的调试点**：tool calling / 多步编排一旦出问题，要能看见"哪一步、什么输入、什么输出"；
2. **性能与成本基线**（收尾 ②）：TTFT / token 成本 / 各段耗时都能从 trace 里聚合出来，而不是重新埋点；
3. **"最小可讲版本"的第 4 条**（`planning/12` §2.4）：**能被观测、能被量化** —— 前三条（契约 / 测试 / 失败路径）已经有了。

## 2. Acceptance Criteria

- **AC1**：新增 `agent_traces` 表，一条记录 = 一个 **span**（`trace_id` / `parent_id` / `span_name` /
  `status` / `duration_ms` / `attributes` / `error` / `created_at`）。
- **AC2**：一次提问的所有 span 共享同一个 `trace_id`，且该 `trace_id` 由 `POST /api/chat` 的响应带回
  （`ChatResponse.trace_id`），调用方能按 ID 取回整条链路。
- **AC3**：**LLM 调用**记录 `gen_ai.*` 字段：`gen_ai.operation.name`、`gen_ai.system`、
  `gen_ai.request.model`、`gen_ai.request.temperature`、`gen_ai.response.model`、
  `gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`、`gen_ai.response.finish_reasons`。
- **AC4**：**检索与上下文**记录 `retrieval.search`（`greenbean.retrieval.top_k` / `.hits`）与
  `context.build`（`greenbean.context.chars` / `.items` / `.dropped`）。
- **AC5**：**上传摄取**记录 `ingest.document`（`greenbean.ingest.pages` / `.chunks_created` / `.job_id`）
  与三个阶段 span：`ingest.parsing` / `ingest.embedding` / `ingest.persisting`。
- **AC6**：**失败必须留痕**：任何 span 抛异常时记为 `status=error` + `error` 文案 + 耗时，**且不改变原行为**
  （trace 是观测层，不能把成功变失败、也不能吞掉异常）。
- **AC7**：**trace 落库不得与摄取事务争写锁**：摄取路径的 span 一律在数据库事务**之外**写入
  （SQLite 单写者约束，教训见 `us-stage1-upload-async.md` §3.2）。
- **AC8**：`GET /api/traces/{trace_id}` 返回该 trace 的全部 span（按 `created_at` 升序）；未知 ID → 404。
- **AC9**：**采样开关**：`settings.TRACE_ENABLED`（默认 `True`）关闭时**不写任何 trace**，
  且不加载 trace 相关组件；关闭状态下链路行为与从前完全一致。
- **AC10**：`ChatResult` 携带 token 用量与模型名（可选字段，默认 `None`），
  既有只传 `content` 的构造方式**不受影响**。

## 3. 设计

### 3.1 span 模型

一条 `agent_traces` 行 = 一个 span。刻意**不做**树形重建：`parent_id` 够用，
真正的树形展示留给阶段 3（前端 trace 面板）。

```
一次提问（trace_id = T）
├─ agent.route            gen_ai.* + greenbean.route / .degraded
├─ retrieval.search       greenbean.retrieval.top_k / .hits
├─ context.build          greenbean.context.chars / .items / .dropped
└─ gen_ai.chat            gen_ai.* （usage / model / finish_reason）

一次上传（trace_id = U）
└─ ingest.document        greenbean.ingest.pages / .chunks_created / .job_id
   ├─ ingest.parsing
   ├─ ingest.embedding
   └─ ingest.persisting
```

### 3.2 字段口径：对齐 OTel，但不引依赖

字段名直接采用 OTel GenAI semconv 的 `gen_ai.*`（**为将来接 OTel 留路**），
本项目特有的信息加 `greenbean.*` 前缀（不污染标准命名空间）。

**不引入 `opentelemetry-*` 依赖**：本地单机、单进程、没有 collector 接收，
引依赖只换来一个更重的启动路径。等真的有 collector 时，这张表就是天然的 exporter 数据源。

### 3.3 trace_id 传播

用 `contextvars`（`app/utils/trace_context.py`）：

- `POST /api/chat` 与 `IngestJobService.run()` 在入口生成并绑定 `trace_id`；
- `TraceRecorder` 与 `traced_chat_completion` 从 contextvar 读取，不需要层层传参；
- `asyncio.to_thread` / 线程池会复制当前 context，所以检索线程里也能拿到同一个 ID。

### 3.4 ⚠️ 与 SQLite 写锁的关系（必须遵守）

`us-stage1-upload-async.md` §3.2 的教训在这里**同样成立**：SQLite 只允许一个写者。
因此本批定了一条硬约束：

> **摄取路径的 span 只在数据库事务之外写**（解析后、嵌入后、落库后各写一次）。

检索路径天然满足（读事务在 `with` 块内结束，span 在块外写）。
`TraceRecorder.record_span` 因此**不接收 session**、自己开会话 —— 这样"在事务内误用"会立刻炸成
`database is locked`，而不是留下难以察觉的部分提交。

### 3.5 失败与采样

- **计时**：`span(...)` 用 `time.perf_counter()` 包住被观测的代码块；异常**照原样重抛**，只额外落一条 `error` span。
- **采样**：`settings.TRACE_ENABLED` 为 `False` 时，`TraceRecorder.record_span` 直接返回 `None` 且不碰数据库；
  controller 的依赖注入在关闭时返回 `None`，agent / service 收到 `None` 就走无 trace 路径。
- **成本**：一次提问 4 条 span、一次上传 4 条 span；每条一次 commit —— 与摄取本身（1~2 分钟）相比可忽略。

## 4. Schema Change Justification

- **User Story requirement**：AC1/AC2/AC8 —— trace 必须能被**按 `trace_id` 查回**、能聚合、重启不丢。
- **Migration required**：**无独立迁移脚本**。沿用 `app/db/init_db._create_schema` 的
  幂等 `CREATE TABLE IF NOT EXISTS`；索引同样 `IF NOT EXISTS`。
- **Backward compatibility**：**纯新增**表与索引；不改既有列、不动 vec0 维度。
- **Data migration needed**：**无**。旧数据没有 trace 这个概念。
- **Tests covering migration**：`tests/integration/persistence/test_database_initialization.py`
  追加"旧库重新初始化后 `agent_traces` 被补建，且既有数据仍在"（与 `ingest_jobs` 同一套用例写法）。

```sql
CREATE TABLE IF NOT EXISTS agent_traces (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_id TEXT,
    span_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    attributes_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_traces_trace_id ON agent_traces (trace_id);
```

## 5. API Contract Change

```
Endpoint:        POST /api/chat
Response:        + trace_id  （**新增可选字段**，向后兼容：调用方不用它也没问题）
                 用途：按 ID 取回整条链路，供评测脚本与将来的 trace 面板关联

Endpoint:        GET /api/traces/{trace_id}   （新增）
Response:        200 {code:200, message:"ok", data:{trace_id, spans:[{span_name, status, duration_ms,
                     attributes, error, created_at, parent_id}...]}}
                 404 未知 trace_id（一条 span 都没有）
Backend impact:  chat/ingest 两条链路接 trace；新增 TraceRecorder / TraceRepository / trace_context
Frontend impact: 无（本批不做前端 trace 面板，见 §7）
Tests added:     tests/unit/utils/test_trace_context.py
                 tests/unit/services/test_trace_recorder.py
                 tests/unit/services/test_llm_trace.py
                 tests/unit/providers/test_openai_compat_provider.py（+usage 映射）
                 tests/integration/api/test_trace_flow.py
                 tests/integration/document/test_ingest_trace.py
                 tests/unit/api/test_trace_controller.py
```

## 6. 验证

| 命令 | 结果 |
|---|---|
| `pytest --cov=app --cov-config=tests/.coveragerc` | **425 passed，覆盖率 100.00%** |
| `npx vitest run` | **246 passed**（前端无改动，无回归） |

**实测发现（值得记下来）**：一次提问落 **5** 条 span，不是设计时画的 4 条 ——
路由那次 LLM 调用本身就是一条 `gen_ai.chat`：

```
gen_ai.chat      ← 路由调用（purpose=router）
agent.route      ← 路由决策：greenbean.route / .degraded
retrieval.search ← greenbean.retrieval.top_k / .hits
context.build    ← greenbean.context.chars / .items / .dropped
gen_ai.chat      ← 回答调用（purpose=answer，带 usage / model / finish_reasons）
```

顺序由"span 在操作**结束时**落库"决定：`agent.route` 要等 LLM 返回才知道 route 值，
所以它排在路由那次 `gen_ai.chat` **之后**。测试按真实顺序锁定，没有为了好看去改实现。

## 7. 未做（留给后续）

1. **前端 trace 面板**：本批只做"可查"，展示留给阶段 3（`planning/12` §3.5 的体验项）。
2. **span 的父子层次**：`parent_id` 字段已就位并有测试，但本批**没有建立真实的父子关系** ——
   摄取与问答的 span 都是平铺的。做前端树形展示时才需要它（那时才知道父 span 的 ID 该在何时生成）。
3. **OTel exporter**：字段已经对齐，接 collector 时补一个 exporter 即可。
4. **trace 清理 / 保留策略**：`agent_traces` 会无限增长；demo 阶段无所谓，长期需要按时间清理。
5. **采样率**：目前是全量（一个开关）；高流量下应改为按比例采样。
6. **prompt / completion 正文**：当前只记规模（`greenbean.context.chars`）与 token 数，**不落正文** ——
   避免把学生资料与问题原文写进日志表（隐私优先）；真要调试时需显式打开。
