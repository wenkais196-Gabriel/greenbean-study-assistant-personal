# US · 阶段 2 · 把 `tools/` 按 MCP 协议暴露成 stdio server

> **状态：已实现（2026-09-13）**
> 验收：`python backend-python/scripts/run_mcp_server.py` 起一个 stdio MCP server；
> 六个工具可被 MCP 客户端发现并调用，工具异常被包成 `{"success": false, ...}` 文本，不炸传输层。
> 前置：[`us-stage2-tools-wiring.md`](us-stage2-tools-wiring.md)（工具已接生产）、[`us-stage2-agent-tool-loop.md`](us-stage2-agent-tool-loop.md)（Agent 已会调用同一批工具）

---

## 1. 这一批补齐的空白

规划（`planning/11` §4.1）把 MCP 列为"第二优先、成本 3–5 天、简历辨识度最高"的补强：
工具此前只是"Python 函数"，本批把它们升级为"可被 Claude Desktop / Cursor 直接调用的 MCP 工具"。

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/mcp_server.py` | **不存在** | `build_server()` 用官方 `mcp` SDK 构造 `MCPServer`，注册 6 个工具 |
| `backend-python/scripts/run_mcp_server.py` | **不存在** | stdio 入口（`build_server().run(transport="stdio")`） |
| `backend-python/requirements.txt` | 无 `mcp` | 新增 `mcp>=2.0,<3`（官方 Python SDK） |
| `app/tools/factory.py` | 已就绪 | 复用 `build_tools()` 装配，MCP 层零业务逻辑 |

## 2. Acceptance Criteria

- **AC1**：`build_server()` 构造 `MCPServer`（name = `greenbean-study-assistant`），注册 6 个工具：
  `chunk_search_tool` / `document_retrieval_tool` / `section_context_tool` /
  `analysis_result_tool` / `quiz_generation_tool` / `todo_generation_tool`。
- **AC2**：每个 MCP 工具转发到 `build_tools()` 装配出的对应生产工具，返回 JSON 文本（工具原生的 `{"success": ...}` 形状）。
- **AC3**：工具执行抛错 → 包成 `{"success": false, "error": "<Type>: <msg>"}` 文本返回，**不冒泡到 MCP 传输层**
  （mcp 2.x 实测会把工具异常抛成 `UnexpectedToolError`，对客户端是传输层故障）。
- **AC4**：输入 schema 由函数签名生成：`chunk_search_tool` 的 `query` 必填，`workspace_id` / `top_k` 可选。
- **AC5**：`build_server(toolset=None)` 默认走生产装配；**构造时不碰磁盘、不加载模型**（嵌入服务与数据库都是懒加载）；测试可注入假 `ToolSet`。
- **AC6**：测试全部离线 —— 直接调 `await server.list_tools()` / `await server.call_tool(...)`，不起真 stdio 进程。
- **AC7**：`pytest --cov=app --cov-config=tests/.coveragerc` → **506 passed / 100.00%**。

## 3. 分层与实现要点

```
MCP 客户端（Claude Desktop / Cursor）
   └─ JSON-RPC over stdio
        └─ scripts/run_mcp_server.py   ← 唯一的入口：启动 + 阻塞，不占 app/ 覆盖率
             └─ app/mcp_server.py::build_server()
                  ├─ MCPServer(name, description, version)
                  └─ _register_tools(server, toolset or build_tools())
                        └─ 6 个 @server.tool(...) 包装函数 → await _run(tool, **kwargs)
```

要点：

- **MCP 层只做协议翻译**：业务工具、生产装配都不动，`build_tools()` 原样复用。
- **`_run()` 是唯一的异常边界**：工具返回 dict 就 `json.dumps`；工具抛异常就包成 failure JSON。
- **入口放 `scripts/` 而不是 `app/`**：stdio 启动会阻塞进程，放 `app/` 里就会制造"测不到的代码路径"。
- **依赖选型**：官方 `mcp` SDK（2.x）。已实测其 `MCPServer.list_tools()` / `call_tool()` 可以直接离线调用，
  这决定了测试不需要起真进程。2.x 的迁移点（`FastMCP` 改名 `MCPServer`、字段 snake_case）已踩过并写进测试。
- **六个工具全部暴露**：quiz / todo 没有 provider 时会返回 `not configured` —— 这是 MCP 调用方**应当看到**的信息，不是服务器故障。

## 4. 验收实测（2026-09-13）

| 项 | 结果 |
|---|---|
| `pytest --cov=app --cov-config=tests/.coveragerc` | **506 passed / 100.00%** |
| 前端 `npm run test:frontend` | 293 passed / 19 文件（未改前端，回归） |
| `list_tools()` | 返回 6 个工具，名字与描述齐全 |
| `call_tool("chunk_search_tool", {"query","workspace_id","top_k"})` | 参数原样转发给工具；返回文本含 `"success": true` 与 data |
| 工具抛 `RuntimeError` | `call_tool` 返回 `"success": false` + `RuntimeError`，不抛 `UnexpectedToolError` |
| input schema | `required == ["query"]`；`properties` 含 `query` / `workspace_id` / `top_k` |
| 生产装配分支 | `build_server()` 不带参数构建成功（未激活 provider、不碰磁盘、不加载模型） |

## 5. 未做（待办）

1. **HTTP / SSE 传输**：本批只做 stdio（本地 MCP server 的标准形态）；要远程调用再补 `run_streamable_http_async`。
2. **MCP 与 Agent 循环合体**：现在 MCP 暴露的是"人/外部客户端直接调工具"，Agent 循环走的是进程内 `ToolExecutor` —— 两者尚未打通（这也是可讲的下一步）。
3. **工具参数的 `Annotated` 描述**：输入 schema 目前只有类型与标题，没有逐参数 description；要给客户端更好的提示可以补 `Annotated[str, Field(description=...)]`。
4. **真实客户端联调**：本批验证到 `list_tools` / `call_tool` 离线等价层；还没在 Claude Desktop / Cursor 里真连过 stdio。
