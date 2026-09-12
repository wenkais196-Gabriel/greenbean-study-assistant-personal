# US · 阶段 1 第二批：让本地数据库真正支持向量存储与 KNN 检索

> **状态：待确认**（BDD/TDD Gate 1 产出）
> 依据：[`planning/06`](../../planning/06-代码现状全景.md) §4.3（债 1）、[`planning/08`](../../planning/08-技术选型决策记录.md) §2.1、上游 spec §5.1（P0 缺失）
> 流程：本文档 → **你确认** → Gate 2（先写测试，确认 Red）→ **你确认** → Gate 3（最小实现）

---

## 0. 为什么是这一批（它其实是个 bug fix）

**这不是新功能，是修一个已经坏掉的地基。** 实测事实：

| 现状 | 问题 |
|---|---|
| `init_db.py` 用 `connection.load_extension("sqlite_vec")` | 依赖 sqlite3 能在动态库搜索路径里找到名为 `sqlite_vec` 的共享库，**在 Windows + Python 3.12 上不成立** |
| `requirements.txt` 里**没有** `sqlite-vec` | 就算加载方式对了，包也没装 |
| 测试全绿 | 因为测试注入了**假 loader**（`connection.create_function("vec_version", ...)`），**真实初始化路径从未被真跑过** |
| `embedding_vectors.vector_json` 是 TEXT 列 | 检索只能把全部向量读进内存逐个算，没有索引 |

上游 spec §5.2 自己就写了要升级为 `sqlite_vec.load(connection)`；`US #19` 把"启动时必须加载 sqlite-vec"写成了验收标准，但**从没真正生效过**。

**已实测验证（2026-09-12）**：
```
sqlite_vec.load(conn)                                    → OK
select vec_version()                                     → v0.1.9
create virtual table embedding_index using
  vec0(chunk_id text primary key, embedding float[384])  → OK
insert + KNN (k=1)                                       → [('c1', 0.0)]
```

---

## 1. User Story

**Title:** 让本地数据库真正支持向量存储与 KNN 语义检索

**As a:** 使用这个助手复习法语课程资料的学生

**I want:** 系统启动时真正加载向量检索扩展，并建立一个能按**语义距离**快速召回的本地索引

**So that:** 我提问时系统能在本地快速找到最相关的资料片段，而不是把整个向量表读进内存逐个比较；且我的资料始终不出本机

---

## 2. Acceptance Criteria

- **AC1**：`initialize_database()` 在**真实环境**下（不注入假 loader）能成功加载 sqlite-vec，并返回非空的 `sqlite_vec_version`。
- **AC2**：初始化后数据库中存在 `embedding_index` 虚拟表，其向量维度等于传入的 `embedding_dimension`。
- **AC3**：可以把 `(chunk_id, vector)` 写入该索引。
- **AC4**：可以按距离返回 top-k 个最相近的 `chunk_id`，**按距离升序**排列。
- **AC5**：维度与索引不一致的向量被**拒绝写入**，并给出明确错误。
- **AC6**：对同一个 `chunk_id` 重复写入是**幂等**的（该 chunk 在索引中始终只有 1 行）。
- **AC7**：初始化**幂等**：重复调用不报错，且**不丢失已写入的向量**。
- **AC8**：`sqlite-vec` 加载失败时，仍抛 `SQLiteVecInitializationError`（保留 `US #19` 的既有失败语义）。

---

## 3. Business Rules

- **Rule 1**：向量维度统一来自 `config/settings.py` 的 `EMBEDDING_DIMENSION`（当前 384），由 `initialize_database(embedding_dimension=...)` 传入。
- **Rule 2**：加载方式统一为 **`sqlite_vec.load(connection)`**，替换当前的 `connection.load_extension("sqlite_vec")`。
- **Rule 3**：`embedding_vectors` 表保留为**权威记录**（向量 + `embedding_model` + 维度等元数据）；`embedding_index` 是它的**可检索副本**。见 §9-A3。
- **Rule 4**：vec0 表的维度在**建表时固定**，`sqlite-vec` 不支持就地改维度——**换 embedding 模型必须重建该表**。这一条必须写进文档与代码注释。
- **Rule 5**：索引写入与读取都是**仓库层**能力，`sqlite_vec` 的具体 API 不外泄到 service 层。

---

## 4. Edge Cases

- **E1**：`k` 大于索引中的记录数 → 返回全部记录，不报错。
- **E2**：索引为空时查询 → 返回空列表。
- **E3**：查询结果中 `chunk_id` 与距离一一对应，距离为 0 表示完全相同的向量。
- **E4**：同一批向量里存在重复 `chunk_id` → 按 AC6 幂等处理。

---

## 5. Failure Cases

- **F1**：扩展加载失败（`sqlite_vec` 包缺失 / 平台不支持）→ 抛 `SQLiteVecInitializationError`，且**不得**报告初始化成功。
- **F2**：写入维度不匹配的向量 → 抛明确的领域异常（`EmbeddingDimensionError`，已存在），不静默截断/补齐。
- **F3**：向不存在的 `chunk_id` 写索引 → 由既有的 `MissingChunkError` 语义处理（与 `EmbeddingRepository.save_for_chunk` 一致）。
- **F4**：查询不存在的 `chunk_id` → 返回空，不抛异常。

---

## 6. Dependencies / Integration Points

- **新依赖**：`sqlite-vec`（**必须写进 `requirements.txt` 并加上限**）。
- **依赖**：`config/settings.py`（维度）、既有的 `EmbeddingVectorModel` / `EmbeddingRepository`。
- **被依赖**：第三批的 `vector_index_builder`（把 Chunk 向量写进这个索引）、第四批的 `retriever`（在这里做 KNN）。
- **不依赖**：fastembed、网络、LLM（**这批完全不需要模型**，所以测试可以真跑而不必 mock）。

---

## 7. Affected Areas

- **Frontend:** 无
- **Backend:** `app/db/init_db.py`（加载方式 + 建表）、`app/repositories/embedding_repository.py`（或新增索引仓库）
- **Database:** **有 schema 变更**（新增 `embedding_index` 虚拟表）—— 见 §8
- **API Contract:** 无变更
- **Tauri / Desktop:** 无
- **Tests:** `tests/integration/persistence/`（真跑 sqlite-vec：初始化 / 写入 / KNN / 幂等 / 维度拒绝）

---

## 8. Schema Change Justification

```text
Schema Change Justification:
- User Story requirement: 需要真正的向量索引才能做 KNN 检索；
  当前 embedding_vectors.vector_json 是 TEXT 列，只能全量扫描后逐个计算。
- Migration required: 是 —— 新增虚拟表
    CREATE VIRTUAL TABLE IF NOT EXISTS embedding_index
    USING vec0(chunk_id text primary key, embedding float[N])
  （N 由 initialize_database(embedding_dimension=...) 决定；语法已实测通过）
- Backward compatibility: 兼容 —— embedding_vectors 表保持不变，继续作为权威记录；
  embedding_index 只是可检索副本。既有测试（注入假 loader 的那些）不受影响，
  因为它们显式传入自己的 loader。
- Data migration needed: 不需要 —— 索引可从 embedding_vectors 重建；
  且 CREATE VIRTUAL TABLE IF NOT EXISTS 保证重复启动安全。
- Tests covering migration: 初始化幂等性 + 重复初始化后已有向量仍可召回（AC7）。
```

> ⚠️ 注意：vec0 会创建若干**伴生表**（`embedding_index_info` / `_chunks` / `_rowids` / `_vector_chunks00`），
> 这是 sqlite-vec 的正常行为，不是副作用泄漏。文档里要写明，避免后来者困惑。

---

## 9. BDD Scenarios

```gherkin
Feature: 本地向量索引（sqlite-vec + vec0）

  Scenario: 初始化数据库时真正加载 sqlite-vec
    Given 一个可写的临时数据目录
    When 调用 initialize_database，且 embedding_dimension 为 384
    Then 返回结果的 persistence_ready 应该为 True
    And 返回结果的 sqlite_vec_version 应该是一个非空字符串

  Scenario: 初始化后存在向量索引表
    Given 一个已完成初始化的数据库
    When 查询数据库中名为 embedding_index 的表
    Then 该表应该存在
    And 向其中写入一个 384 维向量应该成功

  Scenario: 写入向量后可以按相似度召回
    Given 一个已完成初始化的数据库，且索引中已写入 3 个不同的向量
    When 用其中第 2 个向量查询 top-1
    Then 返回的结果应该恰好 1 条
    And 返回的 chunk_id 应该是第 2 个向量对应的 chunk
    And 返回的距离应该为 0

  Scenario: top-k 大于记录数时返回全部
    Given 索引中只有 2 个向量
    When 查询 top-5
    Then 应该返回 2 条结果

  Scenario: 空索引查询返回空结果
    Given 一个还没有写入任何向量的索引
    When 查询 top-5
    Then 应该返回空列表

  Scenario: 维度不匹配的向量被拒绝
    Given 一个向量维度为 384 的索引
    When 尝试写入一个 128 维的向量
    Then 应该抛出 EmbeddingDimensionError
    And 索引中不应该出现该条记录

  Scenario: 重复写入同一 chunk 是幂等的
    Given 索引中已存在 chunk_id 为 c1 的向量
    When 再次写入 c1 的另一个向量
    Then 索引中 chunk_id 为 c1 的记录应该仍然只有 1 条

  Scenario: 重复初始化不丢失已有向量
    Given 一个已写入向量的数据库
    When 再次调用 initialize_database（相同维度）
    Then 之前写入的向量仍然可以被召回

  Scenario: sqlite-vec 加载失败时初始化失败
    Given 一个总是抛出异常的扩展加载器
    When 调用 initialize_database
    Then 应该抛出 SQLiteVecInitializationError
```

---

## 10. Assumptions

- **A1**：vec0 建表语法 `vec0(chunk_id text primary key, embedding float[N])` —— **已实测通过**（含 KNN 查询）。
- **A2**：维度来源为 `initialize_database(embedding_dimension=...)`，`app_metadata` 表已存该值；本批**不引入**新的配置来源。
- **A3**：**向量存两份**（`embedding_vectors.vector_json` 权威 + `embedding_index` 索引副本）。理由是保留元数据与既有约束，代价是存储翻倍 —— **384 维 float32 ≈ 1.5 KB/chunk，10 万个 chunk 约 150 MB**，可接受。**若你认为该省这份空间，请指出**（替代方案是让 vec0 只存 id+向量，元数据只留一处）。
- **A4**：距离度量用 `vec0` 默认（L2 平方距离）。若日后要换 cosine，需要在写入前归一化向量 —— **本批不做**，但会在代码注释里写明。
- **A5**：本批**不引入 fastembed**（不需要模型），因此测试可以真跑 sqlite-vec 而不必 mock。

---

## 11. Confirmation Required

请确认这份 User Story 与 BDD scenarios 是否正确。
确认后我会**先写测试并确认 Red stage**，再实现最小生产代码。

**需要你特别确认的两点**：
1. **§10-A3 的"向量存两份"** 是否接受？（我的建议是接受，换取保留元数据与既有约束的清晰性）
2. **`requirements.txt` 要新增 `sqlite-vec` 依赖** —— 这是本批唯一的依赖变更，是否同意？（它是"修好这个地基"的前提）
