# US · 阶段 1 第四批：按语义召回片段并组装成带来源的上下文

> **状态：待确认**（BDD/TDD Gate 1 产出）
> 依据：[`planning/09`](../../planning/09-架构与数据流.md) §4（问答链路）、[`planning/06`](../../planning/06-代码现状全景.md) §4（断点 ⑦）、上游 spec §4.4
> 前置：前三批已完成（切块 ✅ / 向量索引 ✅ / 向量化 ✅）
> 流程：本文档 → **你确认** → Gate 2（先写测试，确认 Red）→ **你确认** → Gate 3（最小实现）

---

## 0. 这一批补什么，以及它为什么是阶段 1 的关键

| 文件 | 现状 | 本批做什么 |
|---|---|---|
| `app/rag/retriever.py` | 1 行占位 | 把查询嵌入 → vec0 KNN → 阈值过滤 → 返回 top-k 命中 |
| `app/rag/context_builder.py` | 1 行占位 | 把命中补上**来源元数据**（文档 / 页码 / 标题路径），并渲染成可喂给 LLM 的上下文块 |

**为什么关键**：这三批（切块 → 向量 → 检索）做完，链路第一次能从"用户提问"走到"带回溯证据的片段"。
**假设 #1（中文 query 能否检索到法文 chunk）与 #7（`chunk_size` 是否超出模型处理长度）
的答案，都只能在这一批之后才能拿到。**

---

## 1. User Story

**Title:** 按语义召回最相关的片段，并附带可回溯的来源

**As a:** 用中文提问、复习法语课程资料的学生

**I want:** 系统把我问题转成向量、在本地索引里找出最相关的几个片段，
**并且告诉我每个片段来自哪个文档、哪一页、属于哪个标题**

**So that:** 我拿到的答案能追溯到原始资料的位置，而不是一段无从核对的文字

---

## 2. Acceptance Criteria

### Retriever

- **AC1**：给定查询文本，返回**最多 `top_k`** 个命中，按距离升序。
- **AC2**：每个命中包含 `chunk_id` 与 `distance`。
- **AC3**：**距离阈值过滤**：超过 `max_distance` 的命中被丢弃（阈值可配置、可为空表示不过滤）。
- **AC4**：索引为空时返回空列表，不抛异常。
- **AC5**：查询为空字符串或仅含空白时**直接返回空列表，不加载模型**。
- **AC6**：`top_k <= 0` 是非法配置 → 抛 `ValueError`。

### ContextBuilder

- **AC7**：把命中补全为上下文条目，每条含：`chunk_id` / `text` / `document_id` / `page_number` / `heading_path` / `distance`。
- **AC8**：某条命中对应的 chunk 或 unit 查不到时（数据不一致）**跳过该条并继续**，不整体失败。
- **AC9**：渲染出的上下文块**给每个片段标注来源**（形如 `[来源 1] 文档… 第 N 页`），供 LLM 引用。
- **AC10**：空命中列表 → 返回空列表与空字符串。
- **AC11**（2026-09-12 新增）：`build_within_budget(hits, max_chars)` 在预算内**保留全部**命中；
  超出预算的片段**整片丢弃**（不截断文本，避免引用回溯到半截内容），并返回
  `dropped_chunk_ids` 与 `used_chars`；预算按字符近似累加（不加载 tokenizer）。
- **AC12**：预算是**软上限** —— **至少保留 1 条**（首条即便超出预算也保留），避免上下文空转；
  `max_chars <= 0` 抛 `ValueError`。

---

## 3. Business Rules

- **Rule 1**：`top_k` 与 `max_distance` 来自配置（`config/settings.py`），不硬编码。
- **Rule 2**：Retriever **只依赖** `EmbeddingService` 与 `EmbeddingRepository`；ContextBuilder 只依赖 `ChunkRepository` / `DocumentUnitRepository`（维持既有分层，不跨层取数据）。
- **Rule 3**：上下文块中的来源编号（`[来源 N]`）与返回的条目**顺序一致**，便于后续把 LLM 的引用映射回 `chunk_id`。
- **Rule 4**：**命中数量少于 `top_k` 不是错误**（资料本来就不多），正常返回。
- **Rule 5**：`max_distance` 的语义沿用 vec0 的默认度量（**非平方 L2 / 欧氏距离**，越小越相似）——`0` 表示完全相同。
  > 更正（2026-09-12，实测见 [`retrieval-diagnosis.md`](../retrieval-diagnosis.md) §3.4）：本文件原写「L2 平方距离」，
  > 但 vec0 v0.1.9 返回的是**非平方** L2；口径已同步修正到代码注释与配置。

---

## 4. Edge Cases

- **E1**：命中数恰好等于 `top_k`。
- **E2**：命中数少于 `top_k`（资料不足）。
- **E3**：所有命中的距离都超过阈值 → 返回空列表（而不是返回一堆不相关片段）。
- **E4**：`max_distance` 为 `None` → 不做过滤。
- **E5**：chunk 的 `metadata_json` 里没有 `heading_path`（PDF 场景）→ `heading_path` 为空列表。
- **E6**：unit 的 `page_number` 为 `None` → 渲染时省略页码，不显示 "None"。

---

## 5. Failure Cases

- **F1**：查询为空白 → 返回空（不算失败）。
- **F2**：`top_k <= 0` → 抛 `ValueError`（配置错误早暴露，与切块参数的处理一致）。
- **F3**：查询向量维度与索引不符 → 由 `EmbeddingRepository` 抛 `EmbeddingDimensionError`（沿用第二批语义）。
- **F4**：命中指向的 chunk 已被删除（索引与权威表不同步）→ 该条被跳过（AC8），**不抛异常**。

---

## 6. Dependencies / Integration Points

- **依赖**：`EmbeddingService.embed_query`（第三批）、`EmbeddingRepository.search_similar`（第二批）、`ChunkRepository` / `DocumentUnitRepository`。
- **被依赖**：阶段 2 的 `tools/chunk_search_tool`（Agent 调用它检索）、`context_builder` 的输出进 `CHAT_USER_PROMPT_TPL` 的 `${context}`。
- **不依赖**：LLM API（本批只到"组装上下文"为止，不生成答案）。

---

## 7. Affected Areas

- **Frontend:** 无
- **Backend:** `app/rag/retriever.py`、`app/rag/context_builder.py`、`app/config/settings.py`（+ `RETRIEVAL_TOP_K` / `RETRIEVAL_MAX_DISTANCE`）
- **Database:** **无 schema 变更**
- **API Contract:** 无变更（本批不暴露 HTTP 接口）
- **Tauri / Desktop:** 无
- **Tests:** `tests/unit/rag/test_retriever.py`（新增）、`tests/unit/rag/test_context_builder.py`（新增）、`tests/integration/persistence/`（端到端：建索引 → 检索 → 组装上下文）

---

## 8. BDD Scenarios

```gherkin
Feature: 语义召回与上下文组装

  Scenario: 按语义召回返回最多 top_k 个命中
    Given 索引中有 3 个向量，且 top_k 配置为 2
    When 用其中一条的向量作为查询检索
    Then 应该返回 2 个命中
    And 命中的距离应该按升序排列

  Scenario: 命中包含 chunk_id 与距离
    Given 索引中已有向量
    When 检索
    Then 每个命中都应该有非空的 chunk_id
    And 每个命中都应该有距离值

  Scenario: 距离超过阈值的命中被丢弃
    Given 索引中有一个与查询完全不同的向量，且 max_distance 配置为 0.5
    When 检索
    Then 该命中不应该出现在结果中

  Scenario: 阈值为空时不过滤
    Given max_distance 配置为 None
    When 检索
    Then 所有命中都应该返回（直到 top_k）

  Scenario: 空索引返回空结果
    Given 索引中没有任何向量
    When 检索
    Then 应该返回空列表

  Scenario Outline: 空白查询不加载模型直接返回空
    Given 一个记录了模型构造次数的 Retriever
    When 用 "<query>" 检索
    Then 应该返回空列表
    And 模型不应该被构造

    Examples:
      | query |
      |       |
      |    |

  Scenario Outline: 非法 top_k 被拒绝
    Given top_k 配置为 <top_k>
    When 构造 Retriever
    Then 应该抛出 ValueError

    Examples:
      | top_k |
      | 0     |
      | -3    |

  Scenario: 命中被补全来源信息
    Given 索引中有一个来自"第 3 页、标题为 Chapitre 2"的 chunk
    When 用 ContextBuilder 处理该命中
    Then 该条目应该包含 document_id
    And 该条目的 page_number 应该为 3
    And 该条目的 heading_path 应该为 ["Chapitre 2"]

  Scenario: 缺失的 chunk 被跳过而不失败
    Given 一个指向不存在 chunk 的命中
    When 用 ContextBuilder 处理
    Then 应该返回空列表
    And 不应该抛出异常

  Scenario: 上下文块为每个片段标注来源
    Given 两个有效命中
    When 渲染上下文块
    Then 文本中应该包含 "[来源 1]" 与 "[来源 2]"
    And 每个来源后面都应该带上对应的页码

  Scenario: 页码缺失时不显示占位文本
    Given 一个 unit 的 page_number 为 None
    When 渲染上下文块
    Then 文本中不应该出现 "None"

  Scenario: 空命中列表返回空结果
    Given 一个空的命中列表
    When 用 ContextBuilder 处理
    Then 应该返回空列表
    And 渲染出的上下文块应该为空字符串
```

---

## 9. Assumptions

- **A1**：`top_k` 默认 **20**（2026-09-12 由 5 上调：诊断实验测得中文提问 HitRate@5 仅 50%、
  而 @20 达 83.3%（修重音后 91.7%），见 [`retrieval-diagnosis.md`](../retrieval-diagnosis.md) §3.2），
  `max_distance` 默认 **None（不过滤）** ——
  先跑通再调阈值，且阈值必须由评测数据决定。
- **A2**：距离语义为 vec0 默认的 **非平方 L2 / 欧氏距离**（2026-09-12 更正，原写成「平方 L2」）。
  改用 cosine 需先归一化，**本批不做**。
- **A3**：上下文块格式为纯文本 + `[来源 N]` 标记，**不引入**专门的 prompt 模板引擎（沿用上游 `string.Template` 的既有风格）。
- **A4**：本批**不做**重排（reranker）与混合检索——它们要有评测数据支撑才决定（`13` §3.2）。
- **A5**：**`chunk_size` 实验不放在本批**。见 §10。
- **A6**（2026-09-12 新增）：上下文预算按**字符**近似（`CONTEXT_MAX_CHARS` 默认 8000 ≈ 法文 1900 token）。
  精确的 token 预算应由 provider 的上下文窗口决定，留待阶段 2 接入 provider 时替换；
  本批只钉住规模上限，不度量它对回答质量与延迟的影响。

---

## 10. ⚠️ 关于假设 #1 / #7 的实验（**本批不做，但必须紧接着做**）

本批交付的是"能检索"，**但"检索得好不好"要另一场实验回答**：

```
实验（阶段 1 收尾，需真实法语课程资料）：
  变量：chunk_size ∈ {300, 500, 800}
  固定：同一批查询、同一模型、同一 top_k
  指标：HitRate@5（期望来源的页码是否出现在召回里）
  产出：一张表 + 一个结论（chunk_size 取多少），写入 docs/eval-report.md
```

**前置条件（需要你提供或确认）**：
1. **真实法语课程资料**（PDF/PPT）——这是整场实验的数据基础，也是假设 #2（痛点是否真实）的素材；
2. 一批**中文查询 + 期望来源页码**（可先用 10–20 条起步，不必等到 25 条齐全）。

> 没有真实资料，假设 #1/#7 只能停留在"未验证"，**"语义检索有效"这句话就不许写进 README/简历**。

---

## 11. Schema Change Justification

**本批不需要任何 schema 变更。**

```text
Schema Change Justification:
- User Story requirement: 无。本批只读取既有表（chunks / document_units / embedding_index）。
- Migration required: 无
- Backward compatibility: 不适用
- Data migration needed: 无
- Tests covering migration: 不适用
```

---

## 12. API Contract Change

**无 API 契约变更。** 本批不新增/修改 HTTP 接口或 Tauri command
（把检索接进 HTTP 是第五批与阶段 2 的事）。

---

## 13. Confirmation Required

请确认这份 User Story 与 BDD scenarios 是否正确。
确认后我会**先写测试并确认 Red stage**，再实现最小生产代码。

**需要你特别确认的三点**：
1. **§9-A1 的默认值**：`top_k=5`、`max_distance=None`（先不过滤，阈值交给评测）。是否同意？
2. **§7 的 `ContextItem` 字段**（`chunk_id` / `text` / `document_id` / `page_number` / `heading_path` / `distance`）
   —— 这就是将来 `citations` 的原料，够不够？
3. **§10 的前置条件**：**你手上有没有真实的法语课程资料**（PDF/PPT）？
   这决定假设 #1/#7 什么时候能被实测——**没有它，这两条会一直卡在"未验证"**。
