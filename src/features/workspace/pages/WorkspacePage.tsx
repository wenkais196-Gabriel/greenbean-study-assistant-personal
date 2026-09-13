import { useReducer, useCallback, useEffect, useMemo, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import SectionTree from "../components/left/SectionTree";
import FileManager, { type FileItem } from "../components/left/FileManager";
import DocumentViewer from "../components/center/DocumentViewer";
import ChatPanel from "../components/right/ChatPanel";
import ResizableHandle from "../components/shared/ResizableHandle";
import ProviderPanel from "../../provider/components/ProviderPanel";
import type { WorkspaceState, WorkspaceAction, WorkspacePageProps, TextFormatAction } from "../type";
import type { SectionNode, ContentBlock, ContentLine, FootnoteReference } from "../../../types/section";
import type { ChatMessage, ChatSource } from "../../../types/chat";
import { ApiError } from "../../../lib/apiClient";
import { askQuestion, fetchSessionMessages, DEFAULT_WORKSPACE_ID } from "../../chat/api/chatApi";
import { getOrCreateSessionId } from "../../chat/sessionStore";
import { fetchDocumentUnits, listDocuments, type DocumentSummary, type DocumentUnit } from "../../document/api/documentApi";

/** 随请求带给后端的历史消息条数：够维持指代，又不至于把 prompt 撑爆。 */
const MAX_HISTORY_MESSAGES = 8;

function getLocalizedSections(): SectionNode[] {
  return [
    { id: "ch1", title: "第一章：引言", index: "1", expanded: true, children: [
      { id: "ch1-1", title: "背景介绍", index: "1.1" },
      { id: "ch1-2", title: "研究意义", index: "1.2" },
      { id: "ch1-3", title: "论文结构", index: "1.3" },
    ]},
    { id: "ch2", title: "第二章：理论基础", index: "2", expanded: true, children: [
      { id: "ch2-1", title: "概念定义", index: "2.1" },
      { id: "ch2-2", title: "相关研究", index: "2.2" },
    ]},
    { id: "ch3", title: "第三章：方法论", index: "3", expanded: false, children: [
      { id: "ch3-1", title: "数据采集", index: "3.1" },
      { id: "ch3-2", title: "分析方法", index: "3.2" },
      { id: "ch3-3", title: "验证方案", index: "3.3" },
    ]},
    { id: "ch4", title: "第四章：实验与结果", index: "4" },
    { id: "ch5", title: "第五章：结论", index: "5" },
  ];
}

function getLocalizedContent(): ContentBlock[] {
  return [
    { id: "block-ch1-1", sectionId: "ch1-1", title: "1.1 背景介绍", contentType: "text",
      lines: [
        { id: "l1", text: "近年来，人工智能技术取得了飞速发展，深刻改变了各行各业的面貌。", type: "paragraph", footnoteRef: "1" },
        { id: "l2", text: "在教育领域，AI 技术的应用尤为引人注目。", type: "paragraph" },
        { id: "l3", text: "本节将介绍本研究的基本背景和动机。", type: "heading", level: 2 },
        { id: "l4", text: "• 全球教育数字化转型趋势", type: "list" },
        { id: "l5", text: "• 在法中国留学生面临的语言与学习障碍", type: "list" },
        { id: "l6", text: "• 现有工具与解决方案的不足", type: "list", footnoteRef: "2" },
      ]},
    { id: "block-table-1", sectionId: "ch2-1", title: "表1：主流AI教育平台对比", contentType: "table",
      tableData: { headers: ["平台名称", "语言支持", "AI 功能", "定价"],
        rows: [
          { id: "tr1", cells: ["Coursera", "多语言", "课程推荐", "$59/月"] },
          { id: "tr2", cells: ["Duolingo", "40+语言", "自适应学习", "免费+Premium"] },
          { id: "tr3", cells: ["GreenBean", "中/法", "深度解析+问答", "免费"] },
        ]},
    },
    { id: "block-image-1", sectionId: "ch2-1", title: "图1：AI教育市场规模预测", contentType: "image", imageUrl: "",
      imageCaption: "全球AI教育市场将在2025年突破500亿美元（示意图）" },
    { id: "block-ch1-2", sectionId: "ch1-2", title: "1.2 研究意义", contentType: "text",
      lines: [
        { id: "l7", text: "本研究具有重要的理论意义和实践价值。", type: "paragraph" },
        { id: "l8", text: "从理论层面看，本研究探索了 AI 辅助学习的新范式。", type: "paragraph" },
        { id: "l9", text: "从实践层面看，本研究为留学生提供了切实可行的学习工具。", type: "paragraph" },
      ]},
    { id: "block-ch2-1", sectionId: "ch2-1", title: "2.1 概念定义", contentType: "text",
      lines: [
        { id: "l10", text: "本节定义了研究中使用的核心概念。", type: "paragraph" },
        { id: "l11", text: "定义 1（智能学习助手）：...", type: "code" },
        { id: "l12", text: "定义 2（知识图谱）：...", type: "code" },
      ]},
  ];
}

const initialFootnotes: FootnoteReference[] = [
  { id: "fn-1", refNumber: "1", sourceText: "Gartner预测到2025年AI在教育领域创造超过500亿美元的市场价值。", sourceDesc: "第1页，第1段" },
  { id: "fn-2", refNumber: "2", sourceText: "现有针对在法中国留学生的法语AI辅导产品仍属空白。", sourceDesc: "第1页，第6段" },
];

/** 一页在界面上的标题：有页码用页码，没有就退回顺序号。 */
function unitLabel(unit: DocumentUnit): string {
  return unit.pageNumber != null ? `第 ${unit.pageNumber} 页` : `第 ${unit.sequenceIndex + 1} 节`;
}

/** 内容单元 → 左侧导航节点。章节树暂缓（见 docs 里的 BDD 假设），先按"页"列出。 */
function unitsToSections(units: DocumentUnit[]): SectionNode[] {
  return units.map((unit) => ({ id: unit.unitId, title: unitLabel(unit) }));
}

/** 内容单元 → 中间正文块（`sectionId` 用单元 ID，`DocumentViewer` 按它过滤）。 */
function unitsToBlocks(units: DocumentUnit[]): ContentBlock[] {
  return units.map((unit) => ({
    id: unit.unitId,
    sectionId: unit.unitId,
    pageNumber: unit.pageNumber,
    title: unitLabel(unit),
    contentType: "text",
    lines: unit.textContent
      .split("\n")
      .map((text) => text.trim())
      .filter((text) => text.length > 0)
      .map((text, index): ContentLine => ({ id: `${unit.unitId}-l${index}`, text, type: "paragraph" })),
  }));
}

/** 后端文件类型枚举 → 文件面板的徽标类型。 */
const FILE_TYPE_BADGES: Record<string, FileItem["type"]> = {
  pdf: "PDF", docx: "DOC", pptx: "PPT", image: "IMG", text: "TXT", other: "TXT",
};

/** 后端处理状态 → 文件面板的状态点。 */
const FILE_STATUSES: Record<string, FileItem["status"]> = {
  parsed: "parsed", indexed: "parsed", uploaded: "parsing", failed: "pending",
};

/** 后端文档摘要 → 左侧文件面板的一条。 */
function toFileItem(document: DocumentSummary): FileItem {
  return {
    id: document.documentId,
    name: document.title,
    type: FILE_TYPE_BADGES[document.fileType] ?? "TXT",
    // 真实文档没有分类：统一归到默认展开的那个文件夹
    category: "course",
    size: document.pageCount != null ? `${document.pageCount} 页` : "—",
    date: document.createdAt.slice(0, 10),
    status: FILE_STATUSES[document.status] ?? "pending",
  };
}

/**
 * 滚动到某个内容块。
 *
 * `data-block-id` 才是 `DocumentViewer` 实际渲染的属性 —— 旧代码查的是 `id="block-..."`，
 * 所以这段滚动一直没生效（元素永远查不到）。
 */
function scrollToBlock(unitId: string) {
  setTimeout(() => {
    try {
      document
        .querySelector(`[data-block-id="${unitId}"]`)
        ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    } catch {
      // jsdom 等环境没有 scrollIntoView：滚动失败不该影响定位本身
    }
  }, 50);
}

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case "SELECT_SECTION": return { ...state, selectedSectionId: action.sectionId };
    case "TOGGLE_SECTION_EXPAND": {
      const toggleExpand = (nodes: SectionNode[]): SectionNode[] => nodes.map((n) => {
        if (n.id === action.sectionId) return { ...n, expanded: !(n.expanded ?? true) };
        if (n.children) return { ...n, children: toggleExpand(n.children) };
        return n;
      });
      return { ...state, sections: toggleExpand(state.sections) };
    }
    case "TOGGLE_HIGHLIGHT":
      return { ...state, contentBlocks: state.contentBlocks.map((b) => b.id !== action.blockId || !b.lines ? b : { ...b, lines: b.lines.map((l: ContentLine) => l.id === action.lineId ? { ...l, highlighted: !l.highlighted } : l) }) };
    case "UPDATE_LINE_TEXT":
      return { ...state, contentBlocks: state.contentBlocks.map((b) => b.id !== action.blockId || !b.lines ? b : { ...b, lines: b.lines.map((l: ContentLine) => l.id === action.lineId ? { ...l, text: action.text } : l) }) };
    case "FORMAT_LINE":
      return { ...state, contentBlocks: state.contentBlocks.map((b) => {
        if (b.id !== action.blockId || !b.lines) return b;
        return { ...b, lines: b.lines.map((l: ContentLine) => {
          if (l.id !== action.lineId) return l;
          const f = action.format;
          if (f === "bold") return { ...l, bold: !l.bold };
          if (f === "italic") return { ...l, italic: !l.italic };
          if (f === "underline") return { ...l, underline: !l.underline };
          if (f === "strikethrough") return { ...l, strikethrough: !l.strikethrough };
          if (f === "highlight") return { ...l, highlighted: !l.highlighted };
          if (f === "align-left") return { ...l, align: l.align === "left" ? undefined : "left" };
          if (f === "align-center") return { ...l, align: l.align === "center" ? undefined : "center" };
          if (f === "align-right") return { ...l, align: l.align === "right" ? undefined : "right" };
          return l;
        }) as ContentLine[] };
      })};
    case "SET_LANG_DATA": return { ...state, sections: action.sections, contentBlocks: action.contentBlocks };
    case "TOGGLE_FOOTNOTE": return { ...state, expandedFootnoteId: state.expandedFootnoteId === action.footnoteId ? null : action.footnoteId };
    case "SET_SELECTION": return { ...state, currentSelection: action.selection };
    case "SHOW_SELECTION_MENU": return { ...state, showSelectionMenu: action.show, selectionMenuPos: action.pos ?? null };
    case "QUOTE_SELECTION": return { ...state, quotedText: state.currentSelection?.text ?? null, showSelectionMenu: false, currentSelection: null, selectionMenuPos: null };
    case "CLEAR_QUOTE": return { ...state, quotedText: null };
    case "SET_CHAT_INPUT": return { ...state, chatInput: action.text };
    case "SEND_CHAT_MESSAGE": {
      const userMsg: ChatMessage = { id: `msg-${Date.now()}`, role: "user", content: state.quotedText ? `[引用] ${state.quotedText}\n\n${state.chatInput}` : state.chatInput, createdAt: new Date().toISOString() };
      const assistantMsg: ChatMessage = { id: `msg-${Date.now() + 1}`, role: "assistant", content: state.quotedText ? `针对你引用的内容「${state.quotedText.substring(0, 30)}...」回答如下：\n\n这是结合上下文的模拟回复。` : `这是对「${state.chatInput}」的模拟回复。`, createdAt: new Date().toISOString() };
      return { ...state, chatMessages: [...state.chatMessages, userMsg, assistantMsg], chatInput: "", quotedText: null, tokenUsage: state.tokenUsage + 150 };
    }
    case "APPEND_CHAT_MESSAGE": return { ...state, chatMessages: [...state.chatMessages, action.message] };
    case "SET_CHAT_MESSAGES": return { ...state, chatMessages: action.messages };
    case "ADD_TOKEN_USAGE": return { ...state, tokenUsage: state.tokenUsage + action.usage };
    case "SET_LOADING": return { ...state, loading: action.loading };
    case "SET_TOKEN_USAGE": return { ...state, tokenUsage: action.usage };
    case "TOGGLE_LEFT_PANEL": return { ...state, leftCollapsed: !state.leftCollapsed };
    case "TOGGLE_RIGHT_PANEL": return { ...state, rightCollapsed: !state.rightCollapsed, rightPanelWidth: state.rightCollapsed ? state.rightPanelWidth || 302 : 0 };
    case "SET_LEFT_WIDTH": return { ...state, leftPanelWidth: Math.max(160, Math.min(302, action.width)) };
    case "SET_RIGHT_WIDTH": {
      const w = Math.min(340, Math.max(189, action.width));
      return { ...state, rightPanelWidth: w, rightCollapsed: false };
    }
    case "SET_DOC_TITLE": return { ...state, documentTitle: action.title };
    default: return state;
  }
}

function WorkspacePage({ workspaceId = DEFAULT_WORKSPACE_ID }: WorkspacePageProps) {
  const titleRef = useRef<HTMLInputElement>(null);
  const rightDragRef = useRef(false);
  const rightWidthRef = useRef(302);
  const rightDragClientXRef = useRef(0);

  const [leftMode, setLeftMode] = useState<"files" | "sections" | null>("files");
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentError, setDocumentError] = useState<string | null>(null);
  // 会话 ID：存在本地，刷新后复用同一个（否则每次都算新会话，后端历史永远拉不到）。
  // `useState` 的惰性初始化保证只生成/读取一次。
  const [sessionId] = useState(() => getOrCreateSessionId());

  const [state, dispatch] = useReducer(workspaceReducer, {
    sections: getLocalizedSections(), selectedSectionId: null, contentBlocks: getLocalizedContent(),
    chatMessages: [], chatInput: "", loading: false, footnotes: initialFootnotes,
    expandedFootnoteId: null, currentSelection: null, showSelectionMenu: false,
    selectionMenuPos: null, quotedText: null, tokenUsage: 0,
    leftCollapsed: false, rightCollapsed: false,
    leftPanelWidth: 256, rightPanelWidth: 302, documentTitle: "cours-analyse-s1.pdf",
  });

  rightWidthRef.current = state.rightPanelWidth;

  /** 左侧文件列表：后端文档摘要 → 文件面板的形状。 */
  const documentFiles = useMemo(() => documents.map(toFileItem), [documents]);

  const d = useCallback((s: string) => dispatch({ type: "SELECT_SECTION", sectionId: s } as any), []);
  const togg = useCallback((s: string) => dispatch({ type: "TOGGLE_SECTION_EXPAND", sectionId: s } as any), []);
  const th = useCallback((b: string, l: string) => dispatch({ type: "TOGGLE_HIGHLIGHT", blockId: b, lineId: l } as any), []);
  const ut = useCallback((b: string, l: string, t: string) => dispatch({ type: "UPDATE_LINE_TEXT", blockId: b, lineId: l, text: t } as any), []);
  const fmt = useCallback((b: string, l: string, f: TextFormatAction) => dispatch({ type: "FORMAT_LINE", blockId: b, lineId: l, format: f } as any), []);
  const tf = useCallback((id: string) => dispatch({ type: "TOGGLE_FOOTNOTE", footnoteId: id } as any), []);
  const sel = useCallback((s: any) => dispatch({ type: "SET_SELECTION", selection: s } as any), []);
  const sm = useCallback((s: boolean, p?: { x: number; y: number }) => dispatch({ type: "SHOW_SELECTION_MENU", show: s, pos: p } as any), []);
  const qs = useCallback(() => dispatch({ type: "QUOTE_SELECTION" } as any), []);
  const ci = useCallback((t: string) => dispatch({ type: "SET_CHAT_INPUT", text: t } as any), []);
  const cq = useCallback(() => dispatch({ type: "CLEAR_QUOTE" } as any), []);

  /**
   * 打开工作区时恢复上次对话。
   *
   * 会话 ID 来自本地存储，历史在后端 —— 后端落库（C2）只有配上这一步，刷新后才真的"还在"。
   * 404 表示这个会话还没落过库（首次打开，或换了新 ID），当作"没有历史"而不是错误。
   */
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const history = await fetchSessionMessages(sessionId);
        if (!cancelled && history.length > 0) {
          dispatch({ type: "SET_CHAT_MESSAGES", messages: history });
        }
      } catch (error) {
        if (cancelled || (error instanceof ApiError && error.status === 404)) return;
        setChatError(error instanceof Error ? error.message : "加载历史对话失败");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  /**
   * 打开工作区时拉一次真实文档列表。
   *
   * 失败要显示出来：后端没起来时左侧不该是一片空白，让人以为"没有资料"。
   */
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const docs = await listDocuments();
        if (!cancelled) setDocuments(docs);
      } catch (error) {
        if (!cancelled) {
          setDocumentError(error instanceof Error ? error.message : "加载文档列表失败");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * 提问：先乐观追加用户消息，再调后端（检索 + 生成），最后追加带来源的助手消息。
   *
   * 失败必须可见：503 是"还没配模型"、status 0 是"后端没起来"，两种都要让用户看到，
   * 而不是留一个转圈或一条假装成功的回复（真实链路取代了原来的本地模拟回复）。
   */
  const send = useCallback(async () => {
    const query = state.chatInput.trim();
    if ((!query && !state.quotedText) || state.loading) return;

    // 引用的原文一起送过去：检索与回答都要用到这段上下文
    const requestText = state.quotedText ? `[引用] ${state.quotedText}\n\n${query}` : query;

    dispatch({ type: "APPEND_CHAT_MESSAGE", message: {
      id: `msg-${Date.now()}-user`, role: "user", content: requestText, createdAt: new Date().toISOString(),
    }});
    dispatch({ type: "SET_CHAT_INPUT", text: "" });
    dispatch({ type: "CLEAR_QUOTE" });
    dispatch({ type: "SET_LOADING", loading: true });
    setChatError(null);

    try {
      const result = await askQuestion({
        sessionId,
        query: requestText,
        workspaceId,
        history: state.chatMessages
          .slice(-MAX_HISTORY_MESSAGES)
          .map((msg) => ({ role: msg.role, content: msg.content })),
      });

      dispatch({ type: "APPEND_CHAT_MESSAGE", message: {
        id: `msg-${Date.now()}-answer`, role: "assistant", content: result.answer,
        createdAt: new Date().toISOString(), sources: result.sources,
      }});

      const tokens = (result.usage?.inputTokens ?? 0) + (result.usage?.outputTokens ?? 0);
      if (tokens > 0) dispatch({ type: "ADD_TOKEN_USAGE", usage: tokens });
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "提问失败，请稍后重试");
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  }, [state.chatInput, state.quotedText, state.loading, state.chatMessages, workspaceId, sessionId]);

  const setLeftW = useCallback((d: number) => dispatch({ type: "SET_LEFT_WIDTH", width: state.leftPanelWidth + d } as any), [state.leftPanelWidth]);

  const setRightW = useCallback((d: number, clientX?: number) => {
    rightDragRef.current = true;
    if (clientX !== undefined) {
      rightDragClientXRef.current = clientX;
    }
    if (state.rightCollapsed) {
      rightWidthRef.current = Math.min(667, Math.max(189, 189 - d));
      dispatch({ type: "SET_RIGHT_WIDTH", width: rightWidthRef.current } as any);
    } else {
      const w = Math.max(0, Math.min(667, rightWidthRef.current - d));
      rightWidthRef.current = w;
      dispatch({ type: "SET_RIGHT_WIDTH", width: w } as any);
    }
  }, [state.rightCollapsed]);

  const toggleLeftPanel = useCallback((mode: "files" | "sections") => {
    setLeftMode((prev) => (prev === mode ? null : mode));
    if (state.leftCollapsed) {
      dispatch({ type: "TOGGLE_LEFT_PANEL" } as any);
    }
  }, [state.leftCollapsed]);

  const toggleRightPanel = useCallback(() => {
    dispatch({ type: "TOGGLE_RIGHT_PANEL" } as any);
  }, []);

  // Close on mouseup when at minimum width and cursor near window right edge, or when below threshold
  useEffect(() => {
    const handleMouseUp = () => {
      if (rightDragRef.current) {
        rightDragRef.current = false;
        const winW = window.innerWidth;
        const cx = rightDragClientXRef.current;
        // collapse if below threshold, or at minimum width and cursor within 50px of window right edge
        if (
          (!state.rightCollapsed && state.rightPanelWidth > 0 && state.rightPanelWidth < 189) ||
          (state.rightPanelWidth <= 189 && cx > 0 && winW - cx < 50)
        ) {
          dispatch({ type: "TOGGLE_RIGHT_PANEL" } as any);
        }
      }
    };
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [state.rightCollapsed, state.rightPanelWidth]);

  // Auto-collapse right panel when viewport is too small to show content properly
  useEffect(() => {
    const handleResize = () => {
      if (state.rightCollapsed) return;
      const toolbarWidth = 40; // left icon bar
      const leftMax = state.leftCollapsed ? 0 : state.leftPanelWidth;
      // Minimum viewport needed: toolbar + left panel width + right panel min (189) + main content min (200)
      const minViewportNeeded = toolbarWidth + leftMax + 189 + 200;
      if (window.innerWidth < minViewportNeeded) {
        dispatch({ type: "TOGGLE_RIGHT_PANEL" } as any);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [state.rightCollapsed, state.leftCollapsed, state.leftPanelWidth]);

  /** 打开一份文档：拉它的内容单元，铺到左侧导航与中间正文。 */
  const openDocument = useCallback(async (documentId: string, title: string) => {
    // 先同步把"打开了哪一份"落到界面上（左侧标题立即切换），再去取内容
    setSelectedFileId(documentId);
    setSelectedFileName(title);

    try {
      const units = await fetchDocumentUnits(documentId);
      dispatch({ type: "SET_LANG_DATA", sections: unitsToSections(units), contentBlocks: unitsToBlocks(units) });
      dispatch({ type: "SET_DOC_TITLE", title });
      // 不自动跳到第一页：与既有行为一致（中间先显示空状态，用户点左侧的页再看正文）
      dispatch({ type: "SELECT_SECTION", sectionId: null } as any);
      setDocumentError(null);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "加载文档内容失败");
    }
  }, []);

  const handleFileSelect = useCallback((fileId: string, fileName: string) => {
    setLeftMode("sections");
    void openDocument(fileId, fileName);
  }, [openDocument]);

  /**
   * 点击 AI 回答里的来源：定位到那份文档的那一页。
   *
   * 来源可能属于**另一份文档**（检索是跨文档的），所以按 `documentId` 重新取单元，
   * 再按 `pageNumber` 找到对应单元；页码缺失或页不存在时给可读提示，而不是静默无反应。
   */
  const revealSource = useCallback(async (source: ChatSource) => {
    if (source.pageNumber == null) {
      setDocumentError("无法定位到原文页码");
      return;
    }

    try {
      const units = await fetchDocumentUnits(source.documentId);
      const target = units.find((unit) => unit.pageNumber === source.pageNumber);
      if (!target) {
        setDocumentError("无法定位到原文页码");
        return;
      }

      const title =
        documents.find((doc) => doc.documentId === source.documentId)?.title ?? source.documentId;
      setSelectedFileId(source.documentId);
      setSelectedFileName(title);
      dispatch({ type: "SET_LANG_DATA", sections: unitsToSections(units), contentBlocks: unitsToBlocks(units) });
      dispatch({ type: "SET_DOC_TITLE", title });
      dispatch({ type: "SELECT_SECTION", sectionId: target.unitId } as any);
      setDocumentError(null);
      scrollToBlock(target.unitId);
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "加载文档内容失败");
    }
  }, [documents]);

  const handleBackToFiles = useCallback(() => {
    setLeftMode("files");
    setSelectedFileId(null);
  }, []);

  const handleSectionSelect = useCallback((id: string) => {
    d(id);
    scrollToBlock(id);
  }, [d]);

  const showLeftPanel = leftMode !== null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="h-screen bg-[#f5f5f7] text-neutral-800 flex flex-col"
    >
      <div className="flex-1 flex overflow-hidden min-h-0">
        <div className="flex">
          <div className="w-12 flex-shrink-0 bg-white/70 border-r border-black/5 flex flex-col items-center py-3 gap-3">
            <button onClick={() => toggleLeftPanel("files")}
              className={`cursor-pointer w-9 h-9 rounded-lg flex items-center justify-center transition-all ${leftMode === "files" ? "bg-black/10 text-neutral-700" : "text-neutral-400 hover:bg-black/10"}`}
              title="文件管理">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
            </button>
            {selectedFileId && (
              <button onClick={() => toggleLeftPanel("sections")}
                className={`cursor-pointer w-9 h-9 rounded-lg flex items-center justify-center transition-all ${leftMode === "sections" ? "bg-black/10 text-neutral-700" : "text-neutral-400 hover:bg-black/10"}`}
                title="章节导航">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" /></svg>
              </button>
            )}
            <button onClick={toggleRightPanel}
              className={`cursor-pointer w-9 h-9 rounded-lg flex items-center justify-center transition-all ${!state.rightCollapsed ? "bg-black/10 text-neutral-700" : "text-neutral-400 hover:bg-black/10"}`}
              title={state.rightCollapsed ? "展开AI聊天" : "收起AI聊天"}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M12 2a7 7 0 0 0-7 7c0 2.4 1.2 4.5 3 5.7V17h8v-2.3c1.8-1.3 3-3.4 3-5.7a7 7 0 0 0-7-7z" />
                <line x1="9" y1="17" x2="15" y2="17" /><line x1="10" y1="20" x2="14" y2="20" />
              </svg>
            </button>
            <div className="flex-1" />
            <button onClick={() => setShowSettings(true)}
              className="cursor-pointer w-9 h-9 rounded-lg flex items-center justify-center text-neutral-400 hover:bg-black/10 transition-all" title="设置">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>

          <motion.aside
            animate={{ width: !showLeftPanel ? 0 : state.leftPanelWidth, opacity: !showLeftPanel ? 0 : 1 }}
            transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
            className="flex-shrink-0 bg-white/70 border-r border-black/5 backdrop-blur-xl overflow-hidden"
          >
            {showLeftPanel && (
              <div style={{ width: state.leftPanelWidth }} className="h-full relative overflow-hidden">
                <AnimatePresence mode="wait">
                  {leftMode === "files" && (
                    <motion.div key="files-panel" initial={{ x: -state.leftPanelWidth }} animate={{ x: 0 }} exit={{ x: -state.leftPanelWidth }}
                      transition={{ duration: 0.35, ease: [0.25, 0.1, 0.25, 1] }} className="absolute inset-0 bg-white/70">
                      <FileManager files={documentFiles} onFileSelectWithName={handleFileSelect} />
                    </motion.div>
                  )}
                  {leftMode === "sections" && selectedFileId && (
                    <motion.div key="sections-panel" initial={{ x: state.leftPanelWidth }} animate={{ x: 0 }} exit={{ x: state.leftPanelWidth }}
                      transition={{ duration: 0.35, ease: [0.25, 0.1, 0.25, 1] }} className="absolute inset-0 bg-white/70">
                      <SectionTree sections={state.sections} selectedSectionId={state.selectedSectionId}
                        onSelect={handleSectionSelect} onToggle={togg} onBack={handleBackToFiles} title={selectedFileName} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </motion.aside>
        </div>

        {showLeftPanel && <ResizableHandle onResize={setLeftW} position="left" />}

        <main className="flex-1 min-w-0 min-h-0">
          {documentError && (
            <div role="alert" className="mx-4 mt-3 px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-xs text-red-600 break-words">
              {documentError}
            </div>
          )}
          <DocumentViewer contentBlocks={state.contentBlocks} selectedSectionId={state.selectedSectionId}
            footnotes={state.footnotes} expandedFootnoteId={state.expandedFootnoteId}
            currentSelection={state.currentSelection} showSelectionMenu={state.showSelectionMenu} selectionMenuPos={state.selectionMenuPos}
            onToggleHighlight={th} onUpdateLineText={ut} onFormatLine={fmt}
            onToggleFootnote={tf} onSelectText={sel} onShowSelectionMenu={sm} onQuoteSelection={qs} />
        </main>

        <ResizableHandle onResize={setRightW} position="right" onDoubleClick={toggleRightPanel} />
        <motion.aside
          animate={{ width: state.rightCollapsed ? 0 : state.rightPanelWidth, opacity: state.rightCollapsed ? 0 : 1 }}
          transition={rightDragRef.current ? { duration: 0 } : { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
          className="flex-shrink-0 bg-white/70 border-l border-black/5 backdrop-blur-xl overflow-hidden"
          style={{ maxWidth: "100vw" }}
        >
          {!state.rightCollapsed && (
            <div style={{ width: state.rightPanelWidth, maxWidth: "100%" }} className="h-full overflow-hidden relative">
              <ChatPanel messages={state.chatMessages} input={state.chatInput} quotedText={state.quotedText} tokenUsage={state.tokenUsage}
                onInputChange={ci} onSend={send} onClearQuote={cq} loading={state.loading} error={chatError}
                onSourceClick={revealSource} />
            </div>
          )}
        </motion.aside>
      </div>

      {showSettings && <ProviderPanel onClose={() => setShowSettings(false)} />}
    </motion.div>
  );
}

export default WorkspacePage;
