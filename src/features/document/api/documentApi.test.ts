import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import { fetchDocumentUnits, listDocuments } from "./documentApi";

/** 后端返回的原始形状（snake_case）—— 这是「输入」。 */
const wireDocument = {
  document_id: "doc-1",
  title: "cours-analyse-s1",
  original_filename: "cours-analyse-s1.pdf",
  file_type: "pdf",
  status: "parsed",
  page_count: 12,
  created_at: "2026-09-12T10:00:00+00:00",
};

const wireUnit = {
  unit_id: "unit-1",
  sequence_index: 0,
  page_number: 1,
  text_content: "Chapitre 1 : introduction",
};

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

describe("documentApi", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("以 GET /api/documents 取列表，并把 snake_case 转成 camelCase", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: 200, message: "ok", data: [wireDocument] }),
    );

    const documents = await listDocuments();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/documents"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(documents).toEqual([
      {
        documentId: "doc-1",
        title: "cours-analyse-s1",
        originalFilename: "cours-analyse-s1.pdf",
        fileType: "pdf",
        status: "parsed",
        pageCount: 12,
        createdAt: "2026-09-12T10:00:00+00:00",
      },
    ]);
  });

  it("一份文档都没有时返回空数组", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: 200, message: "ok", data: [] }));

    await expect(listDocuments()).resolves.toEqual([]);
  });

  it("以 GET /api/documents/{id}/units 取单元内容", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: 200, message: "ok", data: [wireUnit] }),
    );

    const units = await fetchDocumentUnits("doc-1");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/documents/doc-1/units"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(units).toEqual([
      {
        unitId: "unit-1",
        sequenceIndex: 0,
        pageNumber: 1,
        textContent: "Chapitre 1 : introduction",
      },
    ]);
  });

  it("文档不存在时抛出带状态码的 ApiError（调用方据此区分 404）", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "文档不存在: nope" }, { ok: false, status: 404 }),
    );

    await expect(fetchDocumentUnits("nope")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "文档不存在: nope",
    });
  });

  it("后端连不上时抛 ApiError(status=0) 且文案可读", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await listDocuments().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
    expect((error as ApiError).message).toContain("无法连接后端服务");
  });
});
