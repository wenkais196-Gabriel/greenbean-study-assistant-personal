/**
 * 会话 ID 的本地保存。
 *
 * 为什么需要它：后端 `GET /api/chat/sessions/{id}/messages` 能回读历史，但前提是
 * **刷新之后还是同一个会话 ID** —— 否则每次打开都算新会话，历史永远看不到。
 *
 * 存储不可用时（某些隐私模式直接抛异常）降级为**内存会话**：宁可历史丢，也不能让界面崩。
 */

export const SESSION_STORAGE_KEY = "greenbean.chat.session_id";

/** 存储不可用时的兜底：本次进程内继续用同一个会话 */
let memorySessionId: string | null = null;

function newSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/** 读取已保存的会话 ID；没存过（或存的是空串）时返回 `null`。 */
export function loadSessionId(): string | null {
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    // 以持久化存储为准：存储里没有就是"没有会话"，
    // 内存兜底值只服务于"存储不可用"这一种情况（否则清空存储后还会拿到上一个会话）
    memorySessionId = stored || null;
    return memorySessionId;
  } catch {
    // 存储不可用：退回内存值
    return memorySessionId;
  }
}

/** 保存会话 ID；空串等价于"没有会话"（清掉存储）。 */
export function saveSessionId(sessionId: string): void {
  memorySessionId = sessionId || null;

  try {
    if (sessionId) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    // 存储不可用：仅内存会话
  }
}

/** 复用已保存的会话 ID；没有就生成一个并保存。 */
export function getOrCreateSessionId(): string {
  const existing = loadSessionId();
  if (existing) {
    return existing;
  }

  const created = newSessionId();
  saveSessionId(created);
  return created;
}
