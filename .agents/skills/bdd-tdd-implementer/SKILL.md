---
name: bdd-tdd-implementer
description: >
  Use this skill only for code-changing implementation tasks: feature, bug fix,
  refactor, user story, acceptance criteria, BDD scenario, TDD workflow, unit
  test, integration test, or test-first implementation. 使用此 skill 仅限需要修改代码
  的实现类任务。Codex 必须先解析 User Story，生成 BDD scenarios，等待用户确认，
  再先写测试并确认 Red stage，再等待用户确认，然后实现最小生产代码并运行测试。
  Do not use this skill for pure explanation, architecture discussion, code
  review, code reading, documentation-only work, or non-code-changing tasks.
  不要用于纯解释、架构讨论、代码审查、代码阅读、仅写文档或不修改代码的任务。
---

# BDD & TDD Implementation Skill

这个 repository-scoped instruction-only skill 用于通过严格的 BDD + TDD 流程完成代码变更。

目标：

- 防止过早进入实现。
- 先明确可观察行为和验收标准。
- 先写测试，再写生产代码。
- 保持实现最小、可验证、可维护。

## 适用范围

仅在用户要求代码变更时使用，例如：

- 实现功能
- 修复 bug
- 重构行为并保持功能
- 新增或更新测试
- 实现 User Story
- 将 Acceptance Criteria 转为测试
- 创建 BDD scenarios
- 遵循 TDD 或 test-first development
- 修改 frontend、backend、database、service、repository、API contract、Tauri 或 integration 行为

典型触发语：

- “实现这个功能”
- “修复这个 bug”
- “按 TDD 做”
- “帮我写测试”
- “根据这个 User Story 实现”
- “根据 AC 写代码”
- “补充 BDD 场景”
- “先写测试再实现”
- “refactor this”
- “implement this story”
- “write tests first”

## 不适用范围

不修改代码的任务不要进入 gated implementation workflow，例如：

- 纯解释
- 仅架构讨论
- 仅代码阅读
- 仅代码审查
- 不修改代码的 debugging advice
- documentation-only writing
- BDD / TDD 理论解释
- 询问 BDD 或 TDD 是什么
- 比较工具、框架或库
- 高层产品 brainstorming

如果用户只要求建议、解释或审查，正常回答，不进入本流程。

## 核心原则

不要直接开始写实现代码。默认顺序是：

1. 理解 User Story。
2. 提取或澄清 Acceptance Criteria。
3. 生成 BDD scenarios。
4. 等待用户确认。
5. 先写或更新测试。
6. 运行测试并确认 Red stage。
7. 等待用户确认。
8. 实现最小生产代码。
9. 运行测试并确认 Green stage。
10. 仅在测试保持 green 后进行必要 refactor。
11. 汇报变更和验证结果。

生成 BDD scenarios、TDD 测试说明、测试计划、阶段汇报或代码注释时，默认使用中文；保留必要的英文关键字、API 名称、类型名、函数名和 Gherkin 关键字。

除 Lightweight Mode 明确适用外，确认 gate 不得跳过。

## Gate 0：判断是否适用

在做任何工作前，判断当前任务是否需要修改代码。

- 如果需要代码变更，进入本 skill workflow。
- 如果不需要代码变更，不使用本 workflow。
- 如果用户要求实现但需求不清楚，不写代码；先提出最少必要澄清问题，或给出 best-effort User Story draft 并清楚标注假设。

## Gate 1：User Story Intake

写测试或生产代码之前，必须提取 User Story。

使用此结构：

```text
Title:
As a:
I want:
So that:

Acceptance Criteria:
- AC1:
- AC2:
- AC3:

Business Rules:
- Rule 1:
- Rule 2:

Edge Cases:
- Edge case 1:
- Edge case 2:

Failure Cases:
- Failure case 1:
- Failure case 2:

Dependencies / Integration Points:
- Dependency 1:
- Dependency 2:

Affected Areas:
- Frontend:
- Backend:
- Database:
- API Contract:
- Tauri / Desktop:
- Tests:
```

如果信息缺失，只问最少必要问题。需要澄清的常见内容：

- 用户角色
- 期望结果
- Acceptance Criteria
- 错误行为
- 边界情况
- API contract
- 数据持久化
- 权限规则
- UI 期望
- 现有行为
- 回归风险

如果可以合理假设，必须写明：

```text
Assumptions:
- I assume that...
- I assume that...
```

Gate 1 不允许写测试代码或生产代码。

## Gate 1 输出要求

分析需求后输出：

1. 简洁 User Story。
2. Acceptance Criteria。
3. Business Rules。
4. Edge Cases。
5. Failure Cases。
6. Dependencies and affected modules。
7. 标准 Gherkin BDD scenarios。
8. 确认请求。

除 Lightweight Mode 适用外，输出后必须停止，等待用户确认。

## BDD Scenario 规则

BDD scenarios 必须使用标准 Gherkin 风格，并描述可观察行为，而不是内部实现细节。

使用：

```gherkin
Feature: <feature name>

Scenario: <scenario name>
  Given <initial context>
  When <user action or system event>
  Then <expected observable result>
  And <additional expected result>
```

多个输入共享同一行为时使用 `Scenario Outline`：

```gherkin
Scenario Outline: Reject invalid upload files
  Given the user is on the upload page
  When the user uploads a file with type "<file_type>"
  Then the system should reject the file
  And the user should see "<error_message>"

Examples:
  | file_type | error_message         |
  | exe       | Unsupported file type |
  | empty pdf | File cannot be empty  |
```

优先写：

```gherkin
Then the user should see the parsed document sections
```

避免写：

```gherkin
Then parseDocumentService.parse() should be called once
```

只有当行为无法通过外部结果观察，或直接测试 service-level contract 时，才提到内部 service。

每个 User Story 至少考虑：

- Happy path。
- Important edge case。
- Failure path。如果确实没有失败路径，说明原因。

如果某个场景是 Codex 额外建议而非来自 User Story 或 Acceptance Criteria，标注：

```text
补充建议场景，等待用户确认是否纳入范围。
```

## 测试场景质量规则（Definition of Ready + linter）

> 本节解决一个具体问题：场景"写完了"不等于"能支撑开发"。场景若不在**开写实现之前**满足以下条件，
> 就该退回细化 —— 越晚发现歧义，返工越贵。
>
> 契约优先：**凡场景依赖尚未定稿的契约（接口路径、状态码、协议、口径），不得进入 Gate 2**。
> 这类契约集中在仓库的 `docs/specs/*-contracts.md`（R1 的是 `docs/specs/r1-contracts.md`）；
> 每条待定契约的未决问题最多 3 个，写成 `[NEEDS CLARIFICATION]`。

### Definition of Ready：一条场景必须带齐

1. **稳定 ID**（如 `T-R1-2.1`）与**父 AC 映射**（父 issue / AC 编号）—— 让追溯矩阵能机械计算覆盖率。
2. **GIVEN / WHEN / THEN，且只有一个 When**：多个 `When` 说明这条场景混了多个触发动作，应拆成多条。
   多个 `Then` 只在结果**紧密耦合**时才合法（如"拒绝写入 **并且** 返回 400"）。
3. **断言可外部观察**：用户可见输出、API 响应、数据库持久化、state transition。
4. **通过"对手测试"**：自问 *"一个完全错的实现能不能通过这条断言？"* 能通过 = 断言太虚，重写。
   - ❌ `Then 系统正确响应了` → 什么都通过
   - ✅ `Then 返回 400，且 body 指出缺失字段名`
5. **异常场景数 ≥ happy path 数**：全是 happy path 的场景集合不达标。若某条确实没有失败路径
   （如纯只读查询），显式豁免并写理由：
   `<!-- lint-ack: error-path — 只读查询，无失败路径 -->`（只允许豁免 warning 级，不豁免 error 级）。
6. **测试层级 + 落点文件 + 夹具/替身 + 运行命令**：写清这条场景落在 unit / component / integration / contract
   哪一层，建议文件路径，复用哪些既有 fixture / mock，用什么命令跑。
7. **DoD 勾选**：完成 = **先红后绿** + 覆盖率门槛 + CI 相关 job 绿 + 文档回填。

### 场景 linter（提交前逐条自查）

| 规则 | 触发条件 | 处理 |
|---|---|---|
| `error-path` | 所有场景都是 happy path | 补异常路径，或写 `lint-ack` 理由 |
| `universal-claim` | 出现"所有 / 每个 / 全部"却只有一条场景 | 每个实例至少 2 条场景，或收窄表述 |
| `boundary-entry-point` | 声明了多个入口（REST / CLI / MCP / 前端）但场景只覆盖一个 | 每个入口都要有场景，或显式说明本次只覆盖哪个 |
| `vague-verb` | improve / enhance / handle / 优化 / 处理好 | 换成可计数、可断言的结果 |
| `unquantified` | "快 / 稳定 / 可用"没有阈值 | 给出数字与判定口径 |
| `implicit-dep` | 场景没绑定测试落点（`Test:` 选择器 / 文件） | 补落点，否则无法算覆盖 |
| `testability` | 无法从外部观察 | 改断言对象或改测试层级 |
| `decision-coverage` | 已定的设计决策没有对应场景 | 补场景，或把决策降级为 `[NEEDS CLARIFICATION]` |

### 追溯矩阵（AC ID → 测试）

交付一个 User Story 前，产出并更新一张矩阵，字段固定：

```text
AC-ID | 描述 | test issue / 场景 ID | 测试文件 | 测试函数 | 状态(covered/partial/uncovered/not_implemented)
```

- 状态语义：`covered` 全部条件有断言；`partial` 缺边界/路径；`uncovered` 有实现无测试引用；
  `not_implemented` 实现本身还没做（与 uncovered 区分开，前者是有意排期，后者是漏）。
- **`not_implemented` 不是漏项，但必须在矩阵里可见** —— 否则"以为测了"会一直隐瞒到线上。
- 覆盖率公式（供参考）：`(covered + partial × 0.5) / (total_ac − not_implemented)`。

## Gate 1 确认

BDD scenarios 后必须询问：

```text
Please confirm whether these User Story details and BDD scenarios are correct.
After confirmation, I will write the tests first before implementing production code.
```

确认前不进入测试阶段，除非 Lightweight Mode 明确适用。

## Gate 2：测试计划与测试先行

Gate 1 确认后，先创建 test plan，再写或更新测试。

Test plan 应识别：

```text
Test Plan:
- Unit tests:
- Integration tests:
- Component tests:
- Contract tests:
- E2E tests, only if necessary:
- Existing tests to update:
- Fixtures / mocks to reuse:
- Test command to run:
```

选择能可靠验证行为的最小测试层级。不要在 unit、component、integration 或 contract test 足够时默认添加 E2E。

### Gate 2 允许做的事

- 查找项目已有测试框架、目录和风格。
- 创建或修改测试文件。
- 创建必要 fixture 或 mock 数据。
- 运行相关测试确认 Red stage。
- 汇报测试失败原因。

### Gate 2 禁止做的事

用户确认测试代码前，不允许：

- 修改生产代码。
- 为了让测试通过而实现功能。
- 重构无关代码。
- 修改数据库结构。
- 改动与测试无关的配置。

## Gate 2：Red Stage 要求

必须先写或更新测试，再写生产代码。

写完测试后，尝试运行相关测试。预期结果是 Red：

```text
Expected Red Stage:
- The new or updated test should fail.
- The failure should happen for the expected reason.
- The failure should prove the required behavior is not implemented yet.
```

如果测试没有失败，必须说明原因：

```text
Red Stage Result:
- Did the test fail? Yes / No
- If no, why?
  - Existing code already satisfies the behavior
  - Test does not properly cover the new behavior
  - Test command could not run
  - Environment issue
  - Other:
```

如果测试意外通过，检查测试是否有意义，不要盲目继续。

## Gate 2 确认

写完测试并尝试确认 Red stage 后，停止并询问：

```text
The tests have been added/updated and the Red stage has been checked.
Please confirm before I implement the minimal production code.
```

确认前不写生产代码，除非 Lightweight Mode 明确适用。

## Gate 3：最小生产实现

Gate 2 确认后，只实现让测试通过的最小生产代码。

规则：

- 不要 over-engineer。
- 不要引入无关抽象。
- 不要不必要地重写大块代码。
- 不要改变 public API，除非 User Story 要求。
- 不要改变数据库 schema，除非 Acceptance Criteria 要求。
- 不要添加新依赖，除非有明确理由。
- 保持变更局部；如果影响面不可避免扩大，解释原因。

目标是 Green，不是完美。

## Gate 3：Green Stage 要求

实现后运行相关测试。

预期结果：

```text
Expected Green Stage:
- New or updated tests pass.
- Relevant existing tests still pass.
- No unrelated behavior is broken.
```

如果测试失败，诊断失败原因并做最小修正。不要隐藏失败测试。没有运行测试时，不得声称成功；必须说明原因。

## Gate 4：Refactor

只有测试 green 后才能 refactor。

Refactor 规则：

- 保持可观察行为不变。
- 保持 tests green。
- 只改善清晰度、重复、命名或结构。
- 避免把大重构和功能变更混在一起。
- 不做 speculative refactor。

Refactor 后再次运行相关测试。

## Lightweight Mode

非常小的任务可以使用 Lightweight Mode，但必须同时满足：

- 只影响一到两个文件。
- 行为已经清楚。
- Acceptance Criteria 显而易见或已明确给出。
- 不影响数据库 schema。
- 不影响 API contracts。
- 不影响 authentication、payment、security 或 permissions。
- 用户明确表示要快速处理或不需要确认。

示例：

- 修正测试名 typo。
- 增加一个缺失 assertion。
- 修复简单 null check。
- 更新一个预期输出清楚的小组件行为。
- 为清楚 bug 添加 regression test。

即使使用 Lightweight Mode，也必须：

1. 声明假设行为。
2. 实际可行时先写或更新测试。
3. 实现最小修复。
4. 尽可能运行相关测试。
5. 汇报跳过了什么以及原因。

Lightweight Mode final summary 必须包含：

```text
Lightweight Mode used because:
- Reason:

Skipped gates:
- Gate 1 confirmation
- Gate 2 confirmation

Verification:
- Tests run:
- Result:
```

## 测试质量规则

测试应验证可观察行为，不优先验证内部实现。

优先断言：

- 用户可见输出
- API responses
- 数据库持久化结果
- domain/service return values
- state transitions
- error messages
- integration boundaries
- contract 中规定的文件或 side effects

避免断言：

- private methods
- temporary variables
- internal component structure
- implementation-specific call order
- unimportant mock interactions
- CSS class names，除非它是 public contract
- 大型不稳定 UI tree 的 snapshot tests

Mocks 和 spies 适合验证边界交互：

- External API calls
- File system writes
- Email sending
- Tauri command boundaries
- Database repository boundaries
- Message queue or event publishing
- Time、randomness 或 environment-dependent behavior

## 测试选择策略

选择最低但可靠的测试层级。

### Unit Tests

用于：

- Pure business logic
- Domain rules
- Validation
- Data transformation
- Error handling
- Service-level decisions

### Component Tests

用于：

- React component behavior
- User interactions
- Conditional rendering
- Form validation
- Loading、empty、error states

### Integration Tests

用于：

- Service + repository behavior
- API route + database behavior
- Persistence behavior
- Cross-module coordination

### Contract Tests

用于：

- Frontend/backend API compatibility
- Tauri command payloads
- Request/response schema
- Error response format

### E2E Tests

仅在必要时用于：

- Critical user journeys
- Cross-boundary workflows
- 无法在更低层级可靠测试的 regression coverage

不要默认写 E2E。

## 项目上下文

除非仓库显示不同情况，假设当前项目可能包括：

- Frontend: React + TypeScript
- Desktop shell: Tauri
- Backend: FastAPI
- Database: SQLite
- Vector search: sqlite-vec
- Architecture: Service / Repository separation
- Tests: frontend tests、backend tests、integration tests、selected E2E tests

功能可能包括：

- 上传课程资料
- 解析 PDF / image / 文本
- 生成 DocumentRecord
- 生成 DocumentUnit
- PageIndex
- RAG
- 章节分析
- 结构化学习报告
- 学习待办清单
- 继续追问
- 导出结果

始终先检查仓库约定，再添加新模式。遵循已有命名、文件位置、fixture 风格、mock 风格和测试命令。已有测试框架存在时，不要引入新测试框架。

## Frontend Testing Guidance

React + TypeScript 改动优先行为导向测试。

Component tests 适合：

- Rendering expected content
- User interactions
- Form validation
- Disabled/enabled states
- Loading states
- Error states
- Empty states

优先使用 user-facing queries：

```ts
screen.getByRole(...)
screen.getByText(...)
screen.getByLabelText(...)
```

避免 brittle selectors，除非没有 accessible query。不要过度使用 snapshots。测试 async UI 时使用：

```ts
await screen.findByText(...)
await waitFor(...)
```

## Backend Testing Guidance

FastAPI 改动优先通过 route/client tests 验证外部可观察行为。

测试：

- Status codes
- Response body
- Error format
- Validation behavior
- Authentication / authorization behavior，如果相关
- Database persistence
- Service-layer side effects

Service logic 不需要 API 层时使用 unit tests。Repository persistence 行为重要时，使用 test database 的 integration tests。

## Database Testing Guidance

SQLite / sqlite-vec 相关 User Story 依赖以下行为时，要测试数据库行为：

- Insert/update/delete behavior
- Query filtering
- Sorting
- Search ranking
- Vector retrieval
- Migrations
- Constraints
- Transactions
- Cascade behavior

不要随意改 schema。schema change 必须包含：

```text
Schema Change Justification:
- User Story requirement:
- Migration required:
- Backward compatibility:
- Data migration needed:
- Tests covering migration:
```

## Tauri Testing Guidance

Tauri 或 desktop integration 优先测试 command contracts 和 boundary behavior。

验证：

- Command input payload
- Command output payload
- Error response structure
- Frontend invocation behavior
- Backend command handling

除非低层级无法可靠测试该 workflow，不要默认 full desktop E2E。

## API Contract Rules

修改 API contract 时必须明确记录：

```text
API Contract Change:
- Endpoint / command:
- Request change:
- Response change:
- Error format change:
- Backward compatibility:
- Frontend impact:
- Backend impact:
- Tests added:
```

不要静默改变 response shape。

## Error Handling Rules

失败路径测试应覆盖：

- Invalid input
- Missing input
- Unauthorized access，如果相关
- Forbidden access，如果相关
- Not found
- Conflict
- External dependency failure
- Database failure，实际可行时
- Empty result
- Timeout or cancellation，相关时

错误信息应有用，但不得泄露敏感内部信息。

## Refactoring Rules

Refactor 任务先用测试刻画当前行为，除非已有足够测试。

Refactor workflow：

1. 识别当前可观察行为。
2. 必要时添加 characterization tests。
3. Refactor 前确认 tests pass。
4. 小步 refactor。
5. 每个有意义步骤后运行测试。
6. 未明确要求时不要改变行为。

如果 refactor 改变行为，把它当作 feature 或 bug fix，回到完整 BDD/TDD workflow。

## Bug Fix Rules

Bug fix 先用 failing test 复现 bug。

Bug fix workflow：

1. 描述 expected behavior vs actual behavior。
2. 写一个会失败的 regression test。
3. 确认失败是预期原因。
4. 实现最小修复。
5. 确认 regression test passes。
6. 运行相关 existing tests。

Bug report template：

```text
Bug:
- Expected:
- Actual:
- Reproduction:
- Root cause hypothesis:
- Regression test:
```

## User Story Output Template

Gate 1 使用：

````text
## User Story

Title:

As a:
I want:
So that:

## Acceptance Criteria

- AC1:
- AC2:
- AC3:

## Business Rules

- Rule 1:
- Rule 2:

## Edge Cases

- Edge case 1:
- Edge case 2:

## Failure Cases

- Failure case 1:
- Failure case 2:

## Dependencies / Integration Points

- Dependency 1:
- Dependency 2:

## Affected Areas

- Frontend:
- Backend:
- Database:
- API Contract:
- Tauri / Desktop:
- Tests:

## BDD Scenarios

```gherkin
Feature:

Scenario:
  Given
  When
  Then
```

## Assumptions

- Assumption 1:
- Assumption 2:

## Confirmation Required

Please confirm whether this User Story and these BDD scenarios are correct.
After confirmation, I will write the tests first before implementing production code.
````

## Test Plan Output Template

Gate 2 使用：

```text
## Test Plan

Unit tests:
-

Component tests:
-

Integration tests:
-

Contract tests:
-

E2E tests:
- Not needed unless...

Existing tests to update:
-

Fixtures / mocks to reuse:
-

Test command:
-

## Red Stage Result

Test files added/updated:
-

Command run:
-

Result:
- Failed as expected / Passed unexpectedly / Could not run

Failure reason:
-

Next step:
Please confirm before I implement the minimal production code.
```

## Final Summary Template

实现后使用：

```text
## Summary

Implemented:
-

Tests added/updated:
-

Files changed:
-

BDD scenarios covered:
-

Verification:
- Command:
- Result:

Red-Green-Refactor:
- Red:
- Green:
- Refactor:

Notes:
-

Limitations / Not run:
-
```

## Strict Prohibitions

不得：

- 在 BDD scenarios 确认前写生产代码，除非 Lightweight Mode 适用。
- 在测试写好前写生产代码，除非不可能或明确说明理由。
- 静默跳过 Red stage。
- 没有运行测试却声称测试通过。
- 默认添加 broad E2E tests。
- 没有明确需要就修改数据库 schema。
- 静默修改 API contracts。
- 引入无关 refactors。
- 无理由添加 dependencies。
- 修改大范围无关区域。
- 隐藏不确定性。
- 编造 User Story 不支持的需求。

## 显式调用示例

```text
Use the bdd-tdd-implementer skill to implement the following User Story:

US#1: 上传 PDF 后创建 DocumentRecord 和 DocumentUnit，并允许用户选择章节进行分析。

Acceptance Criteria:
- Given 用户已经进入文档上传页面
- When 用户上传一个有效 PDF 文件
- Then 系统应该创建一个 DocumentRecord
- And 系统应该从 PDF 中解析出 DocumentUnit
- And 用户应该能看到可选择的章节或片段
```

Codex 应先执行 User Story Intake，总结对 US 的理解，然后生成 BDD scenarios。生成 BDD scenarios 后必须停止等待用户确认。用户确认后才能写测试代码。测试代码写完并检查 Red stage 后再次停止等待用户确认。用户再次确认后才能写最小生产实现。
