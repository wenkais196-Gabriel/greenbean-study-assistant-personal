import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import { activateProvider, createProvider, listProviders, type ProviderConfig } from "./providerApi";

/** 后端 `ProviderConfigResponse` 的原始形状（snake_case，与 upload.ts 的惯例一致）。 */
const config: ProviderConfig = {
  id: "p-1",
  name: "deepseek",
  api_mode: "openai-compat",
  api_host: "https://api.deepseek.com",
  api_path: "/v1/chat/completions",
  model_id: "deepseek-chat",
  display_name: "DeepSeek 对话",
  context_window: 65536,
  max_output_tokens: 8192,
  is_active: false,
  created_at: "2026-09-12T10:00:00Z",
  updated_at: "2026-09-12T10:00:00Z",
};

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

describe("providerApi", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("列出模型配置", async () => {
    fetchMock.mockResolvedValue(jsonResponse([config]));

    const result = await listProviders();

    expect(result).toEqual([config]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/providers");
    expect(init.method).toBe("GET");
  });

  it("新增配置：自动补上 api_mode 与 api_path 默认值", async () => {
    fetchMock.mockResolvedValue(jsonResponse(config, { status: 201 }));

    const created = await createProvider({
      name: "deepseek",
      api_host: "https://api.deepseek.com",
      api_key: "sk-x",
      model_id: "deepseek-chat",
      display_name: "DeepSeek 对话",
    });

    expect(created.id).toBe("p-1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/providers");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({
      name: "deepseek",
      api_key: "sk-x",
      api_mode: "openai-compat",
      api_path: "/v1/chat/completions",
      model_id: "deepseek-chat",
    });
  });

  it("激活某个配置", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ id: "p-1", name: "deepseek", display_name: "DeepSeek 对话", model_id: "deepseek-chat" }),
    );

    const active = await activateProvider("p-1");

    expect(active.id).toBe("p-1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/providers/p-1/activate");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("配置名重复时把后端 409 文案抛给界面", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "配置名已存在: deepseek" }, { ok: false, status: 409 }),
    );

    const error = await createProvider({
      name: "deepseek",
      api_host: "https://api.deepseek.com",
      api_key: "sk-x",
      model_id: "deepseek-chat",
      display_name: "DeepSeek 对话",
    }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toContain("配置名已存在");
  });
});
