import { useRef, useEffect, useState, type KeyboardEvent } from "react";
import type { ChatPanelProps } from "../../type";

/** AI logo */
function AIAvatar({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizeMap = { sm: "w-6 h-6", md: "w-8 h-8", lg: "w-10 h-10" };
  const iconSizeMap = { sm: 10, md: 14, lg: 18 };
  return (
    <div className={`${sizeMap[size]} rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20 flex-shrink-0`}>
      <svg width={iconSizeMap[size]} height={iconSizeMap[size]} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a7 7 0 0 0-7 7c0 2.4 1.2 4.5 3 5.7V17h8v-2.3c1.8-1.3 3-3.4 3-5.7a7 7 0 0 0-7-7z" />
        <line x1="9" y1="17" x2="15" y2="17" />
        <line x1="10" y1="20" x2="14" y2="20" />
      </svg>
    </div>
  );
}

/** Token 用量显示 */
function TokenUsage({ usage }: { usage: number }) {
  const max = 4096;
  const percentage = Math.min((usage / max) * 100, 100);
  return (
    <div className="flex items-center gap-1.5 text-[9px] text-neutral-400 flex-shrink-0 min-w-0">
      <div className="w-10 h-1.5 bg-black/10 rounded-full overflow-hidden flex-shrink-0">
        <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300" style={{ width: `${percentage}%` }} />
      </div>
      <span className="font-medium flex-shrink-0">{usage.toLocaleString()} / {max.toLocaleString()}</span>
    </div>
  );
}

/** 引用内容展示条 */
function QuoteBar({ text, onClear }: { text: string; onClear: () => void }) {
  return (
    <div className="mx-1 bg-blue-50 rounded-xl border border-blue-200 px-2.5 py-1.5">
      <div className="flex items-start gap-1.5">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-blue-500 mt-0.5 flex-shrink-0">
          <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z" />
          <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z" />
        </svg>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-blue-600 font-medium mb-0.5">引用内容</p>
          <p className="text-[11px] text-neutral-600 leading-relaxed line-clamp-2">{text}</p>
        </div>
        <button onClick={onClear} className="flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center hover:bg-blue-200 transition">
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-blue-500"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
      </div>
    </div>
  );
}

/** 右侧 AI 聊天面板组件 */
function ChatPanel({ messages, input, quotedText, tokenUsage, onInputChange, onSend, onClearQuote, loading, error }: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // 当前高亮的来源条目（messageId + 下标）；再点一次取消高亮
  const [activeSource, setActiveSource] = useState<{ messageId: string; index: number } | null>(null);

  useEffect(() => {
    try { messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" }); } catch { /* noop */ }
  }, [messages]);

  const handleSend = () => { if ((input.trim() || quotedText) && !loading) onSend(); };
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 面板标题 - 固定在顶部，高度与文件面板一致 */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-[10px] border-b border-black/5 bg-white/50 gap-1 h-[48px]" style={{ whiteSpace: "nowrap" }}>
        <h2 className="text-sm font-semibold text-neutral-700 tracking-tight flex-shrink-0">AI 助手</h2>
        <div className="flex items-center gap-1 flex-shrink-0">
          <TokenUsage usage={tokenUsage} />
          {loading && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
        </div>
      </div>

      {/* 消息列表 - 可滚动区域 */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 scrollbar-hide" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-100 to-purple-100 flex items-center justify-center mb-3">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" className="text-blue-500">
                <path d="M12 2a7 7 0 0 0-7 7c0 2.4 1.2 4.5 3 5.7V17h8v-2.3c1.8-1.3 3-3.4 3-5.7a7 7 0 0 0-7-7z" />
                <line x1="9" y1="17" x2="15" y2="17" /><line x1="10" y1="20" x2="14" y2="20" />
              </svg>
            </div>
            <p className="text-sm text-neutral-500 font-medium">有什么可以帮你？</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && <AIAvatar size="sm" />}
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-black text-white rounded-br-md"
                  : "bg-black/5 text-neutral-700 rounded-bl-md"
              }`}>
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {msg.sources.map((source, index) => {
                      const active = activeSource?.messageId === msg.id && activeSource.index === index;
                      return (
                        <button key={`${msg.id}-source-${index}`} type="button" aria-pressed={active}
                          onClick={() => setActiveSource(active ? null : { messageId: msg.id, index })}
                          title={source.headingPath?.join(" / ") ?? undefined}
                          className={`text-[10px] px-1.5 py-0.5 rounded-md border transition-colors cursor-pointer ${
                            active
                              ? "bg-blue-500 text-white border-blue-500"
                              : "bg-white/70 text-neutral-500 border-black/10 hover:bg-blue-50"
                          }`}>
                          来源 {index + 1} · {source.pageNumber != null ? `第 ${source.pageNumber} 页` : source.documentId}
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className={`flex items-center justify-between mt-1 ${msg.role === "user" ? "text-white/50" : "text-neutral-400"}`}>
                  <span className="text-[10px]">{new Date(msg.createdAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</span>
                  {msg.role === "assistant" && <span className="text-[9px] opacity-60">AI</span>}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 - 固定在底部 */}
      <div className="flex-shrink-0 border-t border-black/5 bg-white/50 px-3 py-2.5">
        {error && (
          <div role="alert" className="mb-2 px-2.5 py-1.5 rounded-xl bg-red-50 border border-red-200 text-[11px] text-red-600 leading-relaxed break-words">
            {error}
          </div>
        )}
        {quotedText && <div className="mb-2"><QuoteBar text={quotedText} onClear={onClearQuote} /></div>}
        <div className="flex items-center gap-2 bg-black/5 rounded-2xl px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500/30 transition-all duration-200">
          <textarea ref={inputRef} value={input} onChange={(e) => onInputChange(e.target.value)} onKeyDown={handleKeyDown}
            placeholder={quotedText ? "针对引用内容提问..." : "输入你的问题..."}
            rows={1} className="flex-1 bg-transparent text-sm text-neutral-700 placeholder-neutral-400 outline-none resize-none max-h-32" style={{ scrollbarWidth: "none" }} />
          <button onClick={handleSend} disabled={(!input.trim() && !quotedText) || loading}
            className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 ${
              (input.trim() || quotedText) && !loading
                ? "bg-black text-white hover:opacity-85 shadow-sm"
                : "bg-neutral-200 text-neutral-400 cursor-not-allowed"
            }`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-neutral-400 mt-1.5 px-1">Enter 发送，Shift+Enter 换行</p>
      </div>
    </div>
  );
}

export default ChatPanel;
