/**
 * 文件管理面板 — 文件夹树结构，支持上传、右键重命名/删除/移动
 *
 * 上传是**异步**的（见 docs/specs/us-stage1-upload-async.md）：
 * 提交后先拿受理回执（job_id），再轮询摄取进度；大文档要 1~2 分钟，
 * 所以面板上要能看到阶段与百分比，而不是一个卡住的界面。
 */

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  describeProgress,
  pollIngestJob,
  uploadDocument,
  type IngestJob,
  type IngestStage,
  type IngestJobStatus,
} from "../../../../lib/upload";

/* ------------------------------------------------------------------ */
/*  类型定义                                                           */
/* ------------------------------------------------------------------ */

export type FileType = "PDF" | "DOC" | "PPT" | "IMG" | "TXT" | "MD";
export type FileStatus = "parsed" | "parsing" | "pending";

export interface FileItem {
  id: string;
  name: string;
  type: FileType;
  category: string;
  size: string;
  date: string;
  status: FileStatus;
}

export interface Folder {
  key: string;
  label: string;
}

/** 当前这次上传的可视化状态 */
export interface UploadProgress {
  fileName: string;
  status: IngestJobStatus;
  stage: IngestStage | null;
  progress: number;
  error: string | null;
}

/** 轮询回调只带这几个字段：文件名由发起上传的那次调用补上 */
type UploadUpdate = Pick<IngestJob, "status" | "stage" | "progress" | "error">;

export interface FileManagerProps {
  files?: FileItem[];
  folders?: Folder[];
  selectedFileId?: string | null;
  onFileSelect?: (fileId: string) => void;
  /** 选中文件后的回调，返回文件名 */
  onFileSelectWithName?: (fileId: string, fileName: string) => void;
}

/* ------------------------------------------------------------------ */
/*  类型颜色映射                                                       */
/* ------------------------------------------------------------------ */

const TYPE_STYLES: Record<FileType, { bg: string; text: string; label: string }> = {
  PDF: { bg: "#fee2e2", text: "#dc2626", label: "PDF" },
  DOC: { bg: "#dbeafe", text: "#2563eb", label: "DOC" },
  PPT: { bg: "#fef3c7", text: "#d97706", label: "PPT" },
  IMG: { bg: "#fce7f3", text: "#db2777", label: "IMG" },
  TXT: { bg: "#f0fdf4", text: "#16a34a", label: "TXT" },
  MD:  { bg: "#f5f3ff", text: "#7c3aed", label: "MD" },
};

/* ------------------------------------------------------------------ */
/*  默认数据                                                           */
/* ------------------------------------------------------------------ */

const DEFAULT_FOLDERS: Folder[] = [
  { key: "course", label: "课程资料" },
  { key: "exam", label: "考试复习" },
  { key: "thesis", label: "论文参考" },
];

function getDefaultFiles(lang: string): FileItem[] {
  const zh = lang === "zh";
  return [
    { id: "f1", name: "cours-analyse-s1.pdf", type: "PDF", category: "course", size: "12.4 MB", date: "2025-09-15", status: "parsed" },
    { id: "f2", name: "TD-économie-chap2.docx", type: "DOC", category: "course", size: "3.2 MB", date: "2025-10-02", status: "parsed" },
    { id: "f3", name: "cours-droit-commercial.pptx", type: "PPT", category: "course", size: "45.8 MB", date: "2025-10-10", status: "parsing" },
    { id: "f4", name: "cours-maths-tableau.webp", type: "IMG", category: "course", size: "2.1 MB", date: "2025-10-15", status: "pending" },
    { id: "f5", name: zh ? "复习笔记-期中exam.pdf" : "révision-exam.pdf", type: "PDF", category: "exam", size: "8.5 MB", date: "2025-11-01", status: "parsed" },
    { id: "f6", name: zh ? "论文-引言部分.docx" : "mémoire-intro.docx", type: "DOC", category: "thesis", size: "1.8 MB", date: "2025-11-10", status: "parsed" },
    { id: "f7", name: zh ? "参考文献列表.pdf" : "bibliographie.pdf", type: "PDF", category: "thesis", size: "5.3 MB", date: "2025-11-15", status: "pending" },
    { id: "f8", name: "TD-statistiques.pptx", type: "PPT", category: "course", size: "28.6 MB", date: "2025-11-20", status: "parsing" },
  ];
}

function uid(): string {
  const array = new Uint32Array(1);
  crypto.getRandomValues(array);
  return `f_${array[0].toString(36).slice(0, 7)}`;
}

/* ------------------------------------------------------------------ */
/*  文件管理器组件                                                     */
/* ------------------------------------------------------------------ */

export default function FileManager({
  files: externalFiles,
  folders: externalFolders,
  selectedFileId,
  onFileSelect,
  onFileSelectWithName,
}: FileManagerProps) {
  const [lang, _setLang] = useState("zh");

  const [searchQuery, setSearchQuery] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(["course"]));
  const [internalFiles, setInternalFiles] = useState<FileItem[]>(() => externalFiles ?? getDefaultFiles(lang));
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  // 右键菜单状态
  const [contextMenu, setContextMenu] = useState<{ fileId: string; x: number; y: number } | null>(null);
  // 重命名状态
  const [renaming, setRenaming] = useState<{ fileId: string; name: string } | null>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const folders = externalFolders ?? DEFAULT_FOLDERS;
  const allFiles = internalFiles;

  // `externalFiles` 是"外部数据源"（后端的真实文档）：变化时同步进来。
  // 之后的本地编辑（重命名 / 删除 / 移动）只作用于这份副本 —— 后端暂无这些接口，
  // 编辑结果留在本次会话里；不传 `files` 时保持内置演示数据。
  useEffect(() => {
    if (externalFiles) setInternalFiles(externalFiles);
  }, [externalFiles]);

  /** 切换文件夹展开/折叠 */
  const toggleFolder = useCallback((key: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  /** 搜索过滤后的文件 */
  const searchFiltered = useMemo(() => {
    if (!searchQuery.trim()) return null;
    return allFiles.filter((f) =>
      f.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [allFiles, searchQuery]);

  /** 某个文件夹的文件列表 */
  const getFolderFiles = useCallback((key: string): FileItem[] => {
    return allFiles
      .filter((f) => f.category === key)
      .sort((a, b) => {
        if (a.status === "parsed" && b.status !== "parsed") return -1;
        if (a.status !== "parsed" && b.status === "parsed") return 1;
        return a.name.localeCompare(b.name);
      });
  }, [allFiles]);

  const searchResults = searchFiltered;
  const isSearching = searchQuery.trim().length > 0;

  /** 获取文件所属文件夹 */
  const getFileCategory = useCallback((fileId: string) => {
    const file = allFiles.find((f) => f.id === fileId);
    return file?.category;
  }, [allFiles]);

  /** 更新某个文件的状态（上传成功后置为已解析） */
  const setFileStatus = useCallback((fileId: string, status: FileStatus) => {
    setInternalFiles((prev) =>
      prev.map((f) => (f.id === fileId ? { ...f, status } : f))
    );
  }, []);

  /**
   * 上传文件：提交后先拿受理回执，再轮询进度直到终态。
   *
   * 失败时**不清空**条目：让它留在列表里并明确报错，
   * 用户才知道是哪一份没进去（静默清空是最糟的失败表现）。
   */
  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    (e.target as HTMLInputElement).value = "";
    if (!file) return;

    const newFile: FileItem = {
      id: uid(),
      name: file.name,
      type: (file.name.split('.').pop()?.toUpperCase() as FileType) || "PDF",
      category: "",
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      date: new Date().toISOString().split('T')[0],
      status: "parsing",
    };
    setInternalFiles((prev) => [newFile, ...prev]);
    setUploadProgress({
      fileName: file.name,
      status: "queued",
      stage: null,
      progress: 0,
      error: null,
    });

    const applyUpdate = (update: UploadUpdate) =>
      setUploadProgress({ fileName: file.name, ...update });

    try {
      const accepted = await uploadDocument(file);
      applyUpdate(accepted);
      const finished = await pollIngestJob(accepted.job_id, { onUpdate: applyUpdate });
      setFileStatus(newFile.id, finished.status === "succeeded" ? "parsed" : "pending");
    } catch (error) {
      setUploadProgress({
        fileName: file.name,
        status: "failed",
        stage: null,
        progress: 0,
        error: error instanceof Error ? error.message : String(error),
      });
      setFileStatus(newFile.id, "pending");
    }
  }, [setFileStatus]);

  /** 右键打开菜单 */
  const handleContextMenu = useCallback((e: React.MouseEvent, fileId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ fileId, x: e.clientX, y: e.clientY });
  }, []);

  /** 关闭右键菜单 */
  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  /** 删除文件 */
  const handleDelete = useCallback((fileId: string) => {
    setInternalFiles((prev) => prev.filter((f) => f.id !== fileId));
    closeContextMenu();
  }, [closeContextMenu]);

  /** 开始重命名 */
  const handleStartRename = useCallback((fileId: string) => {
    const file = allFiles.find((f) => f.id === fileId);
    if (file) {
      setRenaming({ fileId, name: file.name });
      closeContextMenu();
      setTimeout(() => renameInputRef.current?.focus(), 50);
    }
  }, [allFiles, closeContextMenu]);

  /** 提交重命名 */
  const handleRenameSubmit = useCallback(() => {
    if (renaming && renaming.name.trim()) {
      setInternalFiles((prev) => prev.map((f) =>
        f.id === renaming.fileId ? { ...f, name: renaming.name.trim() } : f
      ));
    }
    setRenaming(null);
  }, [renaming]);

  /** 移动文件到指定文件夹 */
  const handleMove = useCallback((fileId: string, toCategory: string) => {
    setInternalFiles((prev) => prev.map((f) =>
      f.id === fileId ? { ...f, category: toCategory } : f
    ));
    closeContextMenu();
  }, [closeContextMenu]);

  /** 点击文件 */
  const handleFileClick = useCallback((fileId: string, fileName: string) => {
    onFileSelect?.(fileId);
    onFileSelectWithName?.(fileId, fileName);
  }, [onFileSelect, onFileSelectWithName]);

  /** 渲染单个文件按钮（共用） */
  const renderFileButton = (file: FileItem, compact = false) => {
    const isSelected = selectedFileId === file.id;
    const style = TYPE_STYLES[file.type];
    const isRenaming = renaming?.fileId === file.id;

    return (
      <div key={file.id} className="relative group/file">
        {isRenaming ? (
          <div className="flex items-center gap-1 px-2 py-1">
            <input
              ref={renameInputRef}
              value={renaming.name}
              onChange={(e) => setRenaming((prev) => prev ? { ...prev, name: e.target.value } : null)}
              onKeyDown={(e) => { if (e.key === "Enter") handleRenameSubmit(); if (e.key === "Escape") setRenaming(null); }}
              onBlur={handleRenameSubmit}
              className="flex-1 h-6 px-1.5 rounded bg-black/5 text-[11px] text-neutral-700 outline-none border border-blue-400"
            />
          </div>
        ) : (
          <button
            onClick={() => handleFileClick(file.id, file.name)}
            onContextMenu={(e) => handleContextMenu(e, file.id)}
            className={`cursor-pointer w-full flex items-center gap-2 text-left transition-all duration-200 ${
              compact
                ? "px-2 py-1.5 rounded-lg"
                : "px-2.5 py-2 rounded-xl"
            } ${
              isSelected ? "bg-black text-white shadow-sm" : "text-neutral-600 hover:bg-black/5"
            }`}
          >
            <div className={`flex-shrink-0 rounded-md flex items-center justify-center font-bold ${
              compact ? "w-6 h-6 text-[7px]" : "w-7 h-7 rounded-lg text-[7px]"
            }`} style={{ backgroundColor: style.bg, color: style.text }}>
              {style.label}
            </div>
            <span className={`font-medium truncate ${compact ? "text-[11px]" : "text-xs"} ${isSelected ? "text-white" : "text-neutral-700"}`}>
              {file.name}
            </span>
            {!compact && (
              <span className={`ml-auto text-[9px] ${isSelected ? "text-white/60" : "text-neutral-400"}`}>{file.size}</span>
            )}
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* 标题 + 上传按钮 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-black/5">
        <h2 className="text-sm font-semibold text-neutral-700 tracking-tight">我的文档</h2>
        <label className="cursor-pointer w-6 h-6 rounded-md flex items-center justify-center hover:bg-black/10 text-neutral-400 transition" title="上传新文件">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <input type="file" accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.webp" className="hidden" onChange={handleUpload} />
        </label>
      </div>

      {/* 上传进度：受理后就能看到阶段与百分比 */}
      {uploadProgress && (
        <div role="status" className="px-4 py-2 border-b border-black/5 space-y-1">
          <div className="flex items-center justify-between gap-2 text-[10px] text-neutral-500">
            <span className="truncate" title={uploadProgress.fileName}>{uploadProgress.fileName}</span>
            <span className="flex-shrink-0 tabular-nums">{Math.round(uploadProgress.progress * 100)}%</span>
          </div>
          <div className="h-1 rounded-full bg-black/5 overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                uploadProgress.status === "failed" ? "bg-red-500" : "bg-blue-500"
              }`}
              style={{ width: `${Math.round(uploadProgress.progress * 100)}%` }}
            />
          </div>
          <p className={`text-[10px] ${uploadProgress.status === "failed" ? "text-red-600" : "text-neutral-400"}`}>
            {describeProgress(uploadProgress)}
          </p>
        </div>
      )}

      {/* 搜索框 */}
      <div className="px-3 py-2 border-b border-black/5">
        <div className="relative">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文件名..."
            className="w-full h-7 pl-7 pr-2 rounded-lg bg-black/5 text-[11px] text-neutral-600 placeholder-neutral-400 outline-none border-none focus:ring-1 focus:ring-blue-500/30 transition-all"
          />
        </div>
      </div>

      {/* 文件夹树 */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5 scrollbar-hide" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
        {/* 搜索模式 */}
        {isSearching && searchResults && (
          <>
            {searchResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                <p className="text-xs text-neutral-400">暂无匹配文件</p>
              </div>
            ) : (
              <div className="space-y-0.5">
                {searchResults.map((file) => renderFileButton(file, false))}
              </div>
            )}
          </>
        )}

        {/* 非搜索模式：文件夹树 */}
        {!isSearching && (
          <div className="space-y-0.5">
            {/* 无所属文件夹的文件（不上传） */}
            {(() => {
              const uncategorized = allFiles.filter((f) => !f.category || f.category === "");
              if (uncategorized.length === 0) return null;
              return (
                <div className="ml-3 space-y-0.5 mb-1">
                  {uncategorized.map((file) => renderFileButton(file, true))}
                </div>
              );
            })()}
            {folders.map((folder) => {
              const folderFiles = getFolderFiles(folder.key);
              const isExpanded = expandedFolders.has(folder.key);
              return (
                <div key={folder.key}>
                  <button
                    onClick={() => toggleFolder(folder.key)}
                    className="cursor-pointer w-full flex items-center gap-2 px-2.5 py-2 rounded-xl text-left text-neutral-600 hover:bg-black/5 transition-all duration-200">
                    <motion.span animate={{ rotate: isExpanded ? 90 : 0 }} transition={{ duration: 0.15 }}
                      className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 18 15 12 9 6" /></svg>
                    </motion.span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="flex-shrink-0 text-amber-500">
                      <path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v1H2V6zM2 10h20v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8z" />
                    </svg>
                    <span className="text-xs font-medium text-neutral-700 truncate flex-1">{folder.label}</span>
                    <span className="text-[10px] text-neutral-400">{folderFiles.length}</span>
                  </button>
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
                        className="overflow-hidden">
                        <div className="ml-5 border-l border-black/10 pl-2 space-y-0.5">
                          {folderFiles.map((file) => renderFileButton(file, true))}
                          {folderFiles.length === 0 && (
                            <p className="text-[10px] text-neutral-400 px-2 py-1">暂无文件</p>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 右键菜单 - 使用 Portal 确保在整个页面最上层 */}
      {contextMenu && createPortal(
        <>
          <div className="fixed inset-0 z-[9999]" onClick={closeContextMenu} onKeyDown={(e) => { if (e.key === 'Escape') closeContextMenu(); }} tabIndex={0} role="button" aria-label="关闭菜单" />
          <div className="fixed z-[10000] bg-white rounded-xl shadow-xl border border-black/10 py-1 min-w-[160px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}>
            <button onClick={() => handleStartRename(contextMenu.fileId)}
              className="cursor-pointer w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-700 hover:bg-black/5 transition">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
              重命名
            </button>
            <div className="border-t border-black/5 my-1" />
            <div className="px-3 py-1 text-[10px] font-medium text-neutral-400">移动到</div>
            {folders.filter((f) => f.key !== (getFileCategory(contextMenu.fileId) || "")).map((f) => (
              <button key={f.key} onClick={() => handleMove(contextMenu.fileId, f.key)}
                className="cursor-pointer w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-700 hover:bg-black/5 transition">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber-500">
                  <path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v1H2V6zM2 10h20v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8z" />
                </svg>
                {f.label}
              </button>
            ))}
            <button onClick={() => handleMove(contextMenu.fileId, "")}
              className="cursor-pointer w-full flex items-center gap-2 px-3 py-2 text-xs text-neutral-700 hover:bg-black/5 transition">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
              移出文件夹
            </button>
            <div className="border-t border-black/5 my-1" />
            <button onClick={() => handleDelete(contextMenu.fileId)}
              className="cursor-pointer w-full flex items-center gap-2 px-3 py-2 text-xs text-red-600 hover:bg-red-50 transition">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
              删除
            </button>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}
