# US · 阶段 1 · 界面接入：真实问答 / 会话持久化 / 模型配置

> **状态：已实现（2026-09-13）**
> 这一批把链路从"能跑"推到"界面能用"：断开的地方都在**界面侧** ——
> 问答没接后端、会话不落库、模型没法激活、刷新后看不到历史。
> 前置：[`us-stage1-chat.md`](us-stage1-chat.md)（后端问答闭环）、[`us-stage1-ingest.md`](us-stage1-ingest.md)

---

## 1. 这一批补齐的空白

| 位置 | 之前 | 现在 |
|---|---|---|
| `src/lib/apiClient.ts` | **1 行占位**（`upload.ts` 自带一份 base URL 与错误解析） | base URL / JSON 请求 / `ApiError` 错误映射；`upload.ts` 改为复用 |
| `src/features/chat/api/chatApi.ts` | **1 行占位** | `POST /api/chat` + `GET /api/chat/sessions/{id}/messages` 封装（snake_case → camelCase） |
| `src/features/chat/sessionStore.ts` | 不存在 | 会话 ID 的本地保存（存储不可用时降级为内存会话） |
| `src/features/workspace/components/right/ChatPanel.tsx` | 回答纯文本，错误不可见 | 来源条目可点击高亮；后端错误用 `role="alert"` 显示 |
| `src/features/workspace/pages/WorkspacePage.tsx` | `SEND_CHAT_MESSAGE` 生成**本地模拟回复**；会话 ID 每次打开都新生成 | 真实链路：乐观追加用户消息 → 调后端 → 追加带来源的回答；打开时按本地会话 ID 恢复历史 |
| `app/services/chat_service.py` | 回答后不落库 | 回答成功后由 `ChatSessionService` 落 `chat_sessions` / `chat_messages` |
| `app/api/provider_controller.py` | 类风格、**未接路由**（无法激活模型） | `APIRouter` 注册进 `main.py`：`/api/providers` |
| `src/features/provider/` | 不存在 | `providerApi.ts` + `ProviderPanel`（「设置」齿轮打开） |

## 2. Acceptance Criteria

**C1 · 前端接入真实问答**

- **AC1**：发送消息调用 `POST /api/chat`（带 `session_id` / `query` / `history` / `use_extended_context` / `workspace_id`），渲染返回的 `answer`。
- **AC2**：`source_context` 渲染为「来源 N · 第 M 页」条目，点击高亮（`aria-pressed`）。
- **AC3**：请求进行中 `loading=true`，发送按钮禁用。
- **AC4**：失败可见 —— 503 → 后端文案（"尚未配置可用模型"）；连不上后端 → "无法连接后端服务"；空白输入不发请求。
- **AC5**：`ChatResponse.usage`（回答那次调用的 token）累加到面板；provider 不回传时为 `null`（**API 契约变更**）。

**C1b · 前端恢复会话历史**

- **AC15**：会话 ID 存在本地（`localStorage`），刷新后复用同一个；存储不可用（隐私模式抛异常）时降级为内存会话，**不抛错、不崩界面**。
- **AC16**：打开工作区时按该 ID 拉取历史，并按后端给的顺序渲染（用户 / 助手交替）。
- **AC17**：历史里助手消息的来源从 `source_context_json.sources` 还原为可点击条目。
- **AC18**：会话不存在（**404**）→ 按"没有历史"处理，**不显示错误**（首次打开就是这种情况）。
- **AC19**：其他失败（连不上后端 / 5xx）→ 把错误显示出来（否则用户不知道后端不通）。
- **AC20**：历史拉取不阻塞提问（不参与发送按钮的 `loading`）。

**C2 · 会话与消息持久化**

- **AC6**：首次用某 `session_id` 提问自动建会话；重复使用复用，**不覆盖**历史。
- **AC7**：每轮落 user / assistant 各一条；助手那条带 `{"sources": [...]}`（`source_context_json`）。
- **AC8**：`GET /api/chat/sessions/{session_id}/messages` 按时间升序返回；会话不存在 → **404**。
- **AC9**：`workspace_id` 缺省为 `"default"`（与前端常量一致）。
- **AC10**：**回答失败不落库**；落库自成事务（SQLite 单写者）。

**B · 模型配置接 HTTP**

- **AC11**：`/api/providers` 提供列表 / 单个 / 新增 / 更新 / 删除 / 激活 / 当前激活。
- **AC12**：响应**永不包含 `api_key`**；`name` 重复 → **409**；不存在 → **404**。
- **AC13**：激活后 `ProviderRegistry.get_active()` 可拿到实例 —— 即 `POST /api/chat` 不再 503。
- **AC14**：界面「设置」可列出配置、新增、激活；面板关闭回到工作区。

## 3. 关键设计决策

- **落库时机**：放在回答**成功之后**、独立事务（`asyncio.to_thread`）。
  SQLite 单写者，不能在检索的读事务里写别的表 —— 与 [`us-stage1-trace.md`](us-stage1-trace.md) §3.4 同类坑。
- **来源的存储形状**：实体 `source_context_json` 是 `dict`，来源本身是列表，故存成 `{"sources": [...]}`（不改实体）。
- **命名口径**：`chatApi.ts` 在 api 层一次性把 snake_case 转成 camelCase（含助手角色 `agent` → `assistant`）；
  `upload.ts` / `providerApi.ts` 直接沿用 snake_case。两者各自内部一致，组件不会同时见两套命名。
- **会话 ID 的持久化**：放 `sessionStore.ts` 而不是组件里 —— 它要能被单测直接覆盖，
  且"存储不可用就降级为内存会话"这条兜底逻辑不该混在渲染逻辑里。
  读取时**以持久化存储为准**（存储里没有就当作没有会话），内存值只服务于存储不可用这一种情况。
- **404 不是错误**：首次打开时后端还没有这个会话，属于正常路径；只有网络 / 5xx 才算错误。
- **不删类**：`ProviderController` 被既有测试与 provider workflow 使用，保留；新路由与它共用
  `to_provider_response()` / `to_activate_response()`，**没有第二份响应映射逻辑**。
- **`api_key` 不回传**：`ProviderConfigResponse` 本就没有该字段；集成测试额外断言响应文本里不出现密钥值。

## 4. 实测（2026-09-13，本机）

| 命令 | 结果 |
|---|---|
| `npx vitest run` | **289 passed / 19 个文件** |
| `npm run test:python:coverage` | **450 passed / 覆盖率 100.00%** |

新增测试：`src/lib/apiClient.test.ts`、`src/features/chat/api/chatApi.test.ts`、
`src/features/chat/sessionStore.test.ts`、`src/features/provider/api/providerApi.test.ts`、
`src/features/provider/components/ProviderPanel.test.tsx`、
`src/features/workspace/pages/WorkspacePage.chat.test.tsx`、`WorkspacePage.history.test.tsx`、
`WorkspacePage.settings.test.tsx`、`backend-python/tests/integration/api/test_provider_api.py`，
以及 `test_chat_flow.py` 的会话持久化章节。

> ⚠️ 写 `WorkspacePage.*.test.tsx` 时 **必须缓存 `framer-motion` mock 的组件类型**：
> 每次 `get` 都新建函数会让 React 重建整棵 DOM 子树，"先 `change` 再 `keyDown`"就作用在
> 已脱离文档的旧节点上，交互静默失效。详见 `AGENTS.md` 的"当前注意事项"。
>
> ⚠️ 挂载即拉历史之后，**不能再假设 `fetchMock.mock.calls[0]` 就是提问那一次**：
> 测试要按 URL / method 找调用（`WorkspacePage.chat.test.tsx` 里的 `findAskCall`）。

## 5. 未做（待办）

1. **引用只到"来源条目"**：点来源目前只做高亮，跳到 PDF 具体页需要新的"文档单元内容查询"接口。
2. **`provider_configs.api_key` 仍是明文存 SQLite**：响应层已脱敏，但库里是明文，加密存储未做。
3. **文档正文与左侧文件列表仍是本地 mock**：接真数据同样需要上面的"文档单元内容查询"接口。
4. **没有"新建会话"入口**：会话 ID 一直复用，历史只增不减 —— 需要时得清掉本地存储（`greenbean.chat.session_id`）
   才会开新会话；界面上目前没有按钮。
