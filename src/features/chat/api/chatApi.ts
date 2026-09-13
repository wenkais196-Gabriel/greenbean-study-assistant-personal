/**
 * 问答接口封装：`POST /api/chat`（提问 → 带来源的回答）与
 * `GET /api/chat/sessions/{session_id}/messages`（回读会话历史）。
 *
 * 契约见 docs/specs/us-stage1-chat.md。这一层只做三件事：
 * 组装请求体、把 snake_case 的响应转成前端类型、把错误交给 `apiClient` 统一映射。
 */
import { requestJson } from "../../../lib/apiClient";
import type { ChatMessage, ChatSource } from "../../../types/chat";

/**
 * 工作区缺省值：请求不带 `workspace_id` 时用它给会话归档。
 *
 * 与后端 `app/config/settings.py` 的默认工作区保持一致（值一致才能查到同一个会话）。
 */
export const DEFAULT_WORKSPACE_ID = "default";

/** 后端 `source_context` 的原始形状（Python 侧 snake_case）。 */
interface WireSource {
  chunk_id: string;
  document_id: string;
  page_number: number | null;
  heading_path: string[] | null;
  distance: number | null;
}

/** 后端 `usage` 的原始形状；provider 不回传时整个字段为 null。 */
interface WireUsage {
  input_tokens: number | null;
  output_tokens: number | null;
}

interface WireChatResponse {
  session_id: string;
  answer: string;
  source_context: WireSource[] | null;
  trace_id?: string | null;
  usage?: WireUsage | null;
}

/** 后端会话历史里单条消息的原始形状（`ChatMessageResponse`）。 */
interface WireStoredMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  source_context_json: { sources?: WireSource[] } | null;
  created_at: string;
}

/** 一次提问的 token 用量（只含"回答"那次 LLM 调用）。 */
export interface ChatUsage {
  inputTokens: number | null;
  outputTokens: number | null;
}

export interface AskResult {
  answer: string;
  /** 空来源归一为 `[]`，调用方不用再判 null */
  sources: ChatSource[];
  usage: ChatUsage | null;
  traceId: string | null;
}

export interface AskHistoryMessage {
  role: string;
  content: string;
}

export interface AskOptions {
  sessionId: string;
  query: string;
  history?: AskHistoryMessage[];
  useExtendedContext?: boolean;
  /** 工作区归属：会话落库时用它归档；不传则由后端用默认工作区 */
  workspaceId?: string;
  signal?: AbortSignal;
}

function toSource(wire: WireSource): ChatSource {
  return {
    chunkId: wire.chunk_id,
    documentId: wire.document_id,
    pageNumber: wire.page_number,
    headingPath: wire.heading_path,
    distance: wire.distance,
  };
}

/** 后端把助手叫 `agent`，前端叫 `assistant`：在 api 层一次性翻掉。 */
function toMessageRole(role: string): ChatMessage["role"] {
  return role === "user" ? "user" : "assistant";
}

/**
 * 提问并拿到带来源的回答。
 *
 * 空白问题**不发请求**：后端也会 400，但没必要打一次网络往返。
 */
export async function askQuestion(options: AskOptions): Promise<AskResult> {
  const {
    sessionId,
    query,
    history = [],
    useExtendedContext = false,
    workspaceId,
    signal,
  } = options;

  if (!query.trim()) {
    throw new Error("问题不能为空");
  }

  const body = await requestJson<WireChatResponse>("/api/chat", {
    method: "POST",
    body: {
      session_id: sessionId,
      query,
      history,
      use_extended_context: useExtendedContext,
      ...(workspaceId ? { workspace_id: workspaceId } : {}),
    },
    signal,
  });

  return {
    answer: body.answer,
    sources: (body.source_context ?? []).map(toSource),
    usage: body.usage
      ? { inputTokens: body.usage.input_tokens, outputTokens: body.usage.output_tokens }
      : null,
    traceId: body.trace_id ?? null,
  };
}

/**
 * 回读一次会话的历史消息（前端类型，按后端给的时间升序）。
 *
 * 会话不存在时后端回 **404**（抛 `ApiError`，`status === 404`）——
 * 由调用方决定怎么处理：界面把它当作"没有历史"，而不是报错。
 */
export async function fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const messages = await requestJson<WireStoredMessage[]>(
    `/api/chat/sessions/${sessionId}/messages`,
  );

  return messages.map((message) => ({
    id: message.id,
    role: toMessageRole(message.role),
    content: message.content,
    createdAt: message.created_at,
    sources: (message.source_context_json?.sources ?? []).map(toSource),
  }));
}
