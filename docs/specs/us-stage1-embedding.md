# US · 阶段 1 第三批：把片段向量化并写入本地索引

> **状态：已确认（含"文本截断"，2026-09-12）** —— Gate 1 通过，进入 Gate 2（先写测试）
> 依据：[`planning/08`](../../planning/08-技术选型决策记录.md) §2.2（fastembed 选型）、[`planning/06`](../../planning/06-代码现状全景.md) §4（断点 ⑥）、上游 spec §4.4
> 前置：第二批已完成（`embedding_index` vec0 表可用、`save_to_index` / `search_similar` 已就绪）
> 流程：本文档（✅ 确认）→ Gate 2（先写测试，确认 Red）→ **你确认** → Gate 3（最小实现）

---

## 0. 这一批要补齐的两个空白

| 文件 | 现状 | 本批做什么 |
|---|---|---|
| `app/services/embedding_service.py` | 1 行占位 | 用 **fastembed** 把文本转成向量（懒加载模型、可注入、超长截断） |
| `app/rag/vector_index_builder.py` | 1 行占位 | 把一批 Chunk **批量嵌入并双写**进 `embedding_vectors` + `embedding_index` |

做完这一批，链路就到达 **"文档 → 切块 → 向量 → 可语义检索"**，
**假设 #1（中文 query 能否检索到法文 chunk）第一次可以被实测**。

---

## 1. User Story

**Title:** 让切好的片段带上语义向量并进入可检索索引

**As a:** 使用这个助手复习法语课程资料的学生

**I want:** 系统自动把我资料里的每个片段转成语义向量，并在本地建立可检索的索引

**So that:** 我提问时系统能按**语义**（而不只是关键词匹配）找到最相关的片段，
而且这个判断在**我的电脑上**完成、资料不出本机

---

## 2. Acceptance Criteria

- **AC1**：给定 N 条文本，返回 **N 个向量**，每个向量的维度等于配置的 `EMBEDDING_DIMENSION`（384）。
- **AC2**：传入**空文本列表**时直接返回空列表，**不加载模型**（避免无意义地触发首次下载）。
- **AC3**：提供单条**查询**的嵌入接口，返回单个向量（与批量接口结果一致）。
- **AC4**：模型**按需加载且只加载一次** —— 同一实例重复调用不会重复构造模型。
- **AC5**：模型输出的向量维度与配置不符时，**抛出明确错误**，不静默接受。
- **AC6**：可以把一批 Chunk 批量嵌入，并**同时**写入 `embedding_vectors`（含 `embedding_model` 字段，供追溯）与 `embedding_index`（可检索副本）。
- **AC7**：传入**空 Chunk 列表**时返回 0，**不加载模型**。
- **AC8**：索引构建完成后，用其中一个 Chunk 的向量查询 top-1，**能命中该 Chunk 自身**（端到端接通第二批的 KNN 能力）。
- **AC9**（本次新增）：**超过配置上限 `MAX_EMBED_CHARS` 的文本会被截断到该上限后再嵌入**；
  未超限的文本**不被改动**。

---

## 3. Business Rules

- **Rule 1**：模型名与维度来自 `config/settings.py`（`EMBEDDING_MODEL` / `EMBEDDING_DIMENSION`），不硬编码在 service 里。
- **Rule 2**：`embedding_model` 必须写进 `embedding_vectors`，便于日后"这段向量是用哪个模型生成的"追溯（与 `parser_name` / `chunker_name` 的设计一致）。
- **Rule 3**：**所有涉及模型的测试必须注入假模型**，CI **绝不能**下载 0.22 GB 模型。
- **Rule 4**：`EmbeddingService` 只负责"文本 → 向量"，**不碰持久化**；持久化由 `VectorIndexBuilder` 通过 repository 完成（维持既有分层）。
- **Rule 5**：双写顺序为"先权威记录（`embedding_vectors`），后索引（`embedding_index`）"——若中途失败，索引缺失可由权威记录重建。
- **Rule 6**：截断上限 `MAX_EMBED_CHARS` 来自配置（默认 1000 字符），**不硬编码**。

---

## 4. Edge Cases

- **E1**：单条文本 → 返回 1 个向量。
- **E2**：批量接口返回顺序与输入顺序**一一对应**（靠 zip 对齐，不依赖模型内部顺序）。
- **E3**：文本含中文 / 法语 / 混排 → 不影响接口行为（模型自身处理）。
- **E4**：同一批 chunk 中文本内容重复 → 各自独立嵌入、独立索引（不做去重，去重是后续优化项）。
- **E5**：文本长度**恰好等于** `MAX_EMBED_CHARS` → 不截断。
- **E6**：文本恰好超出 1 个字符 → 截断到上限。

---

## 5. Failure Cases

- **F1**：模型构造失败（包缺失 / 无网络首次下载失败）→ **抛出明确错误**，不返回零向量。
- **F2**：模型返回的向量数量与输入文本数量不一致 → 抛错（说明模型行为异常，不能错位对应）。
- **F3**：模型输出维度 ≠ 配置维度 → 抛 `EmbeddingDimensionError`（复用第二批已有的异常语义）。
- **F4**：Chunk 已存在于 `embedding_vectors`（重复构建）→ 由既有 upsert 语义覆盖，**不报错、不产生重复行**。

---

## 6. Dependencies / Integration Points

- **新依赖**：`fastembed`（**必须写进 `requirements.txt` 并加上限**）。
- **依赖**：`config/settings.py`、第二批的 `EmbeddingRepository.save_for_chunk` / `save_to_index`。
- **被依赖**：第四批的 `retriever`（用 `embed_query` + `search_similar`）、第五批的 `document_ingest_service`（摄取时调用 builder）。
- **不依赖**：网络（除首次下载模型）、LLM API。

---

## 7. Affected Areas

- **Frontend:** 无
- **Backend:** `app/services/embedding_service.py`（占位 → 实现）、`app/rag/vector_index_builder.py`（占位 → 实现）、`app/config/settings.py`（+ `MAX_EMBED_CHARS`）
- **Database:** **无 schema 变更**（`embedding_vectors` 与 `embedding_index` 在第二批已就绪）
- **API Contract:** 无变更
- **Tauri / Desktop:** 无
- **Tests:** `tests/unit/services/test_embedding_service.py`（新增）、`tests/unit/rag/test_vector_index_builder.py`（新增，目录不存在需创建）、`tests/integration/persistence/`（索引构建端到端）

---

## 8. BDD Scenarios

```gherkin
Feature: 向量化与索引构建

  Scenario: 批量文本被转成同数量的向量
    Given 一个注入了假模型的 EmbeddingService，且配置维度为 384
    When 用 3 条文本调用批量嵌入
    Then 应该返回 3 个向量
    And 每个向量的长度都应该等于 384

  Scenario: 批量结果与输入顺序一一对应
    Given 一个注入了假模型的 EmbeddingService，且假模型对每条文本返回可区分的向量
    When 用 ["premier", "deuxième", "troisième"] 调用批量嵌入
    Then 第 1 个向量应该对应 "premier"
    And 第 3 个向量应该对应 "troisième"

  Scenario: 空文本列表不加载模型
    Given 一个注入了假模型的 EmbeddingService，且记录模型是否被构造
    When 用空列表调用批量嵌入
    Then 应该返回空列表
    And 模型不应该被构造

  Scenario: 单条查询嵌入返回单个向量
    Given 一个注入了假模型的 EmbeddingService
    When 用一条查询文本调用查询嵌入
    Then 应该返回 1 个向量
    And 它与批量嵌入同一条文本的结果一致

  Scenario: 模型按需加载且只加载一次
    Given 一个记录了构造次数的假模型工厂
    When 连续调用嵌入两次
    Then 模型工厂应该只被调用 1 次

  Scenario: 超过上限的文本被截断后再嵌入
    Given 一个 EmbeddingService，其截断上限为 100 字符
    And 一个会记录实际收到文本的假模型
    When 用一条 250 字符的文本调用批量嵌入
    Then 假模型收到的文本长度应该恰好为 100

  Scenario: 未超过上限的文本不被改动
    Given 一个 EmbeddingService，其截断上限为 100 字符
    And 一个会记录实际收到文本的假模型
    When 用一条 100 字符的文本调用批量嵌入
    Then 假模型收到的文本应该与输入完全一致

  Scenario Outline: 模型输出维度与配置不符时报错
    Given 一个返回 <dimension> 维向量的假模型
    When 调用嵌入
    Then 应该抛出 EmbeddingDimensionError

    Examples:
      | dimension |
      | 128       |
      | 512       |

  Scenario: 模型返回的向量数量与输入不一致时报错
    Given 一个返回数量不匹配的假模型
    When 用 2 条文本调用批量嵌入
    Then 应该抛出 ValueError

  Scenario: 一批 Chunk 被嵌入并双写进向量表与索引
    Given 数据库中已有 2 个 Chunk
    When 用 VectorIndexBuilder 为它们构建索引
    Then 应该返回 2
    And embedding_vectors 表中应该有 2 条记录
    And 每条记录的 embedding_model 都等于配置的模型名
    And embedding_index 表中应该有 2 条记录

  Scenario: 空 Chunk 列表不加载模型
    Given 一个注入了假模型的 VectorIndexBuilder
    When 传入空的 Chunk 列表
    Then 应该返回 0
    And 模型不应该被构造

  Scenario: 索引构建后能用向量命中对应 Chunk
    Given 已为 2 个 Chunk 构建了索引
    When 用第 1 个 Chunk 的向量查询 top-1
    Then 返回的 chunk_id 应该是第 1 个 Chunk
    And 距离应该为 0

  Scenario: 重复构建同一批 Chunk 不产生重复记录
    Given 已为 2 个 Chunk 构建过索引
    When 再次为同一批 Chunk 构建索引
    Then embedding_vectors 与 embedding_index 中仍然各只有 2 条记录
```

---

## 9. Assumptions

- **A1**：`EmbeddingService` 通过**可注入的 model factory** 获取模型（默认 `fastembed.TextEmbedding`），
  这样测试注入假模型即可，**不需要 mock 库本身**，也不需要网络。
- **A2**：模型采用**懒加载**（首次调用嵌入时才构造）；构造与推理的耗时都会计入第四批的性能基线。
- **A3**：模型名固定为 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，维度 384（`08` §2.2 已定）。
- **A4**：`MAX_EMBED_CHARS` 默认 **1000 字符** —— 比 `chunk_size`（800）略大，**保证正常 chunk 不会被动到**，
  只为拦住异常超长输入。见 §12 的已知张力。
- **A5**：向量以 `vector_json`（权威表）与 vec0（索引）**双写**（第二批已确认的决策）。
- **A6**：本批**不做**批量大小调优／并发／缓存——那是第四批之后的性能优化项。

---

## 10. Schema Change Justification

**本批不需要任何 schema 变更。**

```text
Schema Change Justification:
- User Story requirement: 无。embedding_vectors 表（含 embedding_model / vector_dimension）
  与 embedding_index 虚拟表都在第二批已建立且字段齐备。
- Migration required: 无
- Backward compatibility: 不适用
- Data migration needed: 无
- Tests covering migration: 不适用
```

---

## 11. API Contract Change

**无 API 契约变更。** 本批不新增/修改任何 HTTP 接口或 Tauri command。

---

## 12. ⚠️ 已知张力：`chunk_size` 与模型的 token 上限不匹配（**必须记录，待评测**）

- `paraphrase-multilingual-MiniLM-L12-v2` 的**最大序列长度为 128 tokens**（模型公开规格）。
- 128 tokens 折算成字符：**法语约 512 字符**、中文约 128 字、混排不定。
- 而我们在第一批定的 `chunk_size = 800` **字符**。

**推论**：对法语课程资料，**一个 800 字符的 chunk 超出模型可处理长度约 1.5 倍**，
**超出部分会被模型静默截断、因而检索不到**。

**本批的处理**：
1. `MAX_EMBED_CHARS`（1000）**不解决**这个问题——它只拦极端输入；
2. 因此这个张力必须在**第四批的评测里用数据解决**：
   ```
   实验：chunk_size ∈ {300, 500, 800} × 同一套查询
   指标：HitRate@5（**这是假设 #1 的核心指标**）
   注意：chunk_size 越小 → 向量覆盖率越高，但上下文越碎 → 存在拐点，需要数据找
   ```
3. 在 `STATUS.md` 的风险/假设区登记，**不得在未实测前宣称"语义检索有效"**。

> 这条也是"**技术选型必须与业务约束对齐**"的一个真实样例：
> 选模型时看了体积、语言覆盖、离线能力，**却漏看了它的上下文长度**——
> 而这个漏看会直接影响检索质量。

---

## 13. Confirmation Required

✅ Gate 1 已确认（含新增的 **AC9 文本截断**）。

接下来：Gate 2 —— 我先写测试并确认 Red stage，再停下等你确认，然后实现最小生产代码。
