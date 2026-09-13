import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiBaseUrl, describeHttpError, requestJson } from "./apiClient";

/** 造一个够用的 Response 替身：本文件只关心 ok / status / json()。 */
function jsonResponse(
  body: unknown,
  init: { ok?: boolean; status?: number; notJson?: boolean } = {},
) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => {
      if (init.notJson) throw new Error("响应不是 JSON");
      return body;
    },
  } as unknown as Response;
}

describe("apiClient", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("默认指向本地后端", () => {
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("以 JSON 方式发起请求并解析响应体", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "42" }));

    const data = await requestJson<{ answer: string }>("/api/chat", {
      method: "POST",
      body: { query: "什么是监督学习" },
    });

    expect(data.answer).toBe("42");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${apiBaseUrl()}/api/chat`);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ query: "什么是监督学习" });
  });

  it("GET 请求不带请求体", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await requestJson("/api/providers");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("后端返回 detail 时把它作为 ApiError 抛出（含状态码）", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "尚未配置可用的模型 provider" }, { ok: false, status: 503 }),
    );

    await expect(requestJson("/api/chat")).rejects.toBeInstanceOf(ApiError);
    await expect(requestJson("/api/chat")).rejects.toThrow("尚未配置可用的模型 provider");
  });

  it("响应不是 JSON 时退回到状态码描述", async () => {
    const response = jsonResponse(null, { ok: false, status: 500, notJson: true });
    await expect(describeHttpError(response)).resolves.toBe("请求失败（HTTP 500）");
  });

  it("连不上后端时给出可读提示而不是原始网络异常", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await requestJson("/api/chat").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
    expect((error as ApiError).message).toContain("无法连接后端服务");
  });
});

describe("apiClient · 错误文案回落", () => {
  it("detail 不是字符串时退回到状态码描述", async () => {
    // FastAPI 的校验错误会是数组，别的网关可能给对象：都不能直接当文案用
    const response = {
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ msg: "invalid" }] }),
    } as unknown as Response;

    await expect(describeHttpError(response)).resolves.toBe("请求失败（HTTP 422）");
  });
});
