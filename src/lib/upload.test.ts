import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  apiBaseUrl,
  describeProgress,
  fetchIngestJob,
  isTerminal,
  pollIngestJob,
  uploadDocument,
  type IngestJob,
} from "./upload";

function makeJob(overrides: Partial<IngestJob> = {}): IngestJob {
  return {
    job_id: "job-1",
    filename: "cours.pdf",
    status: "running",
    stage: "parsing",
    progress: 0.1,
    error: null,
    result: null,
    ...overrides,
  };
}

/** 造一个够用的 Response 替身：本文件只关心 ok / status / json()。 */
function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

describe("upload 协议封装", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /* ===== 提交与查询 ===== */

  it("默认指向本地后端", () => {
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("uploadDocument 以 multipart 提交文件并返回受理结果", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: 202, data: makeJob() }));

    const file = new File(["x"], "cours.pdf", { type: "application/pdf" });
    const accepted = await uploadDocument(file);

    expect(accepted.job_id).toBe("job-1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${apiBaseUrl()}/api/documents/upload`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("fetchIngestJob 查询任务状态", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: 200, data: makeJob({ progress: 0.575 }) }));

    const job = await fetchIngestJob("job-9");

    expect(job.progress).toBe(0.575);
    expect(fetchMock.mock.calls[0][0]).toBe(`${apiBaseUrl()}/api/documents/jobs/job-9`);
  });

  /* ===== 失败路径 ===== */

  it("后端返回 detail 时把它作为错误信息抛出", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "暂不支持 .ppt 格式" }, { ok: false, status: 400 }),
    );

    await expect(uploadDocument(new File(["x"], "a.ppt"))).rejects.toThrow("暂不支持 .ppt 格式");
  });

  it("响应不是 JSON 时退回状态码描述", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);

    await expect(fetchIngestJob("job-1")).rejects.toThrow("HTTP 502");
  });

  /* ===== 状态到文案 ===== */

  it("终态判断只认 succeeded / failed", () => {
    expect(isTerminal("succeeded")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("running")).toBe(false);
    expect(isTerminal("queued")).toBe(false);
  });

  it("按 status / stage 给出可读文案", () => {
    expect(describeProgress({ status: "queued", stage: null, error: null })).toBe(
      "已受理，等待开始",
    );
    expect(describeProgress({ status: "running", stage: "embedding", error: null })).toBe(
      "正在向量化片段",
    );
    expect(describeProgress({ status: "succeeded", stage: null, error: null })).toBe("解析完成");
    expect(describeProgress({ status: "failed", stage: null, error: "解析器炸了" })).toBe(
      "解析失败：解析器炸了",
    );
    expect(describeProgress({ status: "failed", stage: null, error: null })).toBe("解析失败");
  });

  /* ===== 轮询 ===== */

  it("轮询到终态后停止，并回调每一次状态", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ data: makeJob({ status: "running", progress: 0.3 }) }))
      .mockResolvedValueOnce(
        jsonResponse({ data: makeJob({ status: "succeeded", progress: 1, stage: "persisting" }) }),
      );

    const seen: string[] = [];
    const finished = await pollIngestJob("job-1", {
      intervalMs: 0,
      onUpdate: (job) => seen.push(job.status),
    });

    expect(finished.status).toBe("succeeded");
    expect(seen).toEqual(["running", "succeeded"]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("超过等待上限时抛错，不无限轮询", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: makeJob({ status: "running" }) }));

    await expect(pollIngestJob("job-1", { intervalMs: 0, timeoutMs: 0 })).rejects.toThrow(
      "超时",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
