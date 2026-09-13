import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import WorkspacePage from "./WorkspacePage";
import { SESSION_STORAGE_KEY } from "../../chat/sessionStore";

/** Mock framer-motion：组件类型必须缓存，否则每次渲染都会重建整棵 DOM 子树。 */
vi.mock("framer-motion", () => {
  const cache = new Map<string, unknown>();

  const createMotionComponent = (tag: string) => {
    const Component = (props: Record<string, unknown>) => {
      const { children, ...rest } = props;
      const {
        initial: _i, animate: _a, exit: _e, transition: _t,
        ...cleanProps
      } = rest as Record<string, unknown>;
      return React.createElement(tag, cleanProps, children as React.ReactNode);
    };
    Component.displayName = `motion.${tag}`;
    return Component;
  };

  return {
    motion: new Proxy({}, {
      get: (_target, tag: string) => {
        if (!cache.has(tag)) cache.set(tag, createMotionComponent(tag));
        return cache.get(tag);
      },
    }),
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

/** 后端 `GET /api/chat/sessions/{id}/messages` 的原始形状（snake_case）。 */
const storedMessages = [
  {
    id: "m-1",
    session_id: "s-1",
    role: "user",
    content: "上次问的问题",
    source_context_json: null,
    created_at: "2026-09-13T10:00:00Z",
  },
  {
    id: "m-2",
    session_id: "s-1",
    role: "agent",
    content: "上次的回答",
    source_context_json: {
      sources: [
        { chunk_id: "c1", document_id: "doc-1", page_number: 7, heading_path: ["第二章"], distance: 0.2 },
      ],
    },
    created_at: "2026-09-13T10:00:01Z",
  },
];

describe("WorkspacePage · 恢复会话历史", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("刷新后恢复上次对话与它的来源", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "s-1");
    fetchMock.mockResolvedValue(jsonResponse(storedMessages));

    render(<WorkspacePage />);

    expect(await screen.findByText("上次的回答")).toBeDefined();
    expect(screen.getByText("上次问的问题")).toBeDefined();
    expect(screen.getByText(/第 7 页/)).toBeDefined();

    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).toContain("/api/chat/sessions/s-1/messages");
  });

  it("会话在后端不存在时按空历史处理，不弹错误", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "s-gone");
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes("/api/documents")
        ? jsonResponse({ code: 200, message: "ok", data: [] })
        : jsonResponse({ detail: "会话不存在: s-gone" }, { ok: false, status: 404 }),
    );

    render(<WorkspacePage />);

    expect(await screen.findByText("有什么可以帮你？")).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("后端不可用时把错误显示出来", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "s-1");
    fetchMock.mockImplementation(async (url: string) => {
      // 只让会话历史请求失败：文档列表成功返回，才能断言"只有一个错误提示"
      if (String(url).includes("/api/documents")) {
        return jsonResponse({ code: 200, message: "ok", data: [] });
      }
      throw new TypeError("Failed to fetch");
    });

    render(<WorkspacePage />);

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByText(/无法连接后端服务/)).toBeDefined();
  });

  it("本地没有会话 ID 时生成一个，并用它提问", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    render(<WorkspacePage />);
    await waitFor(() => expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeTruthy());
    const savedId = localStorage.getItem(SESSION_STORAGE_KEY);

    fetchMock.mockResolvedValue(
      jsonResponse({
        session_id: savedId,
        answer: "回答",
        source_context: [],
        trace_id: null,
        usage: null,
      }),
    );
    fireEvent.change(screen.getByPlaceholderText("输入你的问题..."), {
      target: { value: "新问题" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("输入你的问题..."), {
      key: "Enter",
      shiftKey: false,
    });

    await screen.findByText("回答");
    const postCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/api/chat") && (init as { method?: string })?.method === "POST",
    );
    expect(postCall).toBeDefined();
    expect(JSON.parse((postCall![1] as { body: string }).body).session_id).toBe(savedId);
  });
});
