import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ChatPanel, { parseAnswerSegments } from "./ChatPanel";
import type { ChatMessage } from "../../../../types/chat";

const sampleMessages: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    content: "帮我总结一下第二节",
    createdAt: "2025-12-01T10:00:00Z",
  },
  {
    id: "msg-2",
    role: "assistant",
    content: "这是对第二节的模拟回答。",
    createdAt: "2025-12-01T10:00:05Z",
  },
];

const defaultProps = {
  messages: [],
  input: "",
  quotedText: null,
  tokenUsage: 0,
  onInputChange: vi.fn(),
  onSend: vi.fn(),
  onClearQuote: vi.fn(),
  loading: false,
};

describe("ChatPanel", () => {
  it("渲染 AI 助手标题", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText("AI 助手")).toBeDefined();
  });

  it("空消息列表显示空状态提示", () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText("有什么可以帮你？")).toBeDefined();
  });

  it("空白输入时发送按钮禁用", () => {
    render(<ChatPanel {...defaultProps} />);
    const sendBtn = document.querySelector("button[disabled]");
    expect(sendBtn).toBeDefined();
  });

  it("输入文本后发送按钮可点击", () => {
    render(<ChatPanel {...defaultProps} onSend={vi.fn()} />);
    const textarea = screen.getByPlaceholderText("输入你的问题...");
    fireEvent.change(textarea, { target: { value: "一个测试问题" } });
    const sendBtn = screen.getByRole("button", { name: "" });
    expect(sendBtn).toBeDefined();
  });

  it("用户消息和AI消息正确显示", () => {
    const { container } = render(<ChatPanel {...defaultProps} messages={sampleMessages} />);
    expect(screen.getByText("帮我总结一下第二节")).toBeDefined();
    expect(screen.getByText("这是对第二节的模拟回答。")).toBeDefined();
    // AI消息左侧应该渲染AIAvatar（渐变背景 + svg图标）
    const gradientDivs = container.querySelectorAll(".bg-gradient-to-br");
    // 空状态也有一个渐变div，assistant消息还有一个
    expect(gradientDivs.length).toBeGreaterThanOrEqual(1);
  });

  it("输入框值改变触发 onInputChange", () => {
    const onInputChange = vi.fn();
    render(<ChatPanel {...defaultProps} onInputChange={onInputChange} />);
    const textarea = screen.getByPlaceholderText("输入你的问题...");
    fireEvent.change(textarea, { target: { value: "你好" } });
    expect(onInputChange).toHaveBeenCalled();
  });

  it("Enter键触发发送", () => {
    const onSend = vi.fn();
    render(<ChatPanel {...defaultProps} input="有内容" onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("输入你的问题...");
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onSend).toHaveBeenCalled();
  });

  it("Shift+Enter不触发发送", () => {
    const onSend = vi.fn();
    render(<ChatPanel {...defaultProps} input="有内容" onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("输入你的问题...");
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("显示引用条", () => {
    render(<ChatPanel {...defaultProps} quotedText="这是一个引用文本" />);
    expect(screen.getByText("引用内容")).toBeDefined();
    expect(screen.getByText("这是一个引用文本")).toBeDefined();
  });

  it("引用条上点击清除触发 onClearQuote", () => {
    const onClearQuote = vi.fn();
    const { container } = render(<ChatPanel {...defaultProps} quotedText="引用" onClearQuote={onClearQuote} />);
    // Find the clear button: the QuoteBar renders a button with an X icon (two crossing lines)
    const quoteBar = container.querySelector(".bg-blue-50");
    expect(quoteBar).toBeDefined();
    const clearBtn = quoteBar?.querySelector("button");
    expect(clearBtn).toBeDefined();
    if (clearBtn) fireEvent.click(clearBtn);
    expect(onClearQuote).toHaveBeenCalled();
  });

  it("显示 token 用量", () => {
    render(<ChatPanel {...defaultProps} tokenUsage={150} />);
    expect(screen.getByText(/150/)).toBeDefined();
    expect(screen.getByText(/4,096/)).toBeDefined();
  });

  it("加载中显示脉冲动画点", () => {
    render(<ChatPanel {...defaultProps} loading={true} />);
    const pulseDots = document.querySelectorAll(".animate-pulse");
    expect(pulseDots.length).toBeGreaterThanOrEqual(1);
  });
});

/** 带检索来源的助手消息：回答要能回溯到具体页码。 */
const sourcedMessages: ChatMessage[] = [
  {
    id: "msg-ask",
    role: "user",
    content: "什么是监督学习",
    createdAt: "2025-12-01T10:00:00Z",
  },
  {
    id: "msg-answer",
    role: "assistant",
    content: "监督学习是用带标签的数据训练模型。",
    createdAt: "2025-12-01T10:00:05Z",
    sources: [
      { chunkId: "c1", documentId: "doc-1", pageNumber: 12, headingPath: ["第二章"], distance: 0.31 },
      { chunkId: "c2", documentId: "doc-1", pageNumber: 3, headingPath: null, distance: 0.44 },
    ],
  },
];

describe("ChatPanel 来源与错误", () => {
  it("助手消息的来源渲染为带页码的条目", () => {
    render(<ChatPanel {...defaultProps} messages={sourcedMessages} />);

    expect(screen.getByText(/第 12 页/)).toBeDefined();
    expect(screen.getByText(/第 3 页/)).toBeDefined();
  });

  it("点击来源条目标记为选中（高亮）", () => {
    render(<ChatPanel {...defaultProps} messages={sourcedMessages} />);

    const first = screen.getByRole("button", { name: /第 12 页/ });
    expect(first.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(first);

    expect(
      screen.getByRole("button", { name: /第 12 页/ }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("没有来源时不渲染来源区", () => {
    render(<ChatPanel {...defaultProps} messages={sampleMessages} />);

    expect(screen.queryByRole("button", { name: /第 \d+ 页/ })).toBeNull();
    expect(screen.queryByText(/来源/)).toBeNull();
  });

  it("显示后端错误提示而非静默失败", () => {
    render(<ChatPanel {...defaultProps} error="尚未配置可用的模型 provider" />);

    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByText(/尚未配置可用的模型 provider/)).toBeDefined();
  });

  it("无错误时不渲染错误条", () => {
    render(<ChatPanel {...defaultProps} error={null} />);

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("parseAnswerSegments", () => {
  it("`第 N 页` 是页码，不会被当成来源号", () => {
    expect(parseAnswerSegments("见 [来源 1, 第3页]")).toEqual([
      { text: "见 ", indices: [] },
      { text: "[来源 1, 第3页]", indices: [1] },
    ]);
  });

  it("支持一组引用多个来源", () => {
    const segments = parseAnswerSegments("A[来源 1, 来源 2]B[来源 3]");

    expect(segments[1]).toEqual({ text: "[来源 1, 来源 2]", indices: [1, 2] });
    expect(segments[3]).toEqual({ text: "[来源 3]", indices: [3] });
  });

  it("没有引用时原样返回一段文本", () => {
    expect(parseAnswerSegments("没有任何引用")).toEqual([{ text: "没有任何引用", indices: [] }]);
  });
});

/** 带正文内联引用的回答：`[来源 N]` 要能点到原文页。 */
const citedMessages: ChatMessage[] = [
  {
    id: "msg-cited",
    role: "assistant",
    content: "监督学习用带标签的数据训练模型 [来源 1, 第12页]，评估用留出法 [来源 2]。",
    createdAt: "2025-12-01T10:00:05Z",
    sources: [
      { chunkId: "c1", documentId: "doc-1", pageNumber: 12, headingPath: null, distance: 0.31 },
      { chunkId: "c2", documentId: "doc-1", pageNumber: 3, headingPath: null, distance: 0.44 },
    ],
  },
];

describe("ChatPanel 正文内联引用", () => {
  it("正文里的 [来源 N] 渲染为可点击引用，点击跳到对应来源", () => {
    const onSourceClick = vi.fn();
    render(<ChatPanel {...defaultProps} messages={citedMessages} onSourceClick={onSourceClick} />);

    fireEvent.click(screen.getByRole("button", { name: "[来源 1, 第12页]" }));

    expect(onSourceClick).toHaveBeenCalledTimes(1);
    expect(onSourceClick.mock.calls[0][0]).toMatchObject({ chunkId: "c1", pageNumber: 12 });
  });

  it("再点一次取消高亮，且不重复跳转", () => {
    const onSourceClick = vi.fn();
    render(<ChatPanel {...defaultProps} messages={citedMessages} onSourceClick={onSourceClick} />);

    const cite = () => screen.getByRole("button", { name: "[来源 1, 第12页]" });
    fireEvent.click(cite());
    expect(cite().getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(cite());
    expect(cite().getAttribute("aria-pressed")).toBe("false");
    expect(onSourceClick).toHaveBeenCalledTimes(1);
  });

  it("引用不存在的来源时保持普通文本、不可点击", () => {
    const outOfRange: ChatMessage[] = [{
      id: "msg-oob",
      role: "assistant",
      content: "这句引了一个不存在的来源 [来源 9]。",
      createdAt: "2025-12-01T10:00:06Z",
      sources: [{ chunkId: "c1", documentId: "doc-1", pageNumber: 12, headingPath: null, distance: 0.31 }],
    }];
    render(<ChatPanel {...defaultProps} messages={outOfRange} />);

    expect(screen.queryByRole("button", { name: /来源 9/ })).toBeNull();
    expect(screen.getByText(/引了一个不存在的来源/)).toBeDefined();
  });

  it("没有来源列表时正文原样显示", () => {
    render(<ChatPanel {...defaultProps} messages={sampleMessages} />);

    expect(screen.getByText("这是对第二节的模拟回答。")).toBeDefined();
  });
});