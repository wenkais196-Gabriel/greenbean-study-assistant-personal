/** 章节树中的单个章节节点 */
export interface SectionNode {
  id: string;
  title: string;
  /** 子章节列表（树形结构） */
  children?: SectionNode[];
  /** 章节在文档中的序号，如 "1.2" */
  index?: string;
  /** 是否展开（有子章节时） */
  expanded?: boolean;
}

/** 文档内容中的一段文本行 */
export interface ContentLine {
  id: string;
  text: string;
  /** 行类型（标题、正文、列表等） */
  type: "heading" | "paragraph" | "list" | "code" | "other";
  /** 标题级别（仅 heading 类型有效） */
  level?: number;
  /** 是否被高亮 */
  highlighted?: boolean;
  /** 加粗 */
  bold?: boolean;
  /** 斜体 */
  italic?: boolean;
  /** 下划线 */
  underline?: boolean;
  /** 删除线 */
  strikethrough?: boolean;
  /** 文本对齐方式 */
  align?: "left" | "center" | "right" | "justify";
  /** 脚注引用标记，如 "1" 代表蓝色圆点 */
  footnoteRef?: string;
  /** 文字颜色 */
  color?: string;
  /** 字号（相对大小，如 "sm", "base", "lg", "xl"） */
  fontSize?: string;
}

/** 表格行 */
export interface TableRow {
  id: string;
  cells: string[];
}

/** 内容块类型 */
export type BlockContentType = "text" | "table" | "image";

/** 文档内容块（一页/一张slide等） */
export interface ContentBlock {
  id: string;
  /** 对应的 SectionNode id */
  sectionId: string;
  /** 块标题 */
  title: string;
  /** 块内文本行（文本类型时有效） */
  lines?: ContentLine[];
  /** 内容类型 */
  contentType?: BlockContentType;
  /** 表格数据（table类型时有效） */
  tableData?: { headers: string[]; rows: TableRow[] };
  /** 图片URL/路径（image类型时有效） */
  imageUrl?: string;
  /** 图片标题（image类型时有效） */
  imageCaption?: string;
  /** 来源页码（真实文档才有）；AI 引用跳转按它定位到原文 */
  pageNumber?: number | null;
}

/** 脚注引用：原文引用来源 */
export interface FootnoteReference {
  id: string;
  /** 引用编号，如 "1" */
  refNumber: string;
  /** 引用的原文片段 */
  sourceText: string;
  /** 来源描述（如："第3页，第2段"） */
  sourceDesc: string;
}

/** 文档选中内容（用于引用询问AI） */
export interface TextSelection {
  /** 选中的文本内容 */
  text: string;
  /** 来源内容块 ID */
  blockId: string;
  /** 来源章节 ID */
  sectionId: string;
  /** 选中范围起始行 ID */
  fromLineId: string;
  /** 选中范围结束行 ID */
  toLineId: string;
}