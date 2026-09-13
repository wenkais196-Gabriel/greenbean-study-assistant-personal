/**
 * 文档查询接口封装：`GET /api/documents`（列表）与
 * `GET /api/documents/{document_id}/units`（逐页原文）。
 *
 * 两个端点都用 `{code, message, data}` 包裹（与被同一控制器服务、以及 `upload.ts` 一致），
 * 这里把 `data` 解出来、把 snake_case 转成 camelCase —— 组件里只见一套命名。
 * base URL 与错误映射在 `src/lib/apiClient.ts`，这一层不重复实现。
 */
import { requestJson } from "../../../lib/apiClient";

/** 后端文档列表里一条的原始形状（Python 侧 snake_case）。 */
interface WireDocument {
  document_id: string;
  title: string;
  original_filename: string;
  file_type: string;
  status: string;
  page_count: number | null;
  created_at: string;
}

/** 后端内容单元的原始形状。 */
interface WireDocumentUnit {
  unit_id: string;
  sequence_index: number;
  page_number: number | null;
  text_content: string;
}

/** `{code, message, data}` 包裹体。 */
interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

/** 左侧文件列表要的文档摘要。 */
export interface DocumentSummary {
  documentId: string;
  title: string;
  originalFilename: string;
  fileType: string;
  status: string;
  /** 页数；后端拿不到时为 null */
  pageCount: number | null;
  createdAt: string;
}

/** 一份文档里的一页（或一张 slide）的原文。 */
export interface DocumentUnit {
  /** 内容单元 ID，也是界面定位用的锚点 */
  unitId: string;
  sequenceIndex: number;
  /** 来源页码；拿不到时为 null（此时无法按页码跳转） */
  pageNumber: number | null;
  textContent: string;
}

function toDocumentSummary(wire: WireDocument): DocumentSummary {
  return {
    documentId: wire.document_id,
    title: wire.title,
    originalFilename: wire.original_filename,
    fileType: wire.file_type,
    status: wire.status,
    pageCount: wire.page_count,
    createdAt: wire.created_at,
  };
}

function toDocumentUnit(wire: WireDocumentUnit): DocumentUnit {
  return {
    unitId: wire.unit_id,
    sequenceIndex: wire.sequence_index,
    pageNumber: wire.page_number,
    textContent: wire.text_content,
  };
}

/**
 * 列出已上传的文档（后端按上传时间倒序）。
 *
 * 一份都没有时后端返回空数组而不是 404 —— "还没上传资料"是正常状态。
 */
export async function listDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  const envelope = await requestJson<Envelope<WireDocument[]>>("/api/documents", { signal });
  return envelope.data.map(toDocumentSummary);
}

/** 读取一份文档的全部内容单元（按文档内顺序）。文档不存在时抛 `ApiError(404)`。 */
export async function fetchDocumentUnits(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentUnit[]> {
  const envelope = await requestJson<Envelope<WireDocumentUnit[]>>(
    `/api/documents/${documentId}/units`,
    { signal },
  );
  return envelope.data.map(toDocumentUnit);
}
