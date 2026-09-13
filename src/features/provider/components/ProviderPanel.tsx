import { useCallback, useEffect, useState } from "react";
import {
  activateProvider,
  createProvider,
  listProviders,
  type ProviderConfig,
  type ProviderDraft,
} from "../api/providerApi";

const EMPTY_DRAFT: ProviderDraft = {
  name: "",
  api_host: "",
  api_key: "",
  model_id: "",
  display_name: "",
};

const fieldClass =
  "w-full bg-black/5 rounded-lg px-2.5 py-1.5 text-xs text-neutral-700 placeholder-neutral-400 outline-none focus:ring-2 focus:ring-blue-500/30";

/**
 * 模型配置面板：列出已有配置、新增配置、激活其中一个。
 *
 * 激活成功后问答链路才真正可用 —— 之前 `POST /api/chat` 只会回 503。
 */
function ProviderPanel({ onClose }: { onClose: () => void }) {
  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [draft, setDraft] = useState<ProviderDraft>(EMPTY_DRAFT);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setConfigs(await listProviders());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载模型配置失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createProvider(draft);
      setDraft(EMPTY_DRAFT);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const activate = async (configId: string) => {
    setBusy(true);
    setError(null);
    try {
      await activateProvider(configId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "激活失败");
    } finally {
      setBusy(false);
    }
  };

  const update = (key: keyof ProviderDraft) => (value: string) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" role="dialog" aria-label="模型配置">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-700">模型配置</h2>
          <button onClick={onClose} aria-label="关闭"
            className="cursor-pointer w-6 h-6 rounded-lg flex items-center justify-center text-neutral-400 hover:bg-black/5">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {error && (
          <div role="alert" className="px-2.5 py-1.5 rounded-xl bg-red-50 border border-red-200 text-[11px] text-red-600 break-words">
            {error}
          </div>
        )}

        <div className="space-y-2">
          {configs.length === 0 ? (
            <p className="text-xs text-neutral-400">还没有配置模型 —— 填一份 API Key 才能开始问答。</p>
          ) : (
            configs.map((config) => (
              <div key={config.id} className="flex items-center justify-between gap-2 border border-black/5 rounded-xl px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm text-neutral-700 truncate">{config.display_name}</p>
                  <p className="text-[10px] text-neutral-400 truncate">{config.model_id} · {config.api_host}</p>
                </div>
                {config.is_active ? (
                  <span className="flex-shrink-0 text-[10px] text-blue-600 font-medium">当前使用</span>
                ) : (
                  <button onClick={() => activate(config.id)} disabled={busy}
                    className="flex-shrink-0 text-[11px] px-2 py-1 rounded-lg bg-black text-white hover:opacity-85 disabled:opacity-50 cursor-pointer">
                    激活
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <input aria-label="配置名" placeholder="配置名（唯一）" value={draft.name}
            onChange={(e) => update("name")(e.target.value)} className={fieldClass} />
          <input aria-label="显示名称" placeholder="显示名称" value={draft.display_name}
            onChange={(e) => update("display_name")(e.target.value)} className={fieldClass} />
          <input aria-label="接口地址" placeholder="接口地址，如 https://api.deepseek.com" value={draft.api_host}
            onChange={(e) => update("api_host")(e.target.value)} className={`${fieldClass} col-span-2`} />
          <input aria-label="模型 ID" placeholder="模型 ID，如 deepseek-chat" value={draft.model_id}
            onChange={(e) => update("model_id")(e.target.value)} className={fieldClass} />
          <input aria-label="API Key" placeholder="API Key" type="password" value={draft.api_key}
            onChange={(e) => update("api_key")(e.target.value)} className={fieldClass} />
        </div>

        <div className="flex justify-end">
          <button onClick={submit} disabled={busy}
            className="text-xs px-3 py-1.5 rounded-xl bg-black text-white hover:opacity-85 disabled:opacity-50 cursor-pointer">
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

export default ProviderPanel;
