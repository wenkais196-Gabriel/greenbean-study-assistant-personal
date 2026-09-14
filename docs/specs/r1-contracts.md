# R1（v0.2.0）契约与决策定稿

> 建立：2026-09-14。**本文件是 R1 全部测试场景与实现的单一事实源**：任何 test issue、实现 PR
> 与本文件冲突时，以本文件为准（改本文件要先改这里，再改 issue）。
>
> 为什么需要它：R1 的 27 条测试场景里，有 8 处契约在写场景时**还不存在**（接口路径、状态码、
> 流式协议、TTFT 口径、重试语义、判重策略…）。这些不定稿，"先写失败测试"就无从落笔 ——
> 测试会各自发明协议，实现再各自发明第二套，缝隙里必然出 bug（本仓库已因 `api_mode`
> 契约两端不一致栽过一次：两边测试都绿，界面「保存配置」必然 422）。
>
> 标注约定：**`[定稿]`** = 已可直接照着写测试。**本文档内所有契约均已定稿**（2026-09-14）；
> 若后续出现新歧义，按 `[NEEDS CLARIFICATION]` 标注，且一次最多 3 个（对齐 Spec Kit 的 `/clarify` 做法）。

## 0. 事实基线（本次查证，2026-09-14）

写契约之前先把"现状到底有什么"钉住，避免按文件名假设已完成：

| 事实 | 证据 |
|---|---|
| 现有 HTTP 面只有 4 组 | `app/api/`：`/chat`（`POST ""`、`GET /sessions/{id}/messages`）、`/documents`（`POST /upload`、`GET /jobs/{id}`、`GET ""`、`GET /{id}/units`）、`/providers`（CRUD + activate）、`/traces/{id}` |
| **没有** sessions 列表 / 删除接口 | `chat_controller.py` 只有上面两条路由 |
| **没有** workspace 的任何接口 | `app/api/` 下无 `workspace_controller.py` |
| **没有** `workspaces` 表 | `db/init_db.py` 的 `_create_schema` 里无该表 |
| **没有** workspace 仓储 | `app/repositories/` 下无 `workspace_repository.py` |
| `Workspace` 实体与 5 类默认类型**已存在** | `app/entities/workspace.py`、`app/enums/workspace_defaults.py`（`course/admin/internship/language/other`） |
| **`file_hash` 从未被计算或写入** | 全仓无 `hashlib` / `sha256` / `md5`；`document_ingest_service.ingest_document(..., file_hash: str \| None = None)` 一路默认 `None`，`document_controller.upload_document` 也未传 |
| 上传落库 `workspace_id = ""`、会话落库 `= "default"` | `ingest_job_service.submit` 默认 `workspace_id=""`；`chat_session_service.DEFAULT_WORKSPACE_ID = "default"` |
| 检索已支持 workspace 过滤（pre-filter 子查询） | `repositories/embedding_repository.py` 的 `workspace_id` 参数；`app/tools/adapters.py` 的 `ProductionChunkSearcher.search` |
| 响应信封与错误口径 | 成功：`{"code": 200, "message": "ok", "data": ...}`（`provider_controller` 用裸 `response_model`）；错误：HTTP 状态码 + `detail` |

---

## C1 · 流式协议 `[定稿]`

- **协议：SSE 帧格式**，`Content-Type: text/event-stream; charset=utf-8`，承载在 HTTP chunked 之上。
  依据：SSE 是 LLM 流式的事实标准（OpenAI 定义了 `data: {...}\n\n` + `data: [DONE]`，Anthropic /
  Google / Mistral / Cohere 全部沿用）；SSE 与 chunked 不是竞品 —— chunked 是传输层，SSE 是其上的应用层帧。
- **端点：`POST /api/chat/stream`**，请求体与 `POST /api/chat` 的 `ChatRequest` **逐字一致**
  （同一份 schema，避免两套协议）。
- **事件类型**（`event:` 字段）：`token`（增量正文）、`sources`（来源条目，在首个 token 前后各发一次）、
  `tool_call`（工具循环的可观察点）、`error`、`done`。每条数据为 JSON，末尾发 `data: [DONE]`。
- **错误必须进流内**：流一旦开始，HTTP 状态码已冻结 → 中途失败发 `event: error` + `event: done`。
  **但"请求还没开始流"的失败仍走状态码**：未配 provider → 503；`query` 为空 → 400。
- **响应头三条必带**：`Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Connection: keep-alive`。
  依据：最常见的"流式失效"不是协议选错，而是被中间层缓冲（Nginx 默认缓冲 4–16 KB）。
- **心跳**：空闲 15 s 发一行注释（`: ping\n\n`，**不能写成 `data: :ping`** —— 那会被当成数据事件）。
- **断连**：捕获 `asyncio.CancelledError` 并**重新抛出**（清理后 re-raise），或用 `request.is_disconnected()`；
  断连后**不落库**（沿用现有"回答成功才落库"口径）。
- **不引入 WebSocket**：只在需要流中取消 / 双向插入时才值得，R1 不需要。
- **实现方式（已拍板）**：原生 `StreamingResponse` + 手写 SSE 帧，**不引入 `sse-starlette`**。
  理由：单机本地、无反向代理，心跳与断连压力小，且本仓库规矩是"无理由不加依赖"。
  代价必须自己承担的部分：心跳、`X-Accel-Buffering`、`CancelledError` 清理 ——
  这三项正好是 `#26` 的断言对象，别省。

## C2 · TTFT 口径 `[定稿]`

- **定义**：请求发出 → 收到**第一个非空内容 token**（空 delta 必须忽略，否则数字无意义）。
- **记两个口径，不要混成一个数**：
  - `ttft_server`：服务端收到请求 → 发出第一个 `token` 事件（**可自动化断言**，无网络抖动）；
  - `ttft_client`：端到端（含网络与浏览器），**手工测量**，必须同时记录样本量与 P50/P95。
- **用分位数，不用均值**（均值被慢尾掩盖）。参考：RAIL 认为 <1 s 感觉自然、>1 s 开始流失注意力。
- **落点**：trace 属性（`greenbean.streaming.ttft_ms`）+ `docs/cost-and-latency.md` 的 TTFT 一列。
- **注意**：客户端测得的 TTFT 明显差于服务端时，先怀疑**缓冲层**，不是模型慢。
- R1 停止条件「首字 ≤ 1.5 s」按 **`ttft_server`** 判定（可控、可复现）；`ttft_client` 只作参考记录。

## C3 · 上传失败重试 `[定稿]`

- **端点：`POST /api/documents/jobs/{job_id}/retry`**。
- **语义：新建 job**（不改原 job 的状态），响应返回**新 job 的 payload**（与 `GET /jobs/{id}` 同形状）。
  - 原 job 保留作审计；新 job 建立之后，原 job 的字段不变。
  - `IngestJob` 增加两个字段（纯新增列，走 R1-3 的迁移）：`retried_from`（原 job id，可空）、
    `retry_count`（整数，默认 0）。
- **只允许终态失败重试**：`failed` → 允许；`queued` / `running` / `succeeded` → **409 Conflict**；
  不存在的 job → 404。
- **重试上限：3 次（已拍板）**。超过则 409 并说明"已达重试上限"。
  依据：毒药任务无限重试会持续占用 worker（`DEFAULT_MAX_WORKERS = 2`，被一个坏文件的死循环拖住就很痛）。
- **文件来源（本次细化时补上的缺口）**：`POST /api/documents/upload` 受理时把文件**落盘**到
  `data/uploads/{job_id}/{filename}`，并把路径写入 `document_records.file_path`；
  `retry` 一律**从磁盘读原文件**，因此重试请求**不需要请求体**，进程重启后也仍可重试。
  依据（现状事实）：`document_records.file_path` 与 `data/uploads/` 目录本就在设计中，但**两者都是空的**
  —— 文件只在内存里过一趟、用完即弃；不落盘的话"一键重试"在刷新页面后就做不到，达不到父 issue 的验收标准。
  ⚠️ 代价：用户课件会落盘（原先不落盘）。`data/uploads/*` 已由 `.gitignore` 忽略；
  **R1 不做磁盘 GC**，清理策略留 R2 —— 写进 `docs/upgrade.md` 的注意事项。
- **不引入 `Idempotency-Key`**：单机无重放风险，属过度设计（该 header 本身也只是 IETF 过期草稿，非 RFC）。
- 仍然遵守：**不在数据库事务内部去写别的表**（进度 / trace / 会话消息都算），否则必然 `database is locked`。

## C4 · 重复上传判重 `[定稿]`

- **指纹算法：SHA-256**，**流式分块计算**（保持内存恒定，不整文件读入）。
  依据：MD5 已不抗碰撞；流式哈希是文件去重的标准做法。
  ⚠️ 现状：`file_hash` **从未被写入**（见 §0），所以本项包含"第一次真正产生指纹"的工作量，
  不是"给已有指纹加个判断"。
- **计算位置**：`POST /api/documents/upload` 受理时算一次（与后续摄取解耦），并透传给
  `IngestJobService.submit(..., file_hash=...)` → `DocumentIngestService`。
- **策略：软跳过（已拍板）** —— 命中同 hash 且已有文档状态非 `failed` 时返回 **200** +
  `{"duplicate": true, "document_id": "<已有文档>"}`，**不创建新 job**；
  `?force=true` 时按正常流程重新上传（逃生舱）。
  依据：Zalando 风格指南要求「返回 200 就必须是同一个资源」—— 这里返回的正是已有 `document_id`，
  语义自洽；alkem-io（`reused=true`）、Atlan（`skipped:hash_match`）同款做法。
  被否掉的替代：409（GitLab / Fedora 同款）—— 语义更"一眼可解释"，但会让"用户重复拖同一份课件"
  这种无害操作变成报错。
- **作用域：全局**（内容身份跨 workspace 唯一）。选此是因为单机单用户；若将来要多用户再改成按 workspace。
- **不算重复的情况**：文件名相同但内容不同（hash 不同）→ 正常受理并新建文档。
- `failed` 的旧记录不得阻塞重新上传（否则失败过的文件永远传不上去）。

## C5 · 新增接口路径与状态码 `[定稿]`

沿用现有风格：成功走 `{"code": ..., "message": ..., "data": ...}` 信封（`/documents`、`/chat` 既如此），
`/providers` 是裸 `response_model`（历史差异，**新接口统一走信封**）；错误用 HTTP 状态码 + `detail`。

| 接口 | 方法 | 说明 | 错误 |
|---|---|---|---|
| `/api/chat/sessions` | GET | 会话列表，`?workspace_id=` 可选过滤，按 `updated_at` 倒序，**不含消息正文** | 500 |
| `/api/chat/sessions/{id}` | DELETE | 删除会话及其消息（级联） | 404 不存在 |
| `/api/chat/sessions/{id}/messages` | GET | 已有 | 404 |
| `/api/documents` | GET | 新增 `?workspace_id=` 可选过滤；不传 = 全部 | 500 |
| `/api/documents/jobs/{id}/retry` | POST | 见 C3 | 404 / 409 |
| `/api/workspaces` | GET / POST | 列表 / 新建 | 400(空名) / 409(重名) |
| `/api/workspaces/{id}` | GET | 详情（**不提供 DELETE**，见下） | 404 |
| `/api/quiz` | POST | 生成自测题（见 C7） | 400 / 404 / 503 |
| `/api/chat/stream` | POST | 见 C1 | 400 / 503 |

**R1 不做**：分页 / 重命名 / 搜索（父 issue 的停止条件已写死）；**工作区删除**——
"删掉一门课，它下面的文档与会话怎么办"属于成员 / 归档一类的语义，与父 issue 明写的
"不做成员 / 权限 / 重命名 / 归档"同族，留到 R2。R1 只提供创建工作区与切换。

## C6 · 工作区 `[定稿]`

- **新增 `workspaces` 表**（`id` / `name` / `description` / `type` / `created_at` / `updated_at`），
  遵循本仓库"纯新增 + `CREATE TABLE IF NOT EXISTS`"约定，并由 **R1-3 的迁移框架**承接（表结构变更的第一个真实迁移）。
- **新增 `workspace_repository.py` / `workspace_service.py` / `workspace_controller.py`**（分层与既有模块一致）。
- **默认工作区**：常量 `"default"` 同时存在于前端 `chatApi.ts` 与后端 `chat_session_service.py`。
  R1-2 后统一为**后端单一常量**，前端从响应里读或复用同一字面量；启动时**幂等确保 default 工作区存在**
  （与 `ProviderService.restore_active` 同类做法）。
- **归属判定**：上传时若未指定 workspace → 落 `"default"`（不再是 `""`）。
  ⚠️ 旧库中已有 `workspace_id = ''` 的历史文档：迁移时**改写成 `"default"`**（而不是丢弃），
  并把这一步写进 `docs/upgrade.md`。
- **收敛语义**：切到某 workspace → 文档列表 / 会话列表 / 检索范围三者同时收窄；空 workspace 返回空数组（不是 404）。

## C7 · quiz 接口 `[定稿]`

- `POST /api/quiz`，请求：`{workspace_id, document_id?, num_questions?}`；响应：`{items: [{question, options[], answer, explanation, term_fr?, term_zh?}]}`。
- 数量：默认取 `QuizGenerationTool.DEFAULT_QUIZ_COUNT`（3，R1 的验收要求是"生成 5–10 题并可作答"，
  因此**界面默认请求 5**，`num_questions <= 0` → 400）。
- **术语题必须带中文对照字段**（`term_zh` 非空），这是 R1 唯一差异化项的判据。
- 失败：目标 workspace 无可用资料 → 400（明确原因）；provider 未配置 → 503；
  模型返回非法 JSON → 400/502 且**不崩**（复用工具的 `success: false` 分支）。

## C8 · R1 门禁进入每条 DoD `[定稿]`

每条 test issue 的"完成"都包含：**测试先红后绿** + Python 覆盖率 **100%**（`tests/.coveragerc` 的 `fail_under`）
+ CI 四 job 绿 + 相关文档回填。另加两条 R1 专属防退化：

- L1 检索基线**不得劣于 v0.1.0**（合成语料 @5 / @10）；
- demo 与文档中**不得出现 `api_key` 与私人课件**（响应层已不返回 `api_key`，要加一条断言锁住）。

---

## 决策记录（2026-09-14 已拍板）

| 项 | 结论 | 依据 |
|---|---|---|
| C1 流式实现 | **原生 `StreamingResponse` + 手写 SSE 帧**，不引 `sse-starlette` | 单机本地、无反向代理，心跳与断连压力小；仓库规矩"无理由不加依赖" |
| C4 判重策略 | **软跳过**：200 + `duplicate: true` + 已有 `document_id`，`?force=true` 逃生舱 | 用户重复拖同一份课件是无害操作，不该变成报错；Zalando 口径自洽 |
| C3 重试上限 | **3 次** | 防毒药任务持续占用 worker（`DEFAULT_MAX_WORKERS = 2`） |

> 其余各处（接口路径、状态码、TTFT 双口径、判重作用域、迁移改写旧 `workspace_id`）均已定稿。
> 要改任何一条：**先改本文档，再改对应 test issue** —— 顺序反了就会重演"实现与测试各一套"。

## 与 test issue 的对应（追溯矩阵的种子）

| 契约 | 主要影响的 test issue |
|---|---|
| C1 流式 | #25 #26 #27 #28 |
| C2 TTFT | #28 |
| C3 重试 | #32 #33 #34 |
| C4 判重 | #35 #36 #37 |
| C5 接口面 | #11 #12 #18 #19 #22 #29 #32 |
| C6 工作区 | #22 #23 #24 + R1-2 全部（#11 #12 #13） |
| C7 quiz 契约 | #29 #30 #31 |
| C8 门禁 | 全部（写入每条 DoD） |
