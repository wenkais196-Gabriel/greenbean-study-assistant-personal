# US · 阶段 1 第五批：摄取闭环（落库 → 切块 → 向量化）

> **状态：已实现（2026-09-12）**
> 依据：[`parser-db-integration-spec.md`](parser-db-integration-spec.md) §7「安全摄入流水线」、`planning/12` §4
> 验收（阶段 1 总目标）：`curl` 上传真实 PDF → 五张表有数据 → `Retriever` **立刻**能召回这些片段

---

## 1. 这一批补齐的空白

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/services/document_ingest_service.py` | 只解析：`save()`、`ChunkService`、`EmbeddingService` **全是注释** | 注入 `session_factory` 后完整摄取：落库 → 切块 → 向量化（**同一事务**） |
| `app/db/runtime.py` | **不存在**（生产 DB 没有统一装配入口） | 新增：按 settings 建库 + engine + session_factory（懒加载单例） |
| `app/api/document_controller.py` | 直接调用同步 service（会阻塞事件循环） | 注入会话工厂 + `run_in_threadpool` |

## 2. Acceptance Criteria

- **AC1**：注入 `session_factory` 时，一次 `ingest_document` 在**同一事务**写入
  `document_records` / `document_units` / `chunks` / `embedding_vectors` / `embedding_index`，五者数量自洽。
- **AC2**：写入顺序满足外键约束：文档 → 单元 → 片段 → 向量（中间显式 `flush`）。
- **AC3**：摄取返回之后，`Retriever` **立刻**能召回刚入库的片段。
- **AC4**：**不注入** `session_factory` 时保持「只解析」：不写库、不加载模型（既有 14 处无参调用不受影响）。
- **AC5**：`embedding_model` 写进 `embedding_vectors` 供追溯（与 `parser_name` / `chunker_name` 同一套思路）。
- **AC6**：上传接口**不阻塞事件循环**：耗时操作放 `run_in_threadpool`。
- **AC7**：返回可见的观测字段：`chunks_created` 与 `elapsed_seconds`（便于后续做进度与性能基线）。

## 3. 实现要点

- **维度必须与建库时的 vec0 维度一致**：`initialize_database` 在不一致时明确报错（换模型须重建索引）。
- **嵌入服务可注入**：测试注入假模型，**绝不触发模型下载**（沿用项目 Rule 3）。
- `runtime.lazy_session_factory()`：让依赖注入"构造 service"这一步不产生建库副作用。
- 事务边界：一次上传 = 一次 commit；中途失败不留半份数据（外键 + 单事务保证）。

## 4. 实测（本机，2026-09-12）

| 场景 | 结果 |
|---|---|
| 2 页 PDF 经 **HTTP 上传**（真 e5 嵌入） | HTTP 200；`chunks_created=7`；五表各就位（1 / 2 / 7 / 7 / 7）；检索返回 top-3 |
| 同规模连续 3 次上传（**稳态**） | **3.31 / 3.45 / 3.35 s** |
| 首次上传（模型需从磁盘冷读 2.2 GB） | ~29.6 s（一次性冷启动） |
| 290 页资料（408 片段） | ~100 s 量级（与 [`retrieval-diagnosis.md`](../retrieval-diagnosis.md) §3.7 的 112 s 一致） |

## 5. 未做（留给后续）

1. **异步 + 进度反馈**：目前上传是同步请求，大文档会让客户端等 1~2 分钟 —— demo 上必须给进度，否则像卡死。
2. `main.py` 的 **CORS** 与 chat / analysis / provider 路由注册（属链路走查里的"开口"）。
3. **原始文件落盘**到 `data/uploads/`（现在只把字节流交给解析器，未持久化原件）。
4. **重复上传去重**（`file_hash` 已透传但未使用）。
