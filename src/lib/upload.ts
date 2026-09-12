/**
 * 后端「异步上传 + 进度轮询」的协议封装。
 *
 * 协议见 docs/specs/us-stage1-upload-async.md：
 * `POST /api/documents/upload` 只做校验与受理（202 + job_id），**不等**摄取完成；
 * 摄取进度通过 `GET /api/documents/jobs/{job_id}` 轮询（parsing → embedding → persisting）。
 *
 * 为什么要有这一层：大文档摄取要 1~2 分钟，UI 必须能持续展示"走到哪一步"，
 * 而不是让用户对着一个卡住的转圈猜系统死没死。
 */

export type IngestJobStatus = "queued" | "running" | "succeeded" | "failed";
export type IngestStage = "parsing" | "embedding" | "persisting";

export interface IngestResult {
  filename: string;
  total_pages: number;
  chunks_created: number;
  document_id: string;
  elapsed_seconds: number;
}

export interface IngestJob {
  job_id: string;
  filename: string;
  status: IngestJobStatus;
  stage: IngestStage | null;
  progress: number;
  error: string | null;
  result: IngestResult | null;
}

/** 阶段文案：UI 唯一需要知道的"进度含义"（后端只报阶段名）。 */
export const STAGE_LABELS: Record<IngestStage, string> = {
  parsing: "正在解析文档",
  embedding: "正在向量化片段",
  persisting: "正在写入索引",
};

/** 轮询间隔：摄取以秒计，500 ms 够跟手，也不会把后端刷爆。 */
export const POLL_INTERVAL_MS = 500;

/** 等待上限：超时明确报错，不无限轮询下去。 */
export const POLL_TIMEOUT_MS = 10 * 60 * 1000;

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/** 后端地址：部署时用 `VITE_API_BASE_URL` 覆盖。 */
export function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

const TERMINAL_STATUSES: readonly IngestJobStatus[] = ["succeeded", "failed"];

/** 是否已经是终态（终态之后不该再轮询）。 */
export function isTerminal(status: IngestJobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

/** 一行状态文案：把 status / stage / error 翻成用户看得懂的话。 */
export function describeProgress(
  job: Pick<IngestJob, "status" | "stage" | "error">,
): string {
  if (job.status === "failed") {
    return job.error ? `解析失败：${job.error}` : "解析失败";
  }
  if (job.status === "succeeded") {
    return "解析完成";
  }
  return job.stage ? STAGE_LABELS[job.stage] : "已受理，等待开始";
}

async function describeHttpError(response: Response): Promise<string> {
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

async function readJob(response: Response): Promise<IngestJob> {
  if (!response.ok) {
    throw new Error(await describeHttpError(response));
  }
  const envelope = (await response.json()) as { data: IngestJob };
  return envelope.data;
}

/** 提交文件：只等"受理"，不等摄取完成。 */
export async function uploadDocument(
  file: File,
  signal?: AbortSignal,
): Promise<IngestJob> {
  const form = new FormData();
  form.append("file", file);
  return readJob(
    await fetch(`${apiBaseUrl()}/api/documents/upload`, {
      method: "POST",
      body: form,
      signal,
    }),
  );
}

/** 查询任务当前状态（单次）。 */
export async function fetchIngestJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<IngestJob> {
  return readJob(await fetch(`${apiBaseUrl()}/api/documents/jobs/${jobId}`, { signal }));
}

export interface PollOptions {
  /** 每次拿到新状态时回调（含首次与终态） */
  onUpdate?: (job: IngestJob) => void;
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** 轮询直到终态；超时抛错而不是无限等下去。 */
export async function pollIngestJob(
  jobId: string,
  options: PollOptions = {},
): Promise<IngestJob> {
  const {
    onUpdate,
    intervalMs = POLL_INTERVAL_MS,
    timeoutMs = POLL_TIMEOUT_MS,
    signal,
  } = options;
  const deadline = Date.now() + timeoutMs;

  for (;;) {
    const job = await fetchIngestJob(jobId, signal);
    onUpdate?.(job);
    if (isTerminal(job.status)) {
      return job;
    }
    if (Date.now() >= deadline) {
      throw new Error("等待解析结果超时，请稍后重试");
    }
    await sleep(intervalMs);
  }
}
