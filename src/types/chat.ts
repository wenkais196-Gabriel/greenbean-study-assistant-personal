/** 聊天消息角色 */
export type MessageRole = "user" | "assistant";

/**
 * 回答引用的检索来源。
 *
 * 后端 `source_context` 是 snake_case（Python 侧字段名），进前端后统一转成 camelCase，
 * 组件里就不用记两套命名。
 */
export interface ChatSource {
  chunkId: string;
  documentId: string;
  /** 命中的页码；拿不到时为 null */
  pageNumber: number | null;
  /** 章节路径（如 ["第二章", "2.1"]）；没有标题结构时为 null */
  headingPath: string[] | null;
  /** 向量距离；越小越相似，null 表示后端没给 */
  distance: number | null;
}

/** 单条聊天消息 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  /** 消息发送时间 ISO 字符串 */
  createdAt: string;
  /** 助手回答引用的资料片段（用户消息没有，历史里的旧消息也可能没有） */
  sources?: ChatSource[];
}

/** 聊天会话 */
export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  /** 关联的文档/工作区 ID（可选） */
  contextId?: string;
}
