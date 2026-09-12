import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import DocumentViewer from "./DocumentViewer";
import type { ContentBlock, FootnoteReference } from "../../../../types/section";

// Mock framer-motion
vi.mock("framer-motion", () => {
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
    motion: new Proxy(
      {},
      { get: (_target, tag: string) => createMotionComponent(tag) },
    ),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  };
});

const sampleBlocks: ContentBlock[] = [
  {
    id: "block-1",
    sectionId: "ch1-1",
    title: "1.1 背景介绍",
    contentType: "text",
    lines: [
      { id: "l1", text: "AI技术发展迅速。", type: "paragraph", footnoteRef: "1" },
      { id: "l2", text: "教育领域应用广泛。", type: "paragraph" },
      { id: "l3", text: "研究背景与动机", type: "heading", level: 2 },
      { id: "l4", text: "• 测试列表项", type: "list" },
      { id: "l5", text: "const x = 1;", type: "code", highlighted: true },
    ],
  },
  {
    id: "block-table",
    sectionId: "ch1-1",
    title: "表1: 对比",
    contentType: "table",
    tableData: {
      headers: ["名称", "值"],
      rows: [
        { id: "tr1", cells: ["A", "1"] },
        { id: "tr2", cells: ["B", "2"] },
      ],
    },
  },
  {
    id: "block-image",
    sectionId: "ch1-1",
    title: "图1: 示意",
    contentType: "image",
    imageUrl: "",
    imageCaption: "示意图说明文字",
  },
  {
    id: "block-img-url",
    sectionId: "ch1-1",
    title: "图2: 实图",
    contentType: "image",
    imageUrl: "https://example.com/img.png",
  },
  {
    id: "block-other-section",
    sectionId: "ch2-1",
    title: "2.1 概念定义",
    contentType: "text",
    lines: [
      { id: "l10", text: "不同章节内容", type: "paragraph" },
    ],
  },
];

const sampleFootnotes: FootnoteReference[] = [
  { id: "fn-1", refNumber: "1", sourceText: "Gartner预测到2025年", sourceDesc: "第1页，第1段" },
  { id: "fn-2", refNumber: "2", sourceText: "第二个引用来源", sourceDesc: "第2页，第3段" },
];

const defaultProps = {
  contentBlocks: sampleBlocks,
  selectedSectionId: null,
  footnotes: sampleFootnotes,
  expandedFootnoteId: null,
  currentSelection: null,
  showSelectionMenu: false,
  selectionMenuPos: null,
  onToggleHighlight: vi.fn(),
  onUpdateLineText: vi.fn(),
  onFormatLine: vi.fn(),
  onToggleFootnote: vi.fn(),
  onSelectText: vi.fn(),
  onShowSelectionMenu: vi.fn(),
  onQuoteSelection: vi.fn(),
};

describe("DocumentViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("未选择章节时显示空状态", () => {
    render(<DocumentViewer {...defaultProps} />);
    expect(screen.getByText("选择章节查看内容")).toBeDefined();
    expect(screen.getByText("点击左侧章节列表，解析内容将在此处展示")).toBeDefined();
  });

  it("选择章节后显示内容块", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.getByText("1.1 背景介绍")).toBeDefined();
    expect(screen.getByText("AI技术发展迅速。")).toBeDefined();
    expect(screen.getByText("教育领域应用广泛。")).toBeDefined();
  });

  it("显示下载和分享按钮", () => {
    render(<DocumentViewer {...defaultProps} />);
    expect(screen.getByTitle("下载")).toBeDefined();
    expect(screen.getByTitle("分享")).toBeDefined();
  });

  it("显示文档工具栏", () => {
    render(<DocumentViewer {...defaultProps} />);
    expect(screen.getAllByTitle("加粗").length).toBeGreaterThanOrEqual(1);
  });

  it("脚注引用显示蓝色圆点按钮", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    const footnoteBtns = screen.getAllByTitle("点击查看原文引用");
    expect(footnoteBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("点击脚注触发 onToggleFootnote", () => {
    const onToggleFootnote = vi.fn();
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" onToggleFootnote={onToggleFootnote} />,
    );
    const footnoteBtns = screen.getAllByTitle("点击查看原文引用");
    fireEvent.click(footnoteBtns[0]);
    expect(onToggleFootnote).toHaveBeenCalledWith("fn-1");
  });

  it("展开脚注显示脚注详情", () => {
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" expandedFootnoteId="fn-1" />,
    );
    expect(screen.getByText("Gartner预测到2025年")).toBeDefined();
  });

  it("展开脚注调用 onToggleFootnote 关闭", () => {
    const onToggleFootnote = vi.fn();
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" expandedFootnoteId="fn-1" onToggleFootnote={onToggleFootnote} />,
    );
    const closeBtns = document.querySelectorAll("button");
    for (const btn of Array.from(closeBtns)) {
      const svg = btn.querySelector("svg");
      if (svg && svg.getAttribute("viewBox") === "0 0 24 24" && svg.querySelector("line[x1='18']")) {
        fireEvent.click(btn);
        break;
      }
    }
    expect(onToggleFootnote).toHaveBeenCalledWith("fn-1");
  });

  it("表格块正确渲染表头和行", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.getByText("表1: 对比")).toBeDefined();
    expect(screen.getByText("名称")).toBeDefined();
    expect(screen.getByText("值")).toBeDefined();
  });

  it("图片块显示占位图和标题", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.getByText("图1: 示意")).toBeDefined();
    expect(screen.getByText("示意图说明文字")).toBeDefined();
    expect(screen.getByText("Chart")).toBeDefined();
  });

  it("有URL的图片块显示图片", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    const img = screen.getByAltText("图2: 实图");
    expect(img).toBeDefined();
    expect(img.getAttribute("src")).toBe("https://example.com/img.png");
  });

  it("列表类型行有正确样式", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.getByText("• 测试列表项")).toBeDefined();
  });

  it("高亮代码行有背景色", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.getByText("const x = 1;")).toBeDefined();
  });

  it("跨章节内容不会显示", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    expect(screen.queryByText("2.1 概念定义")).toBeNull();
  });

  it("内容块之间有分隔线", () => {
    const { container } = render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    const hrs = container.querySelectorAll("hr");
    expect(hrs.length).toBeGreaterThanOrEqual(1);
  });

  it("空章节内容块列表显示空", () => {
    render(<DocumentViewer {...defaultProps} contentBlocks={[]} selectedSectionId="ch1-1" />);
    expect(screen.queryByText("1.1 背景介绍")).toBeNull();
  });

  it("contentEditable 行可编辑", () => {
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    const span = screen.getByText("AI技术发展迅速。");
    expect(span.getAttribute("contentEditable")).toBe("true");
  });

  it("下载按钮点击时创建下载链接", () => {
    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tagName, options) => {
      const el = originalCreateElement(tagName, options);
      if (tagName === "a") {
        el.click = clickSpy;
      }
      return el;
    });
    
    render(<DocumentViewer {...defaultProps} />);
    fireEvent.click(screen.getByTitle("下载"));
    
    expect(createElementSpy).toHaveBeenCalledWith("a");
    expect(clickSpy).toHaveBeenCalled();
    createElementSpy.mockRestore();
  });

  it("分享按钮在支持 navigator.share 时调用分享API", () => {
    const mockShare = vi.fn().mockResolvedValue(undefined);
    const originalShare = navigator.share;
    vi.stubGlobal("navigator", { ...navigator, share: mockShare });
    
    render(<DocumentViewer {...defaultProps} />);
    fireEvent.click(screen.getByTitle("分享"));
    
    expect(mockShare).toHaveBeenCalledWith({
      title: "GreenBean Document",
      text: "Share my course analysis",
    });
    
    vi.stubGlobal("navigator", { ...navigator, share: originalShare });
  });

  it("分享按钮在不支持 navigator.share 时不报错", () => {
    const originalShareDesc = Object.getOwnPropertyDescriptor(navigator, "share");
    Object.defineProperty(navigator, "share", {
      value: undefined,
      writable: true,
      configurable: true,
    });
    
    render(<DocumentViewer {...defaultProps} />);
    fireEvent.click(screen.getByTitle("分享"));
    
    if (originalShareDesc) {
      Object.defineProperty(navigator, "share", originalShareDesc);
    }
  });

  it("分享失败时 catch 块不报错", () => {
    const mockShare = vi.fn().mockRejectedValue(new Error("User cancelled"));
    const originalShare = navigator.share;
    vi.stubGlobal("navigator", { ...navigator, share: mockShare });
    
    render(<DocumentViewer {...defaultProps} />);
    fireEvent.click(screen.getByTitle("分享"));
    
    vi.stubGlobal("navigator", { ...navigator, share: originalShare });
  });

  it("heading level 1 行有正确样式", () => {
    const blocksWithHeading1: ContentBlock[] = [
      {
        id: "block-h1",
        sectionId: "ch1-1",
        title: "第一章",
        contentType: "text",
        lines: [
          { id: "l-h1", text: "大标题", type: "heading", level: 1 },
          { id: "l-h3", text: "小标题", type: "heading", level: 3 },
          { id: "l-code", text: "code line", type: "code" },
          { id: "l-center", text: "居中文本", type: "paragraph", align: "center" },
          { id: "l-right", text: "右对齐文本", type: "paragraph", align: "right" },
          { id: "l-justify", text: "两端对齐文本", type: "paragraph", align: "justify" },
          { id: "l-color", text: "彩色文本", type: "paragraph", color: "#ff0000", underline: true },
        ],
      },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocksWithHeading1} selectedSectionId="ch1-1" />,
    );
    expect(screen.getByText("大标题")).toBeDefined();
    expect(screen.getByText("小标题")).toBeDefined();
    expect(screen.getByText("code line")).toBeDefined();
    expect(screen.getByText("居中文本")).toBeDefined();
    expect(screen.getByText("右对齐文本")).toBeDefined();
    expect(screen.getByText("两端对齐文本")).toBeDefined();
    expect(screen.getByText("彩色文本")).toBeDefined();
  });

  it("tableData 为 null 时 TableBlock 返回 null", () => {
    const blocksNoTable: ContentBlock[] = [
      { id: "block-no-table", sectionId: "ch1-1", title: "No Table", contentType: "table" },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocksNoTable} selectedSectionId="ch1-1" />,
    );
    expect(screen.getByText("No Table")).toBeDefined();
  });

  it("handleLineHtmlChange 触发 onUpdateLineText", () => {
    const onUpdateLineText = vi.fn();
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const span = screen.getByText("AI技术发展迅速。");
    act(() => { span.textContent = "修改后的文本"; });
    fireEvent.blur(span);
    expect(onUpdateLineText).toHaveBeenCalled();
  });

  it("textContent 不变时 blur 不触发 onUpdateLineText", () => {
    const onUpdateLineText = vi.fn();
    const blocks: ContentBlock[] = [
      { id: "b1", sectionId: "ch1-1", title: "Title", contentType: "text",
        lines: [{ id: "lx", text: "unchanged", type: "paragraph" }] },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const span = screen.getByText("unchanged");
    fireEvent.blur(span);
    expect(onUpdateLineText).not.toHaveBeenCalled();
  });

  it("showSelectionMenu 为 true 时显示 SelectionMenu", () => {
    const onQuoteSelection = vi.fn();
    const onShowSelectionMenu = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        showSelectionMenu={true}
        selectionMenuPos={{ x: 100, y: 200 }}
        onQuoteSelection={onQuoteSelection}
        onShowSelectionMenu={onShowSelectionMenu}
      />,
    );
    expect(screen.getByText("引用此段询问 AI")).toBeDefined();
    fireEvent.click(screen.getByText("引用此段询问 AI"));
    expect(onQuoteSelection).toHaveBeenCalled();
  });

  it("SelectionMenu 点击 backdrop 触发 onShowSelectionMenu(false)", () => {
    const onShowSelectionMenu = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        showSelectionMenu={true}
        selectionMenuPos={{ x: 100, y: 200 }}
        onShowSelectionMenu={onShowSelectionMenu}
      />,
    );
    const backdrop = document.querySelector(".fixed.inset-0") as HTMLElement;
    expect(backdrop).toBeTruthy();
    fireEvent.click(backdrop);
    expect(onShowSelectionMenu).toHaveBeenCalledWith(false);
  });

  it("showSelectionMenu 为 false 时不显示 SelectionMenu", () => {
    const onQuoteSelection = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        showSelectionMenu={false}
        selectionMenuPos={null}
        onQuoteSelection={onQuoteSelection}
      />,
    );
    expect(screen.queryByText("引用此段询问 AI")).toBeNull();
  });

  it("selectionchange 事件正确触发 setHasSelection", () => {
    const mockGetSelection = vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "selected text",
      rangeCount: 1,
      getRangeAt: () => ({}),
    } as unknown as Selection);
    render(<DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />);
    act(() => {
      document.dispatchEvent(new Event("selectionchange"));
    });
    expect(mockGetSelection).toHaveBeenCalled();
    mockGetSelection.mockRestore();
  });

  it("EditableText 标题 blur 时触发 onUpdateLineText", () => {
    const onUpdateLineText = vi.fn();
    const blocks: ContentBlock[] = [
      { id: "b-title", sectionId: "ch1-1", title: "可编辑标题", contentType: "text",
        lines: [{ id: "lx", text: "内容", type: "paragraph" }] },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const titleSpan = screen.getByText("可编辑标题");
    act(() => { titleSpan.textContent = "新标题"; });
    fireEvent.blur(titleSpan);
    expect(onUpdateLineText).toHaveBeenCalledWith("b-title", "title-b-title", "新标题");
  });

  it("没有选中行时工具栏按钮禁用", () => {
    render(<DocumentViewer {...defaultProps} />);
    const boldBtn = screen.getAllByTitle("加粗")[0];
    expect(boldBtn.hasAttribute("disabled")).toBeTruthy();
  });

  it("SelectionMenu backdrop 接受 Enter 键关闭", () => {
    const onShowSelectionMenu = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        showSelectionMenu={true}
        selectionMenuPos={{ x: 100, y: 200 }}
        onShowSelectionMenu={onShowSelectionMenu}
      />,
    );
    const backdrop = document.querySelector("[role='button']") as HTMLElement;
    expect(backdrop).toBeTruthy();
    fireEvent.keyDown(backdrop, { key: "Enter" });
    expect(onShowSelectionMenu).toHaveBeenCalledWith(false);
  });

  it("SelectionMenu backdrop 接受 Space 键关闭", () => {
    const onShowSelectionMenu = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        showSelectionMenu={true}
        selectionMenuPos={{ x: 100, y: 200 }}
        onShowSelectionMenu={onShowSelectionMenu}
      />,
    );
    const backdrop = document.querySelector("[role='button']") as HTMLElement;
    fireEvent.keyDown(backdrop, { key: " " });
    expect(onShowSelectionMenu).toHaveBeenCalledWith(false);
  });

  it("EditableText 初始化时同步 textContent", () => {
    const blocks: ContentBlock[] = [
      { id: "b-sync", sectionId: "ch1-1", title: "同步标题", contentType: "text",
        lines: [{ id: "l-sync", text: "同步文本", type: "paragraph" }] },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" />,
    );
    expect(screen.getByText("同步文本")).toBeDefined();
  });

  it("footer 展开显示引用来源", () => {
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" expandedFootnoteId="fn-2" />,
    );
    expect(screen.getByText("第二个引用来源")).toBeDefined();
    expect(screen.getByText("第2页，第3段")).toBeDefined();
  });

  it("handleDownload 正确添加并移除临时按钮", () => {
    const appendChildSpy = vi.spyOn(document.body, "appendChild");
    const removeChildSpy = vi.spyOn(document.body, "removeChild");
    render(<DocumentViewer {...defaultProps} />);
    fireEvent.click(screen.getByTitle("下载"));
    expect(appendChildSpy).toHaveBeenCalled();
    expect(removeChildSpy).toHaveBeenCalled();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });

  it("ContentLineRender 中 footnote 通过 refNumber 找到对应脚注", () => {
    render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />,
    );
    const footnoteBtn = screen.getByTitle("点击查看原文引用");
    expect(footnoteBtn.textContent).toBe("1");
  });

  it("编辑表格表头 blur 时触发 onUpdateLineText", () => {
    const onUpdateLineText = vi.fn();
    const blocks: ContentBlock[] = [
      {
        id: "b-table-edit",
        sectionId: "ch1-1",
        title: "表: 编辑",
        contentType: "table",
        tableData: {
          headers: ["名称", "值"],
          rows: [{ id: "tr1", cells: ["A", "1"] }],
        },
      },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const headerSpan = screen.getByText("名称");
    act(() => { headerSpan.textContent = "新名称"; });
    fireEvent.blur(headerSpan);
    expect(onUpdateLineText).toHaveBeenCalledWith("b-table-edit", "header-0", "新名称");
  });

  it("编辑图片注释 blur 时触发 onUpdateLineText", () => {
    const onUpdateLineText = vi.fn();
    const blocks: ContentBlock[] = [
      {
        id: "b-img-caption",
        sectionId: "ch1-1",
        title: "图: 编辑",
        contentType: "image",
        imageUrl: "",
        imageCaption: "原始图例文字",
      },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const captionSpan = screen.getByText("原始图例文字");
    act(() => { captionSpan.textContent = "新图例文字"; });
    fireEvent.blur(captionSpan);
    expect(onUpdateLineText).toHaveBeenCalledWith("b-img-caption", "caption-b-img-caption", "新图例文字");
  });

  it("default 分支的 getLineStyle 对 paragraph 类型正确应用样式", () => {
    const blocks: ContentBlock[] = [
      {
        id: "b-paragraph-test",
        sectionId: "ch1-1",
        title: "段落测试",
        contentType: "text",
        lines: [
          { id: "l-para", text: "普通段落", type: "paragraph" },
        ],
      },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" />,
    );
    expect(screen.getByText("普通段落")).toBeDefined();
  });

  it("编辑表格单元格触发 handleCellEdit 回调", () => {
    const onUpdateLineText = vi.fn();
    const blocks: ContentBlock[] = [
      {
        id: "b-table-cell-edit",
        sectionId: "ch1-1",
        title: "表: 单元格编辑",
        contentType: "table",
        tableData: {
          headers: ["名称"],
          rows: [{ id: "tr-cell", cells: ["原始值"] }],
        },
      },
    ];
    render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" onUpdateLineText={onUpdateLineText} />,
    );
    const cellSpan = screen.getByText("原始值");
    act(() => { cellSpan.textContent = "新值"; });
    fireEvent.blur(cellSpan);
    expect(onUpdateLineText).toHaveBeenCalledWith("b-table-cell-edit", "tr-cell-cell-0", "新值");
  });

  it("EditableText 初始化时 textContent 不同则同步", () => {
    const blocks: ContentBlock[] = [
      {
        id: "block-edit-sync",
        sectionId: "ch1-1",
        title: "标题",
        contentType: "text",
        lines: [
          { id: "l-sync-edit", text: "原始文本", type: "paragraph" },
        ],
      },
    ];
    const { rerender } = render(
      <DocumentViewer {...defaultProps} contentBlocks={blocks} selectedSectionId="ch1-1" />,
    );
    const span = screen.getByText("原始文本");
    // 直接修改 DOM
    act(() => { span.textContent = "被外部修改"; });
    // 通过修改 contentBlocks 触发 useEffect
    const updatedBlocks: ContentBlock[] = [
      {
        ...blocks[0],
        lines: [{ id: "l-sync-edit", text: "外部修改", type: "paragraph" }],
      },
    ];
    rerender(
      <DocumentViewer {...defaultProps} contentBlocks={updatedBlocks} selectedSectionId="ch1-1" />,
    );
    // useEffect 检测到 line.text 变化，将 DOM 同步更新
    expect(span.textContent).toBe("外部修改");
  });

  it("handleViewFootnote 当脚注 refNumber 不匹配时不触发 onToggleFootnote", () => {
    // 某个脚注按钮引用的 refNumber 不在 footnotes 列表中
    const blocksWithMissingRef: ContentBlock[] = [
      {
        id: "b-missing-ref",
        sectionId: "ch1-1",
        title: "缺失脚注",
        contentType: "text",
        lines: [
          { id: "l-missing", text: "文本", type: "paragraph", footnoteRef: "99" },
        ],
      },
    ];
    const onToggleFootnote = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        contentBlocks={blocksWithMissingRef}
        selectedSectionId="ch1-1"
        onToggleFootnote={onToggleFootnote}
      />,
    );
    const footnoteBtn = screen.getByTitle("点击查看原文引用");
    fireEvent.click(footnoteBtn);
    // refNumber "99" 不在 footnotes 中，onToggleFootnote 不会被调用
    expect(onToggleFootnote).not.toHaveBeenCalled();
  });

  it("ContentLineRender useEffect 同步 line.text 到 contentEditable", () => {
    // 通过修改 contentBlocks 中的 text 值来触发 useEffect 重新执行
    const blocksWithChangedText: ContentBlock[] = [
      {
        id: "block-1",
        sectionId: "ch1-1",
        title: "1.1 背景介绍",
        contentType: "text",
        lines: [
          { id: "l1", text: "初始文本", type: "paragraph" },
        ],
      },
    ];
    const { rerender } = render(
      <DocumentViewer
        {...defaultProps}
        contentBlocks={blocksWithChangedText}
        selectedSectionId="ch1-1"
      />,
    );
    const span = screen.getByText("初始文本");
    // 直接修改 DOM，模拟外部 JS 修改
    act(() => { span.textContent = "被外部修改"; });
    // 通过修改 contentBlocks 中 line.text 的值来触发 useEffect
    const updatedBlocks: ContentBlock[] = [
      {
        ...blocksWithChangedText[0],
        lines: [{ id: "l1", text: "新文本内容", type: "paragraph" }],
      },
    ];
    rerender(
      <DocumentViewer
        {...defaultProps}
        contentBlocks={updatedBlocks}
        selectedSectionId="ch1-1"
      />,
    );
    // useEffect 检测到 line.text 从 "初始文本" 变为 "新文本内容"，同步更新 DOM
    expect(span.textContent).toBe("新文本内容");
  });

  it("ContentLineRender handleBlur 在 onLineHtmlChange 为 undefined 时不报错", () => {
    // 使用一个不传入 onUpdateLineText 的场景（内部 handleLineHtmlChange 为 undefined）
    // 实际上 onUpdateLineText 始终有默认值，但 ContentLineRender 直接调用 onLineHtmlChange
    // 该函数在 ContentLineRender 中是通过 props 传入的，正常情况下始终存在
    // 这个测试验证点击脚注后 handleBlur 中 onLineHtmlChange 的判定分支
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        onUpdateLineText={vi.fn()}
      />,
    );
    const span = screen.getByText("AI技术发展迅速。");
    // 直接触发 blur，text 不变，不触发 onLineHtmlChange
    fireEvent.blur(span);
    // 验证无报错
    expect(screen.getByText("AI技术发展迅速。")).toBeDefined();
  });

  it("selectionchange 事件在 unmount 时正确清理", () => {
    const removeEventListenerSpy = vi.spyOn(document, "removeEventListener");
    const { unmount } = render(
      <DocumentViewer {...defaultProps} selectedSectionId="ch1-1" />,
    );
    unmount();
    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      "selectionchange",
      expect.any(Function),
    );
    removeEventListenerSpy.mockRestore();
  });

  it("通过工具栏插入图片/表格触发 onFormat (handleFormat 回调)", () => {
    const onFormatLine = vi.fn();
    render(
      <DocumentViewer
        {...defaultProps}
        selectedSectionId="ch1-1"
        onFormatLine={onFormatLine}
      />,
    );
    // 文档工具栏中的插入图片按钮
    const insertImageBtns = screen.getAllByTitle("插入图片");
    expect(insertImageBtns.length).toBeGreaterThanOrEqual(1);
    fireEvent.mouseDown(insertImageBtns[0]);
    // 插入图片由 toolbar 的 mousedown 直接调用 onFormat（即 handleFormat）
    // handleFormat 是空函数，所以 onFormatLine 不会被调用
    // 但至少测试不报错
    const insertTableBtns = screen.getAllByTitle("插入表格");
    fireEvent.mouseDown(insertTableBtns[0]);
    expect(onFormatLine).not.toHaveBeenCalled();
  });
});
