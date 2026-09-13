import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProviderPanel from "./ProviderPanel";

const existingConfig = {
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

/** 按 URL + 方法分派响应；默认：列表返回一条配置。 */
function mockApi(overrides: {
  list?: Response[];
  create?: Response;
  activate?: Response;
} = {}) {
  const listResponses = overrides.list ?? [jsonResponse([existingConfig])];
  let listCall = 0;

  return vi.fn(async (url: string, init?: { method?: string }) => {
    if (url.endsWith("/api/providers") && init?.method === "POST") {
      return overrides.create ?? jsonResponse({ ...existingConfig, id: "p-2" }, { status: 201 });
    }
    if (url.includes("/activate")) {
      return overrides.activate ?? jsonResponse({ id: "p-1", name: "deepseek", display_name: "DeepSeek 对话", model_id: "deepseek-chat" });
    }
    const response = listResponses[Math.min(listCall, listResponses.length - 1)];
    listCall += 1;
    return response;
  });
}

describe("ProviderPanel", () => {
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("打开时列出已有配置与模型名", async () => {
    vi.stubGlobal("fetch", mockApi());

    render(<ProviderPanel onClose={onClose} />);

    expect(await screen.findByText("DeepSeek 对话")).toBeDefined();
    expect(screen.getByText(/deepseek-chat/)).toBeDefined();
  });

  it("没有配置时给出提示", async () => {
    vi.stubGlobal("fetch", mockApi({ list: [jsonResponse([])] }));

    render(<ProviderPanel onClose={onClose} />);

    expect(await screen.findByText(/还没有配置模型/)).toBeDefined();
  });

  it("激活一条配置后标记为当前使用", async () => {
    vi.stubGlobal(
      "fetch",
      mockApi({
        list: [
          jsonResponse([existingConfig]),
          jsonResponse([{ ...existingConfig, is_active: true }]),
        ],
      }),
    );

    render(<ProviderPanel onClose={onClose} />);
    fireEvent.click(await screen.findByRole("button", { name: "激活" }));

    expect(await screen.findByText("当前使用")).toBeDefined();
  });

  it("提交表单新增配置并带上填写的字段", async () => {
    const fetchMock = mockApi();
    vi.stubGlobal("fetch", fetchMock);

    render(<ProviderPanel onClose={onClose} />);
    await screen.findByText("DeepSeek 对话");

    fireEvent.change(screen.getByLabelText("配置名"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("接口地址"), { target: { value: "https://api.openai.com" } });
    fireEvent.change(screen.getByLabelText("API Key"), { target: { value: "sk-live" } });
    fireEvent.change(screen.getByLabelText("模型 ID"), { target: { value: "gpt-4o-mini" } });
    fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "OpenAI" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/api/providers") && (init as { method?: string })?.method === "POST",
      );
      expect(createCall).toBeDefined();
      expect(JSON.parse((createCall![1] as { body: string }).body)).toMatchObject({
        name: "openai",
        api_host: "https://api.openai.com",
        api_key: "sk-live",
        model_id: "gpt-4o-mini",
        display_name: "OpenAI",
      });
    });
  });

  it("后端报错时把错误文案显示出来", async () => {
    vi.stubGlobal(
      "fetch",
      mockApi({ create: jsonResponse({ detail: "配置名已存在: openai" }, { ok: false, status: 409 }) }),
    );

    render(<ProviderPanel onClose={onClose} />);
    await screen.findByText("DeepSeek 对话");

    fireEvent.change(screen.getByLabelText("配置名"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("接口地址"), { target: { value: "https://api.openai.com" } });
    fireEvent.change(screen.getByLabelText("API Key"), { target: { value: "sk-live" } });
    fireEvent.change(screen.getByLabelText("模型 ID"), { target: { value: "gpt-4o-mini" } });
    fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "OpenAI" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByText(/配置名已存在/)).toBeDefined();
  });

  it("点击关闭触发回调", async () => {
    vi.stubGlobal("fetch", mockApi());

    render(<ProviderPanel onClose={onClose} />);
    await screen.findByText("DeepSeek 对话");

    fireEvent.click(screen.getByRole("button", { name: "关闭" }));

    expect(onClose).toHaveBeenCalled();
  });
});

describe("ProviderPanel · 激活失败", () => {
  it("激活失败时把后端错误显示出来", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      String(url).includes("/activate")
        ? jsonResponse({ detail: "模型配置不存在: p-1" }, { ok: false, status: 404 })
        : jsonResponse([existingConfig]),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ProviderPanel onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "激活" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByText(/模型配置不存在/)).toBeDefined();
  });
});

describe("ProviderPanel · 失败路径", () => {
  it("加载配置失败时显示错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "服务器内部错误" }, { ok: false, status: 500 })),
    );

    render(<ProviderPanel onClose={vi.fn()} />);

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByText(/服务器内部错误/)).toBeDefined();
  });

  it("网络层异常被规范化成可读错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw "boom";
      }),
    );

    render(<ProviderPanel onClose={vi.fn()} />);

    // `apiClient` 会把 fetch 的任何 reject 统一包成 `ApiError`，
    // 所以组件里 `error instanceof Error` 恒为真（另一侧是防御分支）；
    // 这里锁住"非 Error 的抛出也不会把界面搞崩、且文案可读"这个约定。
    expect(await screen.findByText(/无法连接后端服务/)).toBeDefined();
  });
});
