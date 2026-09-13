import type { SectionNode, ContentBlock, FootnoteReference, TextSelection } from "../../types/section";
import type { ChatMessage } from "../../types/chat";

export type TextFormatAction = "bold" | "italic" | "underline" | "strikethrough" | "highlight" | "align-left" | "align-center" | "align-right" | "align-justify" | "insert-image" | "insert-table";

export interface WorkspaceState {
  sections: SectionNode[];
  selectedSectionId: string | null;
  contentBlocks: ContentBlock[];
  chatMessages: ChatMessage[];
  chatInput: string;
  loading: boolean;
  footnotes: FootnoteReference[];
  expandedFootnoteId: string | null;
  currentSelection: TextSelection | null;
  showSelectionMenu: boolean;
  selectionMenuPos: { x: number; y: number } | null;
  quotedText: string | null;
  tokenUsage: number;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  leftPanelWidth: number;
  rightPanelWidth: number;
  documentTitle: string;
}

export type WorkspaceAction =
  | { type: "SELECT_SECTION"; sectionId: string }
  | { type: "TOGGLE_SECTION_EXPAND"; sectionId: string }
  | { type: "TOGGLE_HIGHLIGHT"; blockId: string; lineId: string }
  | { type: "UPDATE_LINE_TEXT"; blockId: string; lineId: string; text: string }
  | { type: "FORMAT_LINE"; blockId: string; lineId: string; format: TextFormatAction }
  | { type: "TOGGLE_FOOTNOTE"; footnoteId: string }
  | { type: "SET_SELECTION"; selection: TextSelection | null }
  | { type: "SHOW_SELECTION_MENU"; show: boolean; pos?: { x: number; y: number } }
  | { type: "QUOTE_SELECTION" }
  | { type: "CLEAR_QUOTE" }
  | { type: "SET_CHAT_INPUT"; text: string }
  /** 本地模拟回复（离线开发用）；真实链路走下面两个 action */
  | { type: "SEND_CHAT_MESSAGE"; message: ChatMessage }
  /** 追加一条消息（真实问答链路：先追加用户提问，拿到回答后再追加助手消息） */
  | { type: "APPEND_CHAT_MESSAGE"; message: ChatMessage }
  /** 用回读到的历史替换消息列表（打开工作区时恢复上次对话） */
  | { type: "SET_CHAT_MESSAGES"; messages: ChatMessage[] }
  /** 累加真实 token 用量（后端 provider 回传时才有） */
  | { type: "ADD_TOKEN_USAGE"; usage: number }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "SET_TOKEN_USAGE"; usage: number }
  | { type: "TOGGLE_LEFT_PANEL" }
  | { type: "TOGGLE_RIGHT_PANEL" }
  | { type: "SET_LEFT_WIDTH"; width: number }
  | { type: "SET_RIGHT_WIDTH"; width: number }
  | { type: "SET_LANG_DATA"; sections: SectionNode[]; contentBlocks: ContentBlock[] }
  | { type: "SET_DOC_TITLE"; title: string };

export interface SectionTreeProps {
  sections: SectionNode[];
  selectedSectionId: string | null;
  onSelect: (sectionId: string) => void;
  onToggle: (sectionId: string) => void;
}

export interface DocumentViewerProps {
  contentBlocks: ContentBlock[];
  selectedSectionId: string | null;
  footnotes: FootnoteReference[];
  expandedFootnoteId: string | null;
  currentSelection: TextSelection | null;
  showSelectionMenu: boolean;
  selectionMenuPos: { x: number; y: number } | null;
  onToggleHighlight: (blockId: string, lineId: string) => void;
  onUpdateLineText: (blockId: string, lineId: string, text: string) => void;
  onFormatLine: (blockId: string, lineId: string, format: TextFormatAction) => void;
  onToggleFootnote: (footnoteId: string) => void;
  onSelectText: (selection: TextSelection | null) => void;
  onShowSelectionMenu: (show: boolean, pos?: { x: number; y: number }) => void;
  onQuoteSelection: () => void;
}

export interface ChatPanelProps {
  messages: ChatMessage[];
  input: string;
  quotedText: string | null;
  tokenUsage: number;
  onInputChange: (text: string) => void;
  onSend: () => void;
  onClearQuote: () => void;
  loading: boolean;
  /** 后端返回的错误文案（如"尚未配置可用的模型"）；为空表示没有错误 */
  error?: string | null;
}

export interface WorkspacePageProps {
  /** 工作区唯一标识（可选，后续可根据此加载不同数据） */
  workspaceId?: string;
}
