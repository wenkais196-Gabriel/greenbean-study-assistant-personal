# US · 阶段 1 · 问答闭环（开口）：提问 → 检索 → 带来源的回答

> **状态：已实现（2026-09-12）**
> 验收：`POST /api/chat` 的回答带 `source_context`，且**上下文确实来自已入库的资料**（不是 mock）
> 前置：[`us-stage1-ingest.md`](us-stage1-ingest.md)（数据能进库）、[`retrieval-diagnosis.md`](../retrieval-diagnosis.md)（检索质量）

---

## 1. 这一批补齐的空白

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/services/chat_service.py` | **1 行占位** | 编排：路由 → 检索 → 上下文预算 → 生成；同步 IO 进线程池 |
| `app/api/chat_controller.py` | **1 行占位** | `POST /api/chat`，含 400 / 503 错误映射 |
| `app/agents/chat_agent.py` | 上下文是**硬编码 mock**；路由结果只被 `print` | 上下文由调用方注入；新增 `route_question()`，路由**真的决定召回深度** |
| `app/main.py` | 只注册 document，**无 CORS** | 注册 chat 路由 + CORS（名单来自 settings） |
| `app/config/settings.py` | — | `CORS_ALLOWED_ORIGINS`（vite 5173 / Tauri） |

## 2. Acceptance Criteria

- **AC1**：`POST /api/chat` 收到 `{session_id, query, history?}` → 返回 `{session_id, answer, source_context}`。
- **AC2**：`source_context` 与上下文块里的 `[来源 N]` **一一对应**（含 `chunk_id` / `document_id` /
  `page_number` / `heading_path` / `distance`），供前端做引用回溯。
- **AC3**：检索到的上下文**确实拼进了**发给模型的 prompt（不是只查不用）。
- **AC4**：资料为空时仍返回回答（`source_context == []`），不报错。
- **AC5**：provider 未配置 → **503** + 可读提示（而不是 500 堆栈）。
- **AC6**：`query` 为空白 → **400**。
- **AC7**：路由决策**影响行为**：`COMPREHENSIVE` 或 `use_extended_context=True` → 双倍召回候选。
- **AC8**：同步的检索与 query 嵌入走 `asyncio.to_thread`，不阻塞事件循环。

## 3. 分层（沿用既有约定）

```
chat_controller   ← HTTP：校验入参、映射错误码
   └─ ChatService ← 同步基础设施 + 编排：Retriever → ContextBuilder(预算) → render
        └─ ChatAgent ← 只做 路由 + LLM；**不碰持久化**
```

`ChatAgent.route_question()` 暴露出来，是为了让 service 在**检索之前**就能拿到意图，
同时把同一个决策回传给 agent（`route=`），避免重复调用模型。

## 4. 实测（2026-09-12）

| 场景 | 结果 |
|---|---|
| 上传 2 页 PDF 后 `POST /api/chat`（假 provider + 假嵌入） | 200；回答带 `source_context`（`chunk_id` / 第 N 页） |
| 上下文注入 | 发给模型的消息里含 `### Course Context` 与 `[来源 1]` |
| 空库提问 | 200；`source_context == []` |
| provider 未配置 | **503** + "尚未配置可用的模型 provider" |
| 空白 query | **400** |

> 上面的端到端用**假 provider / 假嵌入模型**（CI 不下载模型、不调外部 API）。
> 真实 LLM 下的回答质量与延迟（TTFT / token 成本）**尚未度量** —— 需要 provider key。

## 5. 未做（待办）

1. **`STRUCTURE` 分支**：章节 / 页码级检索还没实现，结构类问题目前也走语义检索；
2. **会话与消息持久化**：`chat_sessions` / `chat_messages` 表已建好但还没写入（历史仍由前端传）；
3. **结构化 trace**：route、检索耗时、上下文规模目前只在日志里，没有结构化字段；
4. **provider 路由注册**：`provider_controller` 是类风格（没有 `APIRouter`），尚未接入 `main.py`；
5. **引用后校验**：模型输出里的 `[来源 N]` 还没有做存在性校验（防幻觉引用）。
