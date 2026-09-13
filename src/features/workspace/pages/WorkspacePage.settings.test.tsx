import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import WorkspacePage from "./WorkspacePage";

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

describe("WorkspacePage · 模型配置入口", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("点击设置按钮打开模型配置面板", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    render(<WorkspacePage />);
    expect(screen.queryByText("模型配置")).toBeNull();

    fireEvent.click(screen.getByTitle("设置"));

    expect(await screen.findByText("模型配置")).toBeDefined();
  });

  it("面板关闭后回到工作区", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    render(<WorkspacePage />);
    fireEvent.click(screen.getByTitle("设置"));
    await screen.findByText("模型配置");

    fireEvent.click(screen.getByRole("button", { name: "关闭" }));

    expect(screen.queryByText("模型配置")).toBeNull();
  });
});
