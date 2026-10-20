# MCP server 无状态核验（规范修订 2026-07-28）

> 核验日期：2026-10-20。环境：`mcp==2.3.0`（`mcp.server.mcpserver.MCPServer`），stdio 传输。
> 核验方式：**两个探针脚本 + 静态代码审计**，不是读文档推测。复现命令见 §6。
> 结论先行：**协议层已无状态化，双栈兼容**；发现 **2 处真实缺陷**、**2 处口径不一致**，均待拍板后再改。

---

## 1. 结论（三行）

1. **符合**：不握手即可 `tools/list`，同连接与跨连接结果一致，`server/discover` 已实现且只声明 `2026-07-28`。
2. **不符合**：① 工具错误在协议层是 `isError: false`（被包成文本），程序化客户端无法识别失败；② MCP 路径**没有工具超时**（`TOOL_TIMEOUT_SECONDS` 只在 chat_agent 生效）。
3. **待观察**：`workspace_id` 默认 `""` 的语义是"不过滤全部工作区"，与 HTTP 侧 `DEFAULT_WORKSPACE_ID="default"` 口径不同 —— 单工作区无害，R1-5 多工作区时会变成跨区可见。

---

## 2. 规范要点（2026-07-28 相对 2025-11-25）

| 变化 | 内容 | 对我们的含义 |
|---|---|---|
| 删协议级会话 | 移除 `Mcp-Session-Id`，list 端点不再因连接而异 | 可在无粘性路由后多副本部署 |
| 删握手 | 移除 `initialize` / `notifications/initialized`；每请求在 `_meta` 自带 `protocolVersion`、`clientCapabilities` | 客户端不必先握手；版本不匹配回 `UnsupportedProtocolVersionError` |
| 新增 `server/discover` | 服务端必须实现，播报版本/能力/身份 | 客户端可先探测再选版本 |
| 变更推送 | `subscriptions/listen` 单条长 POST 响应流，按类型 opt-in | 取代 GET + `resources/subscribe` |
| 跨调用状态 | 用 server-minted handle 当普通工具参数 | 状态显式化、可审计、可过期 |

SDK 侧证据：`mcp/server/_streamable_http_modern.py`（"Single-exchange HTTP serving for protocol version 2026-07-28"）、
`mcp/shared/subscriptions.py`（"Typed event vocabulary for subscriptions/listen (2026-07-28)"）、
`mcp/client/client.py:338`（client `auto` 模式"probes `server/discover` and falls back to the initialize handshake on legacy servers"）。

---

## 3. 探针结果（真实输出）

### 3.1 modern 路径：不握手直接调用

| 断言 | 输入 | 结果 | 判定 |
|---|---|---|---|
| **A1** 无 `initialize` 能否 `tools/list` | `_meta.protocolVersion=2026-07-28` | `result.tools` 返回 **6 个工具**：`chunk_search_tool` / `document_retrieval_tool` / `section_context_tool` / `analysis_result_tool` / `quiz_generation_tool` / `todo_generation_tool`，另带 `cacheScope: private`、`resultType: complete` | ✅ 无状态生效 |
| **A2** 同连接两次 `tools/list` 逐字一致 | 连续两次调用 | `同连接两次一致: True` | ✅ list 不随连接变化 |
| **A3** `server/discover` | 同 `_meta` | `supportedVersions: ["2026-07-28"]`、`capabilities`（tools/prompts/resources，含 `listChanged`）、`_meta.serverInfo`（name/title/version/description） | ✅ 已实现 |
| **A4** 工具失败时的协议语义 | `quiz_generation_tool(context_text="")` | `isError: false`，`content[0].text = {"success": false, "error": "ValueError: context_text cannot be empty"}`；`structuredContent.result` 是**同一段 JSON 的字符串**（二次编码） | ❌ 见 §4-F1 / F2 |

### 3.2 老客户端（legacy 握手）兼容性

| 断言 | 输入 | 结果 | 判定 |
|---|---|---|---|
| **C1** `initialize(protocolVersion=2025-11-25)` | legacy 握手 | 成功返回 `protocolVersion: 2025-11-25`、`serverInfo`，能力降级为 `listChanged: false, subscribe: false` | ✅ 双栈兼容 |
| **C2** `initialized` 后 legacy `tools/list` | 同上 | 返回 6 个工具 | ✅ 老客户端可用 |
| **B1/B2** 跳过握手直接发 legacy 请求 | 无 `_meta` 的 `tools/list` / `server/discover` | `-32602 Invalid request parameters` / `-32601 Method not found` | ✅ 符合预期（legacy 线必须先握手；modern 线必须带 `_meta`） |

**推论**：B1 不是缺陷。SDK 2.3.0 是**双栈**：modern 线（无状态、`_meta` 自描述）与 legacy 线（握手）并存，
我们两条都通。审计文档里必须写清这一点，否则容易被误读成"不兼容老客户端"。

---

## 4. 发现（按严重度）

### F1 · 工具错误在协议层不可见（中）

- **现象**：`isError: false`，错误只体现在工具返回的**文本内容**里。
- **成因**：`app/mcp_server.py:77-87` 的 `_run()` 捕获所有异常并返回 `{"success": false, ...}` 的 JSON 文本；
  注释里写明这是为了避免 mcp 2.x 把异常抛成 `UnexpectedToolError`（传输层错误）。
- **影响**：
  - 对**模型**：可读、可自愈（模型能看到错误并换参数），这是原设计的收益，保留；
  - 对**程序化客户端**（编排器、监控、自动化测试）：无法区分"调用失败"与"成功但内容里含 success:false"，无法做重试/告警。
- **处置建议**（待拍板，二选一）：
  - 方案 A：**参数类错误**（缺参、空值、非法 ID）抛 `MCPError`/让 SDK 标记 `isError: true`；**领域类失败**（无资料、模型未配）仍返回 JSON 文本。
  - 方案 B：保持现状，在描述里声明"所有结果形如 `{success, data|error}`"，要求调用方按 `success` 判断。
  - 我倾向 A：协议层语义与 LLM 可读性各归其位。

### F2 · `structuredContent` 双重编码（低）

- **现象**：`outputSchema` 把 `result` 声明为 `string`，于是 `structuredContent.result` 是 JSON 的字符串，客户端要二次 `json.loads`。
- **影响**：程序化消费别扭；不影响模型。
- **处置建议**：让工具返回 `dict` 而不是 `json.dumps(...)` 字符串，让 SDK 生成结构化 `structuredContent`（需确认 SDK 对 dict 返回值的 schema 推导行为，先写 spike 再改）。

### F3 · MCP 路径没有工具超时（中）

- **现象**：`TOOL_TIMEOUT_SECONDS = 10.0`（`app/config/settings.py:64`）**只在** `app/agents/chat_agent.py` 生效；
  `_run()` 直接 `await tool.run(...)`，无超时、无取消。
- **影响**：检索/模型调用挂住时，MCP 会话一起挂住（客户端只能断开）；与"有界工具循环"的承诺不一致。
- **处置建议**：在 `_run()` 里用 `asyncio.timeout(TOOL_TIMEOUT_SECONDS)`（Python 3.11+），超时返回 `{"success": false, "error": "timeout"}`；
  加一条测试：注入一个 sleep 的假工具，断言 ≤ 超时 + 少量余量返回。

### F4 · `workspace_id` 默认值口径不一致（中，多工作区前必须定）

- **现象**：
  - MCP：`chunk_search_tool(workspace_id: str = "")`、`todo_generation_tool(content_summary, workspace_id: str = "")`（`app/mcp_server.py:45,71`）；
  - 语义：`ProductionChunkSearcher.search()` 里 `workspace_id.strip() or None`（`app/tools/adapters.py:72`），
    文档字符串明写"`workspace_id` 为空 = 不按 workspace 过滤"（`:54`）；
  - HTTP 侧：上传/会话缺省统一到 `DEFAULT_WORKSPACE_ID = "default"`（`app/config/settings.py:16`，R1-2 的成果）。
- **影响**：
  - 单工作区：无害（只有一份数据）；
  - **多工作区（R1-5）**：MCP 客户端不传 `workspace_id` 时能看到全部工作区的片段 —— 这是**跨区可见**，不是"不过滤"这种中性说法。
- **处置建议**：MCP 层缺省改为 `DEFAULT_WORKSPACE_ID`，并把"要跨区检索"做成显式参数（`all_workspaces: bool = False`）或显式传 `"*"`。
  这会改变工具 schema（新增语义），需要一条测试锁住"不传 = 只看 default"。

### F5 · 工具缺少注解与"何时别用"（低）

- **现象**：6 个工具只有一行英文描述（来自各工具类的 `description`），无 `readOnlyHint`/`destructiveHint`，无输出大小上限提示，无"何时不该用"。
- **影响**：客户端无法按权限渲染/拦截；模型选工具的准确率取决于描述质量。
- **处置建议**：给只读工具加 `readOnlyHint=True`；给两个**会花钱**的生成工具在描述里写明"调用会产生模型费用"；描述补一句反例（"不要用它回答事实性问题，用 chunk_search_tool"）。

---

## 5. 八项静态审计（逐条结论）

| # | 审计项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 工具是否有隐藏全局可变状态 | ✅ 无（工具实例由 `build_tools()` 一次性装配，检索/嵌入懒加载；无模块级可变缓存） | `app/tools/factory.py`、`app/tools/adapters.py:80-84` |
| 2 | `tools/list` 是否不依赖请求 | ✅ 是（A2/B 均一致；无请求上下文参与） | 探针 A2、C2 |
| 3 | 每个工具是否自带完整默认值 | ⚠️ 部分（有默认值，但 `workspace_id=""` 的语义与 HTTP 不同，见 F4） | `mcp_server.py:45,71` |
| 4 | 幂等性是否明确 | ❌ 未声明（检索类天然只读；两个生成类每次调用都会花钱且结果不同，描述里没写） | `app/tools/*.py` 描述 |
| 5 | 错误是否映射为 `isError` | ❌ 否（统一包成 JSON 文本） | F1；`mcp_server.py:77-87` |
| 6 | 描述是否说明"何时该用/不该用"+ 返回大小 | ❌ 否（仅一行英文描述） | F5 |
| 7 | MCP 路径是否有超时 | ❌ 否（超时只在 chat_agent 内） | F3；`settings.py:64` vs `chat_agent.py:18` |
| 8 | 与 `DEFAULT_WORKSPACE_ID` 是否一致 | ❌ 否（默认 `""` = 不过滤） | F4 |

---

## 6. 复现命令

```bash
cd C:/Users/swkgb/Documents/repos/greenbean-study-assistant-personal

# 依赖与协议版本
.venv/Scripts/python.exe -m pip show mcp | head -3        # mcp==2.3.0
grep -rn "2026-07-28" .venv/Lib/site-packages/mcp/shared/subscriptions.py

# 探针（脚本在临时目录，只读，不写库）
.venv/Scripts/python.exe <probe1>.py    # A1-A4 + B1-B3
.venv/Scripts/python.exe <probe2>.py    # C1-C3（legacy 握手）
```

探针脚本内容见 PR 描述（未入库：它们会启动子进程，不属于 `app/` 覆盖率路径；若要入库应放 `scripts/` 并标记 `no cover`）。

---

## 7. 不修的理由（本周）

| 项 | 为什么不这周改 |
|---|---|
| F1 `isError` | 会改变工具契约（两个生成工具 + 6 条测试），需要先定"参数错误 vs 领域失败"的边界 |
| F2 双重编码 | 依赖 SDK 对 dict 返回值的 schema 推导，先写 20 行 spike 验证再改 |
| F3 超时 | 改动小，但会与 chat_agent 的超时策略重复；应抽成共用的 `run_with_timeout()` |
| F4 工作区默认 | **产品语义决策**：不传 `workspace_id` 到底该看"全部"还是"当前工作区"，属于 R1-5 契约，需拍板 |
| F5 注解 | 需要先确认目标客户端（Cursor / Claude Desktop）读不读 annotations，避免写完没人用 |

> 本周的产出是**把问题变成有证据的清单**，不是把所有问题都改掉。改 F3/F4 会动契约，等拍板。

---

## 8. 待拍板（两条）

1. **F1**：错误走协议层 `isError`（方案 A），还是维持 JSON 文本约定（方案 B）？
2. **F4**：MCP 不传 `workspace_id` 时，默认看 `default` 工作区（安全）还是全部（方便）？
