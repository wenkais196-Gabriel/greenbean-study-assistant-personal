/**
 * 与 Python 后端通信的通用 HTTP 封装：统一 base URL、JSON 编解码与错误映射。
 *
 * 之前只有 `upload.ts` 自带一份 base URL 与错误解析；问答链路接进来后不能再复制第三份，
 * 所以把这两件事提到这里，`upload.ts` / `chatApi.ts` / 将来的 provider 配置都复用它。
 */

export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/** 后端地址：部署时用 `VITE_API_BASE_URL` 覆盖。 */
export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

/**
 * 带 HTTP 状态码的请求错误。
 *
 * UI 需要按状态码分档：503 = 还没配模型（该去设置里配），0 = 后端没起来，
 * 400 = 输入有问题。只抛一句字符串的话，界面只能显示"请求失败"。
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** 取后端 `detail` 文案；拿不到就退回状态码描述。 */
export async function describeHttpError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail) {
      return body.detail;
    }
  } catch {
    // 响应不是 JSON（网关错误页等）：退回到状态码描述
  }
  return `请求失败（HTTP ${response.status}）`;
}

export interface JsonRequestOptions {
  method?: string;
  /** 会以 JSON 序列化；不传则不发请求体。 */
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * 发一次 JSON 请求并返回解析后的响应体。
 *
 * - 非 2xx → 抛 `ApiError`（message 优先用后端 `detail`，status 为 HTTP 状态码）；
 * - fetch 自身 reject（网络不通）→ 抛 `ApiError(status=0)`，文案对用户可读。
 */
export async function requestJson<T>(
  path: string,
  options: JsonRequestOptions = {},
): Promise<T> {
  const { method = "GET", body, signal } = options;

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch {
    // fetch 只在网络层失败时 reject；HTTP 4xx/5xx 会正常 resolve
    throw new ApiError("无法连接后端服务，请确认后端已启动", 0);
  }

  if (!response.ok) {
    throw new ApiError(await describeHttpError(response), response.status);
  }

  return (await response.json()) as T;
}
