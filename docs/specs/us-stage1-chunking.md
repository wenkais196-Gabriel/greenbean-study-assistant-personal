# US · 阶段 1 第一批：把解析后的文档单元切成可溯源的语义片段

> **状态：待确认**（BDD/TDD Gate 1 产出）
> 依据：[`planning/12-路线图v2`](../../planning/12-路线图v2-决策与体验优先.md) 阶段 1、[`planning/08`](../../planning/08-技术选型决策记录.md) §2.3（切块策略）、[`planning/06`](../../planning/06-代码现状全景.md) §4（断点 ⑤）
> 流程：本文档 → **你确认** → Gate 2（先写测试，确认 Red）→ **你确认** → Gate 3（最小实现）→ Green

---

## 0. 为什么这是第一批（分批理由）

阶段 1 的完整范围有 8 个模块（`12` §2），一次性确认会失控。按**可独立验证的最小纵向切片**拆成四批：

| 批次 | 内容 | 依赖 | 状态 |
|---|---|---|---|
| **第一批（本文档）** | **切块**：`ChunkService` + `ChunkRepository.save_batch` + `config/settings.py` | 无（纯逻辑 + 已存在的 `chunks` 表） | **待确认** |
| 第二批 | 向量化与索引：修 `init_db` 的 sqlite-vec 加载（**bug fix**）+ `EmbeddingService` + `rag/vector_index_builder` | 第一批 | 待出 |
| 第三批 | 检索与上下文：`rag/retriever` + `rag/context_builder` | 第二批 | 待出 |
| 第四批 | 摄取闭环：`document_ingest_service` 解封落库 + `main.py` CORS | 一~三批 | 待出 |

**选第一批先做的三个理由**：
1. 它是**纯逻辑**（输入文本 → 输出片段），最容易做严格的 TDD，不需要模型、不需要网络；
2. 它是**断点 ⑤**（`planning/06` §4），是检索的前置，不做它后面都动不了；
3. **不需要改数据库 schema**（`chunks` 表已存在且结构匹配），风险最低。

---

## 1. User Story

**Title:** 把解析后的文档单元切成可溯源的语义片段（Chunk）

**As a:** 使用这个助手复习法语课程资料的学生

**I want:** 系统把我上传的课程资料切成大小合适、语义完整的片段，并且**记住每一段来自哪一页、属于哪个标题**

**So that:** 我提问时系统能精准定位到相关内容，并在我看到的答案里给出**能跳回原页的引用**，而不是一段无从核对的文字

---

## 2. Acceptance Criteria

- **AC1**：每个 Chunk 都记录**来源 DocumentUnit**、在**该 unit 内的序号**、以及在**该 unit 正文中的字符区间**（`start_char` / `end_char`）。
- **AC2**：每个 Chunk 的文本长度**不超过配置的 `chunk_size`**。
- **AC3**：同一 unit 内相邻 Chunk 之间保留 **`chunk_overlap` 个字符的重叠**，使跨片段边界的内容不丢失。
- **AC4**：切块**优先在段落边界**断开；只有当**单个段落本身超过 `chunk_size`** 时，才退化为按窗口硬切。
- **AC5**：每个 Chunk 的 `metadata_json` 记录该片段**所属的 heading 路径**（取自 unit 的 `metadata_json.headings`）；unit 无 heading 时该字段为 `[]`。
- **AC6**：`text_content` 为空白（或仅含空白字符）的 unit **不产生任何 Chunk**。
- **AC7**：一个 unit 切出的全部 Chunk 能通过 `ChunkRepository.save_batch` **一次性持久化**，且同一 unit 内 `sequence_index` 唯一。

---

## 3. Business Rules

- **Rule 1**：`chunk_size` 与 `chunk_overlap` 来自统一配置（新增 `app/config/settings.py`），**不得硬编码**在 service 里。
- **Rule 2**：同一 unit 内 `sequence_index` 从 **0** 开始**连续递增**，无空洞。
- **Rule 3**：`start_char` / `end_char` 是**相对于所属 unit 的 `text_content`** 的偏移（不是整个文档），与 `Chunk` 实体的既有定义一致。
- **Rule 4**：每个 Chunk 必须写入 `chunker_name` 与 `chunker_version`，用于日后追溯"这段是用哪版切块器切的"。（与 `parser_name` / `parser_version` 的设计一致，见上游 `DocumentUnit`。）
- **Rule 5**：**不产生空 Chunk**。切分后 `strip()` 为空白的片段直接丢弃。（`Chunk` 实体本身就会拒绝空 `text_content`。）
- **Rule 6**：切块**不修改** `DocumentUnit`，只读取。切块是幂等的纯函数：同样的 unit + 同样配置 → 同样的 Chunk 列表。

---

## 4. Edge Cases

- **E1**：unit 正文长度**恰好等于** `chunk_size` → 产生 1 个 Chunk，不产生空的第 2 个。
- **E2**：**单个段落超过 `chunk_size`**（如 OCR 出来的整页无分段）→ 按窗口硬切，仍不超过 `chunk_size`。
- **E3**：**中文 + 法语混排**文本 → 长度按**字符数**计，不按字节、不按词。
- **E4**：unit **有 headings**（PPT / Word / Markdown）→ 每个 Chunk 带上正确的 heading 路径；**PDF 的 headings 恒为空数组**（已知限制），此时路径为空。
- **E5**：**最后一个片段**短于 `chunk_size` → 正常产出，不补齐、不丢弃。
- **E6**：正文中**存在连续多个换行**（空段落）→ 不产生空 Chunk（Rule 5）。
- **E7**：**空列表输入**（没有任何 unit）→ 返回空列表，不抛异常。

---

## 5. Failure Cases

- **F1**：配置非法 —— `chunk_overlap >= chunk_size` → **抛 `ValueError`**（配置错误必须早暴露，而不是静默产生无限循环或零长度片段）。
- **F2**：配置非法 —— `chunk_size <= 0` → 抛 `ValueError`。
- **F3**：unit 的 `text_content` 为空白 → **不算失败**，返回空列表（正常行为，见 AC6）。
- **F4**：`save_batch` 收到**同一 unit 内重复的 `sequence_index`** → 由数据库唯一约束拒绝（`UNIQUE(document_unit_id, sequence_index)` 已存在），**不做静默覆盖**。

> **说明**：本批**没有外部依赖**（不调模型、不发网络请求），因此没有"超时 / 外部服务失败"类失败路径。这是刻意的——第一批刻意排除不确定性，让 TDD 干净。

---

## 6. Dependencies / Integration Points

- **依赖**：`app.entities.DocumentUnit`（输入，已存在）、`app.entities.Chunk`（输出，已存在）、`app.config.settings`（**新增**）、`app.repositories.ChunkRepository`（**新增 `save_batch`**）。
- **被依赖**：第二批的 `EmbeddingService`（消费 Chunk 文本）、第三批的 `retriever`（返回 Chunk + 溯源）、第四批的 `document_ingest_service`（串联调用）。
- **不依赖**：`EmbeddingService`、fastembed、sqlite-vec、网络、LLM。

---

## 7. Affected Areas

- **Frontend:** 无
- **Backend:** `app/services/chunk_service.py`（1 行占位 → 实现）、`app/repositories/chunk_repository.py`（+ `save_batch`）、`app/config/settings.py`（1 行占位 → 实现）
- **Database:** **无 schema 变更**（见 §10）
- **API Contract:** **无变更**（见 §11）
- **Tauri / Desktop:** 无
- **Tests:** `tests/unit/services/test_chunk_service.py`（现为 1 行占位 → 替换）；新增 `tests/unit/config/`（settings 校验）；`tests/integration/persistence/`（`save_batch` 持久化）

---

## 8. BDD Scenarios

```gherkin
Feature: DocumentUnit 切块（Chunk 生成）

  Scenario: 正文短于 chunk_size 的单元产生单个 Chunk
    Given 一个 DocumentUnit，其 text_content 长度小于配置的 chunk_size
    When 对该 unit 执行切块
    Then 应该产生 1 个 Chunk
    And 该 Chunk 的 text_content 等于该 unit 的全文
    And 该 Chunk 的 sequence_index 为 0
    And 该 Chunk 的 start_char 为 0
    And 该 Chunk 的 end_char 等于该 unit 正文的字符长度
    And 该 Chunk 的 document_unit_id 等于该 unit 的 id

  Scenario: 正文长于 chunk_size 的单元被切成多个 Chunk
    Given 一个 DocumentUnit，其 text_content 长度大于配置的 chunk_size 的两倍
    When 对该 unit 执行切块
    Then 应该产生至少 2 个 Chunk
    And 每个 Chunk 的 text_content 长度都不超过 chunk_size
    And 所有 Chunk 的 sequence_index 从 0 开始连续递增

  Scenario: 优先在段落边界切断
    Given 一个 DocumentUnit，其正文由 3 个段落组成，第 1、2 段之和恰好超过 chunk_size
    When 对该 unit 执行切块
    Then 第 1 个 Chunk 的文本应该恰好等于第 1 段
    And 第 1 个 Chunk 不应该把第 2 段从中间切断

  Scenario: 单个段落超过 chunk_size 时按窗口硬切
    Given 一个 DocumentUnit，其正文是 1 个没有换行的超长段落，长度大于 chunk_size 的三倍
    When 对该 unit 执行切块
    Then 应该产生至少 3 个 Chunk
    And 每个 Chunk 的文本长度都不超过 chunk_size

  Scenario: 相邻 Chunk 之间保留配置的重叠
    Given 一个 DocumentUnit，其正文被切成 2 个 Chunk，且配置的 chunk_overlap 大于 0
    When 对该 unit 执行切块
    Then 第 2 个 Chunk 的开头应该与第 1 个 Chunk 的结尾重叠 chunk_overlap 个字符

  Scenario: 每个 Chunk 记录自己所属的 heading 路径
    Given 一个 DocumentUnit，其 metadata_json 中的 headings 为 [{"level": 1, "text": "Chapitre 3"}, {"level": 2, "text": "Le polymorphisme"}]
    When 对该 unit 执行切块
    Then 每个 Chunk 的 metadata_json 都应该包含 heading 路径 ["Chapitre 3", "Le polymorphisme"]

  Scenario: 没有 headings 的单元（如 PDF）也能切块
    Given 一个 DocumentUnit，其 metadata_json 中的 headings 为空数组
    When 对该 unit 执行切块
    Then 应该正常产生 Chunk
    And 每个 Chunk 的 heading 路径为空列表

  Scenario: 每个 Chunk 记录切块器标识
    Given 任意一个可切块的 DocumentUnit
    When 对该 unit 执行切块
    Then 每个 Chunk 的 chunker_name 与 chunker_version 都不为空

  Scenario Outline: 空白正文不产生任何 Chunk
    Given 一个 DocumentUnit，其 text_content 为 "<blank_content>"
    When 对该 unit 执行切块
    Then 应该产生 0 个 Chunk

    Examples:
      | blank_content |
      |               |
      |      |
      | \n\n\n        |
      | \t  \n        |

  Scenario: 正文长度恰好等于 chunk_size
    Given 一个 DocumentUnit，其 text_content 长度恰好等于配置的 chunk_size
    When 对该 unit 执行切块
    Then 应该产生 1 个 Chunk
    And 该 Chunk 的文本等于该 unit 全文

  Scenario: 空单元列表返回空结果
    Given 一个空的 DocumentUnit 列表
    When 执行切块
    Then 应该返回空列表
    And 不应该抛出异常

  Scenario: 段落之间的连续空行不产生空 Chunk
    Given 一个 DocumentUnit，其正文在段落之间有 3 个连续换行
    When 对该 unit 执行切块
    Then 所有 Chunk 的 text_content 去除空白后都不为空

  Scenario Outline: 非法配置被拒绝
    Given 配置的 chunk_size 为 <chunk_size>，chunk_overlap 为 <chunk_overlap>
    When 对该配置执行切块
    Then 应该抛出 ValueError

    Examples:
      | chunk_size | chunk_overlap |
      | 500        | 500           |
      | 500        | 600           |
      | 0          | 0             |
      | -100       | 10            |

  Scenario: 切出的 Chunk 能被批量持久化并读回
    Given 一个已经切成 N 个 Chunk 的 DocumentUnit 已存在于数据库中
    When 调用 ChunkRepository.save_batch 保存这些 Chunk 并提交
    Then 数据库中该 unit 下应该有 N 条 chunk 记录
    And 按 sequence_index 排序的顺序与切块产出的顺序一致

  Scenario: 同一单元内重复的 sequence_index 被数据库拒绝
    Given 数据库中某 unit 下已存在 sequence_index 为 0 的 Chunk
    When 再次保存一个 document_unit_id 与 sequence_index 都相同的 Chunk
    Then 数据库应该拒绝这次写入
    And 不应该静默覆盖已有记录
```

> **补充建议场景，等待用户确认是否纳入范围。**
> 以下两个场景我认为有价值，但**不是**从你的 US/AC 直接推出的，是否纳入由你定：
>
> ```gherkin
> Scenario: 切块不修改来源单元
>   Given 一个已存在的 DocumentUnit 及其切块结果
>   When 再次对该 unit 执行切块
>   Then 产出应该与第一次完全一致
>   And 该 unit 的 text_content 与 token_count 不应该被改变
> ```
> ```gherkin
> Scenario: 中法混排文本按字符计数
>   Given 一个 DocumentUnit，其正文为 "Le polymorphisme 多态是面向对象编程的核心概念"
>   When 对该 unit 执行切块，且 chunk_size 设为 10
>   Then 每个 Chunk 的字符数都应该不超过 10
>   And 不应该出现被截断的半个字符
> ```

---

## 9. Assumptions

- **A1**：`chunk_size` 与 `chunk_overlap` **按字符计**（不是 token）。理由见 [`planning/08`](../../planning/08-技术选型决策记录.md) §2.4：`token_utils.py` 目前是占位，阶段 1 不引入 tokenizer；`metadata_json` 会记录参数，为日后换 token 留出空间。
- **A2**：默认值取 **`chunk_size = 800`、`chunk_overlap = 120`**（15% 重叠）。对照业界常见的"500–1000 tokens / 10–15% overlap"，中文字符 ≈ 1 token、法语约 4 字符 ≈ 1 token，故 800 字符是偏保守的中值。**这两个值会被评测集 A/B 调整**（`12` §3.3），现在只是起点。
- **A3**：`chunker_name` 取 `"paragraph_window_chunker"`（段落优先 + 窗口回退），`chunker_version` 取 `"1.0.0"`。这与上游 spec §4.4 里 `fixed_size_chunker` / `recursive_chunker` 的命名习惯一致，但更准确描述本实现。
- **A4**：heading 路径在 `metadata_json` 里以 `{"heading_path": ["Chapitre 3", "Le polymorphisme"]}` 形式存放，**不改数据库 schema**（`Chunk.metadata_json` 已是 `TEXT` 列存 JSON）。
- **A5**：本批**不实现**章节树切块（`planning/08` §2.3 已决定降级为"数据驱动再定"）。
- **A6**：本批**不做** `page_index_builder` 的重构（那是阶段 1 末尾的事，见 `planning/04` §5.3）。

---

## 10. Schema Change Justification

**本批不需要任何 schema 变更。**

```text
Schema Change Justification:
- User Story requirement: 无。chunks 表已存在，字段（document_unit_id / sequence_index /
  text_content / start_char / end_char / token_count / metadata_json /
  chunker_name / chunker_version / created_at）完全覆盖本批需求。
- Migration required: 无
- Backward compatibility: 不适用
- Data migration needed: 无
- Tests covering migration: 不适用
```

> 这正是选它当第一批的收益之一：**零 schema 风险**。

---

## 11. API Contract Change

**无 API 契约变更。** 本批不新增/修改任何 HTTP 接口或 Tauri command。

---

## 12. Confirmation Required

请确认这份 User Story 与 BDD scenarios 是否正确。
确认后我会**先写测试并确认 Red stage**，再实现最小生产代码。

**需要你特别确认的三点**：
1. **§9-A2 的默认参数**（`chunk_size = 800` / `chunk_overlap = 120`）是否接受？它们是评测调优的起点，不是定论。
2. **§8 末尾两个"补充建议场景"** 是否纳入本批范围？
3. **§5-F1 的失败策略**：配置非法时**抛 `ValueError` 直接失败**（我倾向这样，早暴露），而不是静默用默认值兜底。是否同意？
