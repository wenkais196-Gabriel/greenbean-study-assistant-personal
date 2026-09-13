# US · 阶段 2 · Agent 工具循环：模型自主调用工具 + 失败降级

> **状态：已实现（2026-09-13）**
> 验收：`ChatService.answer()` 给 `ChatAgent` 注入三个检索工具的 schema 与生产执行器；
> 模型可以在初始检索上下文**之外**自主调用工具补充信息，任何工具失败 / 超时都降级为"用已有上下文直答"。
> 前置：[`us-stage2-tools-wiring.md`](us-stage2-tools-wiring.md)（工具已接生产）、[`us-stage1-chat.md`](us-stage1-chat.md)（问答闭环）

---

## 1. 这一批补齐的空白

阶段 1 的 `ChatAgent` 是**单轮**：路由 → 检索（调用方代劳）→ 拼 prompt → 直答。规划里
"检索 → 判断上下文是否充分 → 不足则改写 query 重检 → 生成答案"的 Agent 循环没有兑现。
本批把这句话兑现为 **OpenAI function calling 口径的有界工具循环**。

| 文件 | 之前 | 现在 |
|---|---|---|
| `app/providers/base.py` | `chat_completion` 无 `tools`；`ChatResult` 无 `tool_calls` | 新增可选 `tools` 参数与 `ToolCall`（`id`/`name`/`arguments`），向后兼容 |
| `app/providers/openai_compat_provider.py` | 不透传 `tools` | 透传 `tools`；把 `message.tool_calls` 解析进 `ChatResult.tool_calls`（非法 JSON → `{}`） |
| `app/tools/schemas.py` | **不存在** | 三个检索工具的 OpenAI function calling schema（provider 无关的工具不背协议） |
| `app/agents/tool_executor.py` | **不存在** | `ToolExecutor`：按名执行（同步/异步都行）、结果序列化成文本、超长截断、未知工具名报错 |
| `app/agents/chat_agent.py` | 单轮直答 | 有界工具循环（`max_tool_rounds`）+ 失败/超时/轮数用尽 → 降级直答；每次工具调用落 `greenbean.tool.call` span |
| `app/services/chat_service.py` | 不装配工具 | 注入 `RETRIEVAL_TOOL_SCHEMAS` + 懒加载 `ToolExecutor`（复用同一会话工厂与嵌入服务） |
| `app/tools/factory.py` | `build_tools()` 无维度参数 | 增加 `embedding_dimension` 透传（测试库 8 维 / 生产 1024 维，必须与建库一致） |
| `app/config/settings.py` | — | `MAX_TOOL_ROUNDS=3`、`TOOL_TIMEOUT_SECONDS=10.0`、`TOOL_RESULT_MAX_CHARS=4000` |

## 2. Acceptance Criteria

- **AC1**：`AIProvider.chat_completion(..., tools=None)` 与 `ChatResult.tool_calls` 为**可选**扩展，既有调用方零影响。
- **AC2**：`OpenAICompatibleProvider` 透传 `tools`；无 `tools` 时不传该 key；`message.tool_calls` 解析为 `list[ToolCall]`，缺失为 `None`，非法 JSON 参数落 `{}`（由工具校验环节触发降级）。
- **AC3**：`ChatAgent` 有界工具循环：模型返回 tool_calls 时执行并把结果作为 `role=tool` 消息回喂，直到模型不再要工具或轮数用尽（默认 3 轮）。
- **AC4**：工具执行走生产 `ToolExecutor`（`chunk_search` / `document_retrieval` / `section_context`）；结果序列化文本、超长按 `TOOL_RESULT_MAX_CHARS` 截断；每次调用记一条 `greenbean.tool.call` span。
- **AC5**：**失败降级**：工具执行抛错 / 未知工具名 / 参数非法 / 超时 → 停止循环，用初始检索上下文直答（不带 tools），异常不出给用户。
- **AC6**：轮数用尽仍要求工具 → 强制直答（硬终止条件，不无限循环）。
- **AC7**：`ChatService` 仍是唯一入口，把工具 schema 与执行器注入 `ChatAgent`；`POST /api/chat` 对外契约不变。
- **AC8**：全部 mock provider 测试；`pytest --cov=app --cov-config=tests/.coveragerc` → **495 passed / 100.00%**。

## 3. 循环设计与分层

```
ChatService.answer()
  ├─ route（RouterAgent，失败已降级）
  ├─ retrieve（初始检索，ChatService 代劳 —— 不变）
  └─ agent.generate_response(context, sources, route, tool_schemas, tool_executor)
       ├─ 有 tools 且 executor 就位 → 循环：
       │    LLM(tools) → 无 tool_calls?  → 收尾回答
       │                → 有 tool_calls?  → 逐条执行（asyncio.timeout 兜底）
       │                   ├─ 成功 → 追加 assistant echo + role=tool 消息，下一轮
       │                   └─ 失败 → 立即降级：不带 tools 的直答
       └─ 无 tools → 单轮直答（既有路径，零变化）
```

要点：

- **初始检索不变**：`ChatService` 仍先做一次检索给模型兜底，工具循环是"补充"而非替代 ——
  这也让降级有处可退：任何工具失败都退回最初那份上下文。
- **有界**：`max_tool_rounds` 是硬上限，模型一直要工具也不会无限循环。
- **协议 echo**：OpenAI 要求"模型请求过工具后，下一轮必须 echo assistant 的 tool_calls 再跟 tool 消息"，
  `_assistant_tool_call_message` 负责这条协议，`ToolCall.arguments` 再序列化回 JSON。
- **可观测**：`greenbean.tool.call` span 记录每次工具调用的名字 / 耗时 / 错误，降级率可统计。
- **超时**：`asyncio.timeout` 只防"工具实现卡死"，本地检索毫秒级，正常不会触发。

## 4. 为什么工具循环对"求职叙事"重要

规划里的原话：**这是 agent 岗最核心的一段**——工具粒度怎么定、为什么不用一次性塞上下文、
循环终止条件、降级策略。本批的可讲点：

1. **工具粒度**：三个检索工具，每个只做一件事，schema 与其 `run()` 签名一一对应；
2. **为什么不是一次性塞上下文**：模型在初始上下文不足时**自己决定**再查什么（query 由模型改写）；
3. **终止条件**：模型不再要工具 OR 轮数上限 OR 失败降级，三者任一触发都会停；
4. **降级策略**：与 `RouterAgent` 同一思路 —— 工具层异常绝不冒泡给用户，一律退回直答。

## 5. 验收实测（2026-09-13）

| 项 | 结果 |
|---|---|
| `pytest --cov=app --cov-config=tests/.coveragerc` | **495 passed / 100.00%**（`fail_under=100`） |
| 前端 `npm run test:frontend` | 293 passed / 19 文件（未改前端，回归） |
| 循环 happy path（mock provider） | 第一轮要工具 → 执行 → 结果回喂 → 第二轮答案；`tools` 只出现在第一轮 |
| 降级 | 工具抛错 / 未知工具名 / 超时（`tool_timeout_seconds=0.001`）→ 第二轮调用**不带 tools**、用初始上下文直答 |
| 轮数上限 | `max_tool_rounds=2`、模型连续要工具 → 2 轮循环 + 1 次强制直答，共 3 次调用 |
| e2e 合龙（真库 + 假嵌入 + 假 provider） | 模型要 `chunk_search` → 生产 `ProductionChunkSearcher` 真检索 → `role=tool` 结果回喂 → 第二轮回答 |
| provider 契约 | `tools` 透传 / 默认不带 / `tool_calls` 解析 / 非法 JSON → `{}` / 缺失 → `None` |

## 6. 未做（待办）

1. **MCP server**：把同一批工具按 MCP 协议暴露（下一批）。
2. **引用后校验**：模型输出里的 `[来源 N]` 仍未做存在性校验（防幻觉引用），属阶段 3 的 L2 评测范畴。
3. **工具结果的 token 级预算**：目前按字符截断，精确 token 预算应由 provider 上下文窗口决定（与 `CONTEXT_MAX_CHARS` 同一个待办）。
4. **真实 provider 下的循环质量**（工具成功率、TTFT、多轮成本）未度量 —— 需要 provider key。
5. **`STRUCTURE` 检索分支**：仍与概念类同深度，无章节/页码级检索（继承自阶段 1 待办）。
