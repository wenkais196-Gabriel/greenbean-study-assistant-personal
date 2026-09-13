import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import WorkspacePage from "./WorkspacePage";

/**
 * Mock framer-motion。
 *
 * ⚠️ 组件类型必须**缓存**：如果每次访问 `motion.div` 都新建一个组件函数，
 * React 会认为类型变了，于是卸载并重建整棵子树 —— DOM 节点被替换，
 * 测试里"先 change 再 keyDown"就会作用在已脱离文档的旧节点上，导致交互静默失效。
 */
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

const chatPayload = {
  session_id: "s-1",
  answer: "监督学习是用带标签的数据训练模型。",
  source_context: [
    { chunk_id: "c1", document_id: "doc-1", page_number: 12, heading_path: ["第二章"], distance: 0.31 },
  ],
  trace_id: "trace-1",
  usage: { input_tokens: 900, output_tokens: 120 },
};

/**
 * 按 URL 分派：`/messages` 是打开工作区时的历史拉取，其余是提问。
 *
 * 挂载即拉历史之后，不能再假设 `fetchMock.mock.calls[0]` 就是提问那一次。
 */
function mockChatApi(payload: unknown, history: unknown = []) {
  return vi.fn(async (url: string) =>
    String(url).includes("/messages") ? jsonResponse(history) : jsonResponse(payload),
  );
}

/** 在当前面板里输入问题并回车发送。 */
function askQuestion(text: string) {
  fireEvent.change(screen.getByPlaceholderText("输入你的问题..."), {
    target: { value: text },
  });
  // 重新查询而不是复用上面的节点：一次重渲染之后 DOM 节点可能已被替换
  fireEvent.keyDown(screen.getByPlaceholderText("输入你的问题..."), {
    key: "Enter",
    shiftKey: false,
  });
}

/** 提问那一次调用（POST /api/chat），与历史拉取区分开。 */
function findAskCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.find(
    ([url, init]) => String(url).endsWith("/api/chat") && (init as { method?: string })?.method === "POST",
  );
}

describe("WorkspacePage · 问答接入后端", () => {
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

  it("发送问题后调用 POST /api/chat 并渲染带来源的回答", async () => {
    fetchMock.mockImplementation(mockChatApi(chatPayload));

    render(<WorkspacePage />);
    askQuestion("什么是监督学习");

    expect(await screen.findByText(chatPayload.answer)).toBeDefined();
    expect(screen.getByText(/第 12 页/)).toBeDefined();

    const askCall = findAskCall(fetchMock);
    expect(askCall).toBeDefined();
    const [url, init] = askCall!;
    expect(url).toContain("/api/chat");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body.query).toBe("什么是监督学习");
    expect(body.session_id).toBeTruthy();
  });

  it("模型未配置时显示错误提示且不产生助手回答", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes("/messages")
        ? jsonResponse([])
        : jsonResponse({ detail: "尚未配置可用的模型 provider" }, { ok: false, status: 503 }),
    );

    render(<WorkspacePage />);
    askQuestion("什么是监督学习");

    expect(await screen.findByText(/尚未配置可用的模型 provider/)).toBeDefined();
    expect(screen.getByText("什么是监督学习")).toBeDefined();
  });

  it("空白输入不发出提问请求", async () => {
    fetchMock.mockImplementation(mockChatApi(chatPayload));

    render(<WorkspacePage />);
    askQuestion("   ");

    await screen.findByText("有什么可以帮你？");
    expect(findAskCall(fetchMock)).toBeUndefined();
  });

  it("回答的 token 用量累加到面板", async () => {
    fetchMock.mockImplementation(mockChatApi(chatPayload));

    render(<WorkspacePage />);
    askQuestion("什么是监督学习");

    expect(await screen.findByText(/1,020/)).toBeDefined();
  });
});
