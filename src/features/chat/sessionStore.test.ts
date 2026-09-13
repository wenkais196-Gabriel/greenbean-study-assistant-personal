import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SESSION_STORAGE_KEY, getOrCreateSessionId, loadSessionId, saveSessionId } from "./sessionStore";

describe("sessionStore", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("没有保存过时读取返回 null", () => {
    expect(loadSessionId()).toBeNull();
  });

  it("写入后能读回同一个会话 ID", () => {
    saveSessionId("s-1");

    expect(loadSessionId()).toBe("s-1");
  });

  it("首次调用生成新 ID 并保存（刷新后能复用）", () => {
    const first = getOrCreateSessionId();

    expect(first).toBeTruthy();
    expect(loadSessionId()).toBe(first);
  });

  it("已有 ID 时复用而不是新生成", () => {
    saveSessionId("s-existing");

    expect(getOrCreateSessionId()).toBe("s-existing");
    expect(loadSessionId()).toBe("s-existing");
  });

  it("保存空字符串等价于没有会话（不把空值当有效会话）", () => {
    saveSessionId("s-1");
    saveSessionId("");

    expect(loadSessionId()).toBeNull();
  });

  it("localStorage 不可用时降级为内存会话，不抛错", () => {
    // 某些隐私模式会直接抛异常：会话需要能在内存里继续，而不是让界面崩掉
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    void getItem;
    void setItem;

    expect(() => saveSessionId("s-1")).not.toThrow();
    expect(getOrCreateSessionId()).toBeTruthy();
  });

  it("会话 ID 使用可读前缀，便于在存储里辨认", () => {
    expect(getOrCreateSessionId().startsWith("session-")).toBe(true);
    expect(SESSION_STORAGE_KEY).toBe("greenbean.chat.session_id");
  });
});
