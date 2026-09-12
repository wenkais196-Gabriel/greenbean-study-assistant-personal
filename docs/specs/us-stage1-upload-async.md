# US · 阶段 1 收尾 ①：上传异步化 + 摄取进度反馈

> **状态：已实现（2026-09-12）**
> 依据：[`us-stage1-ingest.md`](us-stage1-ingest.md) §5「未做 1」、`planning/12` §3.5「解析进度反馈」
> 验收：上传大文档**立即**拿到受理回执，客户端能持续看到解析 / 嵌入 / 落库的真实进度

---

## 1. 这一批补齐的空白

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/api/document_controller.py` | `POST /upload` **同步**跑完整个摄取（290 页 ≈ 100 s，客户端干等） | 校验后立即返回 **202 + job_id**；新增 `GET /documents/jobs/{id}` 轮询 |
| `app/rag/vector_index_builder.py` | 一次性 `embed_texts(全部 chunk)`：112 s 内**没有任何观测点** | 拆成 `embed_chunks`（分批 + `on_progress(processed, total)`）与 `write_vectors`；`build_for_chunks` 保留为两者组合 |
| `app/services/document_ingest_service.py` | 只返回最终结果，中期无信号 | 新增可选 `on_progress(stage, ratio)` 阶段回调；流水线重排为「解析 → 切块 → **嵌入（事务外）** → 落库（单事务）」 |
| `app/db/init_db.py` / `models.py` | 无任务状态载体 | 新增 `ingest_jobs` 表（**落库**，重启后仍可查） |
| `app/services/ingest_job_service.py` | 不存在 | 新增：受理 → 线程池投递 → 阶段进度写库 → 终态 |
| `src/lib/upload.ts` + `FileManager.tsx` | `apiClient.ts` 是空占位、上传只改本地状态 | 真实上传 + 轮询，展示阶段文案与百分比 |

## 2. Acceptance Criteria

- **AC1**：`POST /api/documents/upload` 在摄取完成**之前**返回 **202**，响应体含 `data.job_id`；响应耗时与文档页数无关。
- **AC2**：`GET /api/documents/jobs/{job_id}` 返回 `status` ∈ `queued | running | succeeded | failed`、
  `stage` ∈ `parsing | embedding | persisting`（未开始/已结束时为 `null`）、`progress`（0~1）、`filename`、`error`。
- **AC3**：摄取成功后 job 为 `succeeded`，`progress == 1.0`，`data.result` 携带**可序列化的摄取摘要**
  （`filename` / `total_pages` / `status` / `page_index_preview` / `document_id` / `document_units_count` /
  `chunks_created` / `elapsed_seconds`），且数据立即可被 `Retriever` 召回。
- **AC4**：后台摄取抛异常时 job 为 `failed` + 可读 `error`；**上传请求本身仍是 202**（错误不再以 500 出现在上传响应里）。
- **AC5**：未知 `job_id` → **404**。
- **AC6**：`progress` **单调不减**；`succeeded` / `failed` 是终态，不再变回 `running`。
- **AC7**：`embedding` 阶段按**已处理片段数**推进：`VectorIndexBuilder.embed_chunks` 每完成一批就回调一次
  （408 片段、默认批 16 → 至少 26 次）。
- **AC8**：分批嵌入与整批嵌入**结果一致**（同一文本得到同一向量），分批只是加观测点，不改语义。
- **AC9**：既有同步校验行为不变：空文件名 → 422、不支持的扩展名 / 空内容 → 400，且**不创建 job**。
- **AC10**：前端上传后展示阶段文案 + 百分比；成功后文件状态为 `parsed`；失败展示错误原因且**不清空**条目。
- **AC11**：`ingest_jobs` 表在**旧库**（已存在、无该表）上重新初始化后被补建，既有表与 vec0 维度不受影响。

## 3. 实现要点

### 3.1 为什么落库而不是内存

进程内字典最简单，但**重启即丢**：用户刷新后查 `job_id` 会得到 404，而"我刚上传的东西去哪了"
正是这个功能要消除的不确定感。落库换来"状态可查、可追溯"，代价是一张纯新增的表（见 §4）。
生产侧无迁移负担：`data/` 无存量库，且 `_create_schema` 是幂等的 `CREATE TABLE IF NOT EXISTS`。

### 3.2 进度语义，以及一个必须记下来的坑：SQLite 写锁

阶段权重（整体 `progress`）：`parsing 0.00 → 0.10`、`embedding 0.10 → 0.95`、`persisting 0.95 → 1.00`。
区间按**流水线的真实顺序**排（解析 → 嵌入 → 落库），进度因此天然单调；
嵌入占 85% 的权重，因为它就是耗时的那一段（e5-large 实测约 200 ms/片段）。

**嵌入必须在任何写库之前完成 —— 这是正确性问题，不是风格问题。**
本批第一次跑集成测试时，所有上传任务都失败了：

```
AssertionError: OperationalError: database is locked
[SQL: UPDATE ingest_jobs SET stage=?, progress=?, updated_at=? WHERE ingest_jobs.id = ?]
```

根因：进度回调原本发生在 `_persist` 事务**内部**，而 SQLite 同一时刻只允许一个写者 ——
落库事务只要写下去（`session.flush()` 那一刻就拿到了写锁），进度写库（另一个连接）就必然被拒。
**加 `busy_timeout` 治不了**：持锁的正是同一个线程，等多久都不会自己释放。

修法是把流水线从"落库 → 切块 → 嵌入"改成"**切块 → 嵌入 → 落库**"，
并把 `VectorIndexBuilder` 拆成两步：

| 方法 | 做什么 | 碰数据库 |
|---|---|---|
| `embed_chunks(chunks, on_progress=...)` | 分批嵌入，纯计算 | ❌ |
| `write_vectors(repository, chunks, vectors)` | 双写权威表 + vec0 索引 | ✅ |
| `build_for_chunks(...)` | 上面两步的组合（保持既有调用方式） | ✅ |

于是最耗时的 112 s 落在**无锁的事务之外**（进度写得进去），而落库仍是**单事务**
（`us-stage1-ingest.md` AC1 的原子性没有被牺牲）。双写顺序与从前一致（先权威、后索引）。

**回调是尽力而为，不是事务边界**：进度写库与摄取本身不在同一事务 ——
否则进度只有在提交那一刻才可见，等于没有进度。
摄取失败 → job 置 `failed`；进度停留在失败前的阶段，如实反映"走到哪一步炸的"。

> 顺带一个测出来的边界：**没有回调时不做分批**（没有观测者就没有分批的必要），
> 直接走 `EmbeddingService.embed_texts` 的批量接口 —— 两条路径产出同样的向量（有测试锁定）。

### 3.3 执行模型

- `IngestJobService`：`submit()` 建 job（`queued`）→ 投递线程池 → 返回；`run()` 在 worker 里同步执行。
- 默认 `ThreadPoolExecutor(max_workers=2)`：嵌入是 CPU 密集，再多的 worker 只会互相抢核。
- controller 侧只做 HTTP：校验入参、映射错误码；建 job 与轮询读库都是同步 DB 操作，走 `run_in_threadpool`。
- **可注入 executor**：测试注入同步/受控 executor，不依赖 sleep 与竞态。
- `run()` **不向外抛异常**：线程池 worker 里没人接得住，错误必须落到 job 上由客户端轮询看到。

### 3.4 组件职责

```
document_controller    ← HTTP：校验、202、404
   └─ IngestJobService ← job 生命周期 + 线程池投递 + 进度写库（阶段权重折算在这里）
        └─ DocumentIngestService ← 解析 → 切块 → 嵌入（事务外）→ 落库（单事务）
             └─ VectorIndexBuilder ← embed_chunks（分批 + 回调） / write_vectors
```

## 4. Schema Change Justification

- **User Story requirement**：上传改异步后，"这次上传到哪一步了"必须有一个**请求之外**可查询、
  且**进程重启后仍可查**的状态载体（AC1/AC2/AC5）。
- **Migration required**：**无独立迁移脚本**。本仓库 schema 由 `app/db/init_db._create_schema` 的
  `CREATE TABLE IF NOT EXISTS` 幂等创建；新增表对旧库是"下次启动自动补齐"。
- **Backward compatibility**：**纯新增**。不改既有列、不改 vec0 维度、不动 `app_metadata.embedding_dimension`；
  旧库可直接沿用，无需重建索引。
- **Data migration needed**：**无**。旧数据里不存在"上传任务"这个概念，历史文档不需要回溯生成 job 行。
- **Tests covering migration**：`tests/integration/persistence/test_database_initialization.py`
  新增两个用例：新库建表；**旧库（先 DROP `ingest_jobs`）重新初始化后表被补建且既有数据仍在**（AC11）。

```sql
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT,
    progress REAL NOT NULL DEFAULT 0,
    error TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## 5. API Contract Change

```
Endpoint:        POST /api/documents/upload
Request:         不变（multipart/form-data，字段名 file）
Response:        200 {code:200, message:"文件上传并解析成功", data:{document_record, document_units, ...}}
              →  202 {code:202, message:"文件已受理，正在解析", data:{job_id, filename, status, ...}}
Error format:    400（不支持格式 / 空内容）/ 422（空文件名）**不变**
                 — 且这些错误在**同步阶段**返回，不会创建 job
Backward compat: **不向后兼容**。同步语义被异步取代：调用方必须改为轮询。
                 不留 `?sync=true` 双路径 —— 单人 fork + demo 优先，双路径会多养一份测试与一条长期不走的代码。

Endpoint:        GET /api/documents/jobs/{job_id}   （新增）
Response:        200 {code:200, message:"ok", data:{...}}
                 404 未知 job_id
job 结构:        {job_id, filename, status, stage, progress, error, result, created_at, updated_at}
                 （受理与轮询返回**同一个形状**，前端只用一套解析逻辑）
Frontend impact: src/lib/upload.ts（新增：协议封装 + 轮询）+ FileManager.tsx 改为真实上传 + 进度条
Backend impact:  document_controller（202 + 新端点）+ IngestJobService（新增）+ 摄取流水线重排
Tests added:     tests/unit/services/test_ingest_job_service.py          （job 生命周期 / 权重 / 夹取 / 未知任务）
                 tests/integration/api/test_document_upload_async.py     （202 不等摄取 / 轮询到可检索 / 失败 / 404 / 校验不留 job）
                 tests/integration/api/test_document_controller.py       （改写：受理契约 + 三种异常映射）
                 tests/unit/rag/test_vector_index_builder.py              （分批回调 / 空列表 / 分批不改语义）
                 tests/unit/services/test_document_ingest_service.py      （阶段顺序 / 无回调路径 / 0 页文档）
                 tests/integration/persistence/test_database_initialization.py（补表 / 旧库）
                 src/lib/upload.test.ts + FileManager.test.tsx            （协议 / 失败路径 / 进度 UI）
```

> **`result` 与同步响应不同构**是**有意的**：job 存在 DB 里，必须可 JSON 序列化，
> 不能塞 `DocumentRecord` / `DocumentUnit` 实例。摘要字段名沿用同步响应的命名，
> 但把实体换成 `document_id` 与计数。

## 6. 验证

| 命令 | 结果 |
|---|---|
| `pytest --cov=app --cov-config=tests/.coveragerc` | **386 passed，覆盖率 100.00%** |
| `npx vitest run` | **246 passed**（11 个测试文件） |

**未跑**：真 `e5-large` 模型下的端到端实测（本地与 CI 一律用假嵌入模型，避免下载 2.2 GB）。
"290 页 ≈ 100 s"的推算来自 `us-stage1-ingest.md` §4 的实测，不在本批重新测量。

## 7. 未做（留给后续）

1. **取消 / 重试**：job 一旦投递不能取消，失败后要重新上传。
2. **多进程一致性**：`ThreadPoolExecutor` 是进程内的，多 worker 部署下 job 会在"接收请求的进程"里执行；
   单机 demo 够用，横向扩展需要换成外部队列。
3. **进度落库频率**：按**批次**写库（408 片段 / 批 16 → 26 次 UPDATE）；更大语料应改为节流写入。
4. **原始文件落盘**到 `data/uploads/`（`us-stage1-ingest.md` §5-3 的既有待办，本批未做）。
5. **前端文件列表的数据源**：仍是组件内 mock，未接 `GET /documents`（后端也还没有列表端点）。
6. **会话/消息持久化**与**结构化 trace**：属阶段 2（见 `us-stage1-chat.md` §5）。
