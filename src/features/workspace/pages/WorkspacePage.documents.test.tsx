import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import WorkspacePage from "./WorkspacePage";

/**
 * Mock framer-motion。
 *
 * ⚠️ 组件类型必须**缓存**：每次 `get` 都新建组件函数会让 React 认为类型变了，
 * 卸载并重建整棵子树 → DOM 节点被替换 → "先 change 再 keyDown" 作用在旧节点上，交互静默失效。
 * 写法与 `WorkspacePage.chat.test.tsx` 保持一致。
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

const DOCUMENT_ID = "doc-real";

const documentsPayload = {
  code: 200,
  message: "ok",
  data: [
    {
      document_id: DOCUMENT_ID,
      title: "真实法语课件",
      original_filename: "reel.pdf",
      file_type: "pdf",
      status: "parsed",
      page_count: 2,
      created_at: "2026-09-12T10:00:00+00:00",
    },
  ],
};

const unitsPayload = {
  code: 200,
  message: "ok",
  data: [
    { unit_id: "unit-1", sequence_index: 0, page_number: 1, text_content: "Première page du cours" },
    { unit_id: "unit-2", sequence_index: 1, page_number: 2, text_content: "Deuxième page du cours" },
  ],
};

/** 默认回答带一条指向第 2 页的来源。 */
function chatPayloadFor(pageNumber: number | null) {
  return {
    session_id: "s-1",
    answer: "监督学习是用带标签的数据训练模型。",
    source_context: [
      {
        chunk_id: "c1",
        document_id: DOCUMENT_ID,
        page_number: pageNumber,
        heading_path: ["第二章"],
        distance: 0.31,
      },
    ],
    trace_id: "trace-1",
    usage: { input_tokens: 900, output_tokens: 120 },
  };
}

/**
 * 按 URL 分派。`/units` 必须排在 `/api/documents` 之前判断 —— 前者的路径里也含后者。
 */
function mockApi(
  options: {
    documents?: unknown;
    units?: unknown;
    chat?: unknown;
    history?: unknown;
  } = {},
) {
  const {
    documents = documentsPayload,
    units = unitsPayload,
    chat = chatPayloadFor(2),
    history = [],
  } = options;

  return vi.fn(async (url: string) => {
    const target = String(url);
    if (target.includes("/units")) return jsonResponse(units);
    if (target.includes("/api/documents")) return jsonResponse(documents);
    if (target.includes("/messages")) return jsonResponse(history);
    return jsonResponse(chat);
  });
}

/** 在当前面板里输入问题并回车发送。 */
function ask(text: string) {
  fireEvent.change(screen.getByPlaceholderText("输入你的问题..."), {
    target: { value: text },
  });
  // 重新查询而不是复用节点：重渲染之后 DOM 节点可能已被替换
  fireEvent.keyDown(screen.getByPlaceholderText("输入你的问题..."), {
    key: "Enter",
    shiftKey: false,
  });
}

describe("WorkspacePage · 接真实文档与引用跳转", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("打开工作区时左侧列出后端返回的真实文档，而不是内置 mock", async () => {
    vi.stubGlobal("fetch", mockApi());

    render(<WorkspacePage />);

    expect(await screen.findByText("真实法语课件")).toBeTruthy();
    expect(screen.queryByText("TD-économie-chap2.docx")).toBeNull();
  });

  it("选中文档后中间显示该文档的真实原文", async () => {
    vi.stubGlobal("fetch", mockApi());

    render(<WorkspacePage />);
    fireEvent.click(await screen.findByText("真实法语课件"));
    fireEvent.click(await screen.findByText("第 1 页"));

    expect(await screen.findByText(/Première page du cours/)).toBeTruthy();
  });

  it("点击引用来源会定位到对应页的原文", async () => {
    vi.stubGlobal("fetch", mockApi());

    render(<WorkspacePage />);
    ask("监督学习是什么");
    await screen.findByText("监督学习是用带标签的数据训练模型。");

    fireEvent.click(await screen.findByRole("button", { name: /来源 1/ }));

    expect(await screen.findByText(/Deuxième page du cours/)).toBeTruthy();
  });

  it("点击正文里的 [来源 N] 也能定位到原文页", async () => {
    // 内联引用与来源条目走同一条链路 —— 这条用例锁住"正文入口真的接到了 revealSource"
    const cited = { ...chatPayloadFor(2), answer: "监督学习用带标签的数据训练模型 [来源 1]。" };
    vi.stubGlobal("fetch", mockApi({ chat: cited }));

    render(<WorkspacePage />);
    ask("监督学习是什么");
    await screen.findByText(/监督学习用带标签的数据训练模型/);

    fireEvent.click(await screen.findByRole("button", { name: "[来源 1]" }));

    expect(await screen.findByText(/Deuxième page du cours/)).toBeTruthy();
  });

  it("来源没有页码时给出可读提示且不崩溃", async () => {
    vi.stubGlobal("fetch", mockApi({ chat: chatPayloadFor(null) }));

    render(<WorkspacePage />);
    ask("监督学习是什么");
    await screen.findByText("监督学习是用带标签的数据训练模型。");

    fireEvent.click(await screen.findByRole("button", { name: /来源 1/ }));

    expect(await screen.findByText(/无法定位到原文页码/)).toBeTruthy();
  });

  it("后端连不上时显示可读错误，而不是白屏", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const target = String(url);
        if (target.includes("/messages")) return jsonResponse([]);
        throw new TypeError("Failed to fetch");
      }),
    );

    render(<WorkspacePage />);

    expect((await screen.findByRole("alert")).textContent).toContain("无法连接后端服务");
  });
});
