/**
 * 模型配置接口封装：`/api/providers`。
 *
 * 为什么要有它：问答链路从后端的 `ProviderRegistry` 取当前激活的 provider，
 * 在它之前**没有任何 HTTP 途径**能激活一个 —— 界面只能一直显示"尚未配置可用的模型"。
 *
 * 响应字段沿用后端的 snake_case（与 `src/lib/upload.ts` 的惯例一致），不再多一层命名转换。
 */
import { requestJson } from "../../../lib/apiClient";

/** 后端 `ProviderConfigResponse` —— **不含 `api_key`**。 */
export interface ProviderConfig {
  id: string;
  name: string;
  api_mode: string;
  api_host: string;
  api_path: string;
  model_id: string;
  display_name: string;
  context_window: number;
  max_output_tokens: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 激活结果（后端 `ProviderActivateResponse`）。 */
export interface ProviderActivateResult {
  id: string;
  name: string;
  display_name: string;
  model_id: string;
}

/** 界面只需要填这几项，其余用默认值补齐。 */
export interface ProviderDraft {
  name: string;
  api_host: string;
  api_key: string;
  model_id: string;
  display_name: string;
}

/** 与后端 `ProviderConfigCreateRequest` 的默认值保持一致。 */
export const DEFAULT_API_MODE = "openai-compat";
export const DEFAULT_API_PATH = "/v1/chat/completions";
export const DEFAULT_CONTEXT_WINDOW = 65536;
export const DEFAULT_MAX_OUTPUT_TOKENS = 8192;

/** 列出所有模型配置。 */
export function listProviders(): Promise<ProviderConfig[]> {
  return requestJson<ProviderConfig[]>("/api/providers");
}

/** 新增一份配置（默认**不激活**，避免悄悄换掉正在用的模型）。 */
export function createProvider(draft: ProviderDraft): Promise<ProviderConfig> {
  return requestJson<ProviderConfig>("/api/providers", {
    method: "POST",
    body: {
      api_mode: DEFAULT_API_MODE,
      api_path: DEFAULT_API_PATH,
      context_window: DEFAULT_CONTEXT_WINDOW,
      max_output_tokens: DEFAULT_MAX_OUTPUT_TOKENS,
      ...draft,
    },
  });
}

/** 把某份配置设为当前使用的模型。 */
export function activateProvider(configId: string): Promise<ProviderActivateResult> {
  return requestJson<ProviderActivateResult>(
    `/api/providers/${configId}/activate`,
    { method: "POST" },
  );
}
