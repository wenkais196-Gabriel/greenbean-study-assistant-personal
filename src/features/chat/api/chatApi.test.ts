import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import type { ChatSource } from "../../../types/chat";
import { askQuestion } from "./chatApi";

const SESSION_ID = "s-1";

/** 后端返回的原始形状（snake_case）—— 这是「输入」。 */
const wireSource = {
  chunk_id: "chunk-1",
  document_id: "doc-1",
  page_number: 12,
  heading_path: ["第二章", "2.1"],
  distance: 0.31,
};

/** 前端内部统一 camelCase —— 这是「期望输出」（转换由 chatApi 负责）。 */
const source: ChatSource = {
  chunkId: "chunk-1",
  documentId: "doc-1",
  pageNumber: 12,
  headingPath: ["第二章", "2.1"],
  distance: 0.31,
};

const chatResponse = {
  session_id: SESSION_ID,
  answer: "监督学习是用带标签的数据训练模型。",
  source_context: [wireSource],
  trace_id: "trace-1",
  usage: { input_tokens: 900, output_tokens: 120 },
};

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

describe("chatApi", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("以 POST /api/chat 提问并返回回答、来源与用量", async () => {
    fetchMock.mockResolvedValue(jsonResponse(chatResponse));

    const result = await askQuestion({ sessionId: SESSION_ID, query: "什么是监督学习" });

    expect(result.answer).toBe(chatResponse.answer);
    expect(result.sources).toEqual([source]);
    expect(result.usage).toEqual({ inputTokens: 900, outputTokens: 120 });
    expect(result.traceId).toBe("trace-1");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/chat");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({
      session_id: SESSION_ID,
      query: "什么是监督学习",
      history: [],
      use_extended_context: false,
    });
  });

  it("请求体带上工作区归属与历史消息", async () => {
    fetchMock.mockResolvedValue(jsonResponse(chatResponse));

    await askQuestion({
      sessionId: SESSION_ID,
      query: "还有呢",
      workspaceId: "ws-1",
      useExtendedContext: true,
      history: [{ role: "user", content: "上一轮问题" }],
    });

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.workspace_id).toBe("ws-1");
    expect(body.use_extended_context).toBe(true);
    expect(body.history).toEqual([{ role: "user", content: "上一轮问题" }]);
  });

  it("没有检索来源时返回空来源列表而不是 null", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ ...chatResponse, source_context: null, usage: null }),
    );

    const result = await askQuestion({ sessionId: SESSION_ID, query: "你好" });

    expect(result.sources).toEqual([]);
    expect(result.usage).toBeNull();
  });

  it("provider 未配置（503）时抛出可读错误", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "尚未配置可用的模型 provider" }, { ok: false, status: 503 }),
    );

    const error = await askQuestion({ sessionId: SESSION_ID, query: "你好" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(503);
    expect((error as ApiError).message).toContain("尚未配置");
  });

  it("空白问题直接被拒绝且不发请求", async () => {
    await expect(
      askQuestion({ sessionId: SESSION_ID, query: "   " }),
    ).rejects.toThrow("问题不能为空");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
