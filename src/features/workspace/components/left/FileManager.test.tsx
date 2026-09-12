import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import FileManager, { type FileItem, type Folder } from "./FileManager";
import { pollIngestJob, uploadDocument, type IngestJob } from "../../../../lib/upload";

/**
 * 上传走真实网络（见 src/lib/upload.ts），测试里把这两个调用换掉；
 * `describeProgress` 等纯函数保留真实实现 —— UI 文案正是要验证的部分。
 */
vi.mock("../../../../lib/upload", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../../lib/upload")>();
  return { ...actual, uploadDocument: vi.fn(), pollIngestJob: vi.fn() };
});

const uploadDocumentMock = vi.mocked(uploadDocument);
const pollIngestJobMock = vi.mocked(pollIngestJob);

function makeJob(overrides: Partial<IngestJob> = {}): IngestJob {
  return {
    job_id: "job-1",
    filename: "cours-fr.pdf",
    status: "queued",
    stage: null,
    progress: 0,
    error: null,
    result: null,
    ...overrides,
  };
}

/** 通过隐藏的 file input 触发一次上传 */
function uploadFile(file: File) {
  const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
  Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
  fireEvent.change(fileInput);
}

function makeCourseFile() {
  return new File(["dummy content"], "cours-fr.pdf", { type: "application/pdf" });
}

describe("FileManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 默认：受理成功、随后立刻完成 —— 覆盖大多数用例，个别用例再各自覆盖
    uploadDocumentMock.mockResolvedValue(makeJob({ status: "queued" }));
    pollIngestJobMock.mockResolvedValue(makeJob({ status: "succeeded", progress: 1 }));
  });

  afterEach(() => {
    cleanup();
  });

  /* ===== 基础渲染 ===== */

  it("渲染文件管理标题和默认文件夹", () => {
    render(<FileManager />);
    expect(screen.getByText("我的文档")).toBeDefined();
    expect(screen.getByText("课程资料")).toBeDefined();
    expect(screen.getByText("考试复习")).toBeDefined();
    expect(screen.getByText("论文参考")).toBeDefined();
  });

  it("默认文件列表渲染在展开的文件夹中", () => {
    render(<FileManager />);
    // "课程资料" 默认展开
    expect(screen.getByText("cours-analyse-s1.pdf")).toBeDefined();
    expect(screen.getByText("TD-économie-chap2.docx")).toBeDefined();
  });

  /* ===== 搜索 ===== */

  it("搜索框过滤文件", () => {
    render(<FileManager />);
    const searchInput = screen.getByPlaceholderText("搜索文件名...");
    fireEvent.change(searchInput, { target: { value: "analyse" } });
    expect(screen.getByText("cours-analyse-s1.pdf")).toBeDefined();
  });

  it("空搜索结果显示空状态", () => {
    render(<FileManager />);
    const searchInput = screen.getByPlaceholderText("搜索文件名...");
    fireEvent.change(searchInput, { target: { value: "zzz_nonexistent_file" } });
    expect(screen.getByText("暂无匹配文件")).toBeDefined();
  });

  it("搜索模式下不显示文件夹结构", () => {
    render(<FileManager />);
    const searchInput = screen.getByPlaceholderText("搜索文件名...");
    fireEvent.change(searchInput, { target: { value: "cours" } });
    // 搜索模式下不应显示文件夹标题（课程资料仅在非搜索模式显示）
    expect(screen.queryByText("考试复习")).toBeNull();
  });

  /* ===== 文件夹展开/折叠 ===== */

  it("点击文件夹可展开子文件", () => {
    render(<FileManager />);
    expect(screen.queryByText("复习笔记-期中exam.pdf")).toBeNull();
    fireEvent.click(screen.getByText("考试复习"));
    expect(screen.getByText("复习笔记-期中exam.pdf")).toBeDefined();
  });

  it("展开的空文件夹显示「暂无文件」", () => {
    const folders = [{ key: "empty", label: "空文件夹" }];
    const files: FileItem[] = [];
    render(<FileManager folders={folders} files={files} />);
    fireEvent.click(screen.getByText("空文件夹"));
    expect(screen.getByText("暂无文件")).toBeDefined();
  });

  /* ===== 文件点击 ===== */

  it("点击文件触发 onFileSelect", () => {
    const onFileSelect = vi.fn();
    const onFileSelectWithName = vi.fn();
    render(<FileManager onFileSelect={onFileSelect} onFileSelectWithName={onFileSelectWithName} />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    expect(fileBtn).toBeDefined();
    if (fileBtn) {
      fireEvent.click(fileBtn);
      expect(onFileSelect).toHaveBeenCalledWith("f1");
      expect(onFileSelectWithName).toHaveBeenCalledWith("f1", "cours-analyse-s1.pdf");
    }
  });

  it("仅 onFileSelect 回调时只触发一个", () => {
    const onFileSelect = vi.fn();
    render(<FileManager onFileSelect={onFileSelect} />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.click(fileBtn);
      expect(onFileSelect).toHaveBeenCalledWith("f1");
    }
  });

  /* ===== 上传 ===== */

  it("上传新文件触发文件列表更新", () => {
    render(<FileManager />);
    const uploadLabel = screen.getByTitle("上传新文件");
    const fileInput = uploadLabel.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeDefined();
    const file = new File(["dummy content"], "nouveau-cours.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);
    // 文件名会出现在两处：上传进度区与文件列表条目
    expect(screen.getAllByText("nouveau-cours.pdf")).toHaveLength(2);
  });

  it("上传空文件列表不会报错", () => {
    render(<FileManager />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeDefined();
    // 空 file 列表（用户取消选择）
    Object.defineProperty(fileInput, "files", { value: [] });
    fireEvent.change(fileInput);
    // 不应有额外文件出现
    expect(screen.getByText("cours-analyse-s1.pdf")).toBeDefined();
  });

  /* ===== 上传：异步受理 + 进度反馈（docs/specs/us-stage1-upload-async.md AC10） ===== */

  it("上传后展示当前阶段与百分比", async () => {
    pollIngestJobMock.mockImplementation((_jobId, options) => {
      options?.onUpdate?.(makeJob({ status: "running", stage: "embedding", progress: 0.5 }));
      return new Promise<never>(() => {}); // 挂住：只验证中间态
    });

    render(<FileManager />);
    uploadFile(makeCourseFile());

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("cours-fr.pdf");
    expect(status.textContent).toContain("正在向量化片段");
    expect(status.textContent).toContain("50%");
  });

  it("解析完成后展示完成文案与 100%", async () => {
    pollIngestJobMock.mockImplementation(async (_jobId, options) => {
      const finished = makeJob({ status: "succeeded", stage: "persisting", progress: 1 });
      options?.onUpdate?.(finished);
      return finished;
    });

    render(<FileManager />);
    uploadFile(makeCourseFile());

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("解析完成")
    );
    expect(screen.getByRole("status").textContent).toContain("100%");
  });

  it("摄取失败时展示失败原因，而不是静默消失", async () => {
    pollIngestJobMock.mockImplementation(async (_jobId, options) => {
      const failed = makeJob({ status: "failed", error: "ValueError: 解析器无法解析该文件" });
      options?.onUpdate?.(failed);
      return failed;
    });

    render(<FileManager />);
    uploadFile(makeCourseFile());

    expect(await screen.findByText(/解析失败：ValueError/)).toBeDefined();
    // 文件条目保留在列表里（进度区也会显示文件名），用户才知道是哪一份没进去
    expect(screen.getAllByText("cours-fr.pdf")).toHaveLength(2);
  });

  it("受理请求被拒时展示后端给出的原因", async () => {
    uploadDocumentMock.mockRejectedValue(new Error("暂不支持 .ppt 格式"));

    render(<FileManager />);
    uploadFile(new File(["x"], "slides.ppt"));

    expect(await screen.findByText(/暂不支持 .ppt 格式/)).toBeDefined();
  });

  /* ===== 上传按钮 ===== */

  it("上传标签区域存在", () => {
    render(<FileManager />);
    expect(screen.getByTitle("上传新文件")).toBeDefined();
  });

  /* ===== 右键菜单: 重命名 ===== */

  it("右键菜单操作-重命名", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    expect(fileBtn).toBeDefined();
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      expect(screen.getByText("重命名")).toBeDefined();
      fireEvent.click(screen.getByText("重命名"));
      const renameInput = document.querySelector("input.border-blue-400") as HTMLInputElement;
      expect(renameInput).toBeDefined();
    }
  });

  it("重命名提交后文件名称更新（blur 保存）", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      fireEvent.click(screen.getByText("重命名"));
      const renameInput = document.querySelector("input.border-blue-400") as HTMLInputElement;
      if (renameInput) {
        fireEvent.change(renameInput, { target: { value: "新名称.pdf" } });
        fireEvent.blur(renameInput);
        expect(screen.getByText("新名称.pdf")).toBeDefined();
        expect(screen.queryByText("cours-analyse-s1.pdf")).toBeNull();
      }
    }
  });

  it("重命名 Enter 键提交", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      fireEvent.click(screen.getByText("重命名"));
      const renameInput = document.querySelector("input.border-blue-400") as HTMLInputElement;
      if (renameInput) {
        fireEvent.change(renameInput, { target: { value: "enter-name.pdf" } });
        fireEvent.keyDown(renameInput, { key: "Enter" });
        expect(screen.getByText("enter-name.pdf")).toBeDefined();
      }
    }
  });

  it("重命名 Escape 取消", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      fireEvent.click(screen.getByText("重命名"));
      const renameInput = document.querySelector("input.border-blue-400") as HTMLInputElement;
      if (renameInput) {
        fireEvent.change(renameInput, { target: { value: "cancelled.pdf" } });
        fireEvent.keyDown(renameInput, { key: "Escape" });
        // 取消后应恢复原标题
        expect(screen.getByText("cours-analyse-s1.pdf")).toBeDefined();
        expect(screen.queryByText("cancelled.pdf")).toBeNull();
      }
    }
  });

  /* ===== 右键菜单: 删除 ===== */

  it("右键菜单操作-删除", () => {
    render(<FileManager />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      expect(screen.getByText("删除")).toBeDefined();
      fireEvent.click(screen.getByText("删除"));
      expect(screen.queryByText("cours-analyse-s1.pdf")).toBeNull();
    }
  });

  /* ===== 右键菜单: 移动到 ===== */

  it("右键菜单操作-移动到其他文件夹", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      expect(screen.getByText("移动到")).toBeDefined();
      expect(screen.getByText("移出文件夹")).toBeDefined();
      // 不应出现当前文件夹的选项
      expect(screen.queryByText("移到课程资料")).toBeNull();
    }
  });

  it("右键菜单移动到指定文件夹", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      const moveTargets = screen.getAllByText("论文参考");
      const moveTarget = moveTargets[moveTargets.length - 1];
      fireEvent.click(moveTarget);
      expect(screen.queryByText("重命名")).toBeNull(); // 菜单已关闭
    }
  });

  it("右键菜单移出文件夹", () => {
    render(<FileManager />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      fireEvent.click(screen.getByText("移出文件夹"));
      expect(screen.queryByText("重命名")).toBeNull(); // 菜单已关闭
    }
  });

  /* ===== 右键菜单: 关闭 ===== */

  it("右键菜单可通过 Escape 关闭", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      expect(screen.getByText("删除")).toBeDefined();
      const backdrop = document.querySelector('[aria-label="关闭菜单"]');
      expect(backdrop).toBeDefined();
      fireEvent.keyDown(backdrop!, { key: "Escape" });
      expect(screen.queryByText("删除")).toBeNull();
    }
  });

  it("右键菜单点击 backdrop 关闭", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    if (fileBtn) {
      fireEvent.contextMenu(fileBtn);
      expect(screen.getByText("重命名")).toBeDefined();
      const backdrop = document.querySelector('[aria-label="关闭菜单"]');
      expect(backdrop).toBeDefined();
      fireEvent.click(backdrop!);
      expect(screen.queryByText("重命名")).toBeNull();
    }
  });

  /* ===== 选中样式 ===== */

  it("选中文件时应用选中样式", () => {
    render(<FileManager selectedFileId="f1" />);
    const fileBtn = screen.getByText("cours-analyse-s1.pdf").closest("button");
    expect(fileBtn).toBeDefined();
    if (fileBtn) {
      expect(fileBtn.className).toContain("bg-black");
      expect(fileBtn.className).toContain("text-white");
    }
  });

  /* ===== 外部传入数据 ===== */

  it("外部传入 files 和 folders 覆盖默认数据", () => {
    const externalFiles: FileItem[] = [
      { id: "ext1", name: "external.pdf", type: "PDF", category: "custom", size: "1 MB", date: "2025-01-01", status: "parsed" },
    ];
    const externalFolders: Folder[] = [{ key: "custom", label: "自定义文件夹" }];
    render(<FileManager files={externalFiles} folders={externalFolders} />);
    fireEvent.click(screen.getByText("自定义文件夹"));
    expect(screen.getByText("external.pdf")).toBeDefined();
    expect(screen.queryByText("课程资料")).toBeNull();
  });

  /* ===== 无归属文件 ===== */

  it("无类别文件显示在未分类区域", () => {
    const files: FileItem[] = [
      { id: "uncat1", name: "无归属文件.txt", type: "TXT", category: "", size: "1 KB", date: "2025-01-01", status: "pending" },
    ];
    render(<FileManager files={files} folders={[]} />);
    expect(screen.getByText("无归属文件.txt")).toBeDefined();
  });

  /* ===== 不同类型文件样式 ===== */

  it("所有文件类型样式映射正确", () => {
    const allTypes: FileItem[] = [
      { id: "t1", name: "a.pdf", type: "PDF", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "t2", name: "b.docx", type: "DOC", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "t3", name: "c.pptx", type: "PPT", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "t4", name: "d.png", type: "IMG", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "t5", name: "e.txt", type: "TXT", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "t6", name: "f.md", type: "MD", category: "docs", size: "1 KB", date: "2025-01-01", status: "parsed" },
    ];
    const folders: Folder[] = [{ key: "docs", label: "各类文档" }];
    const { container } = render(<FileManager files={allTypes} folders={folders} />);
    fireEvent.click(screen.getByText("各类文档"));
    expect(screen.getByText("a.pdf")).toBeDefined();
    expect(screen.getByText("b.docx")).toBeDefined();
    expect(screen.getByText("c.pptx")).toBeDefined();
    expect(screen.getByText("d.png")).toBeDefined();
    expect(screen.getByText("e.txt")).toBeDefined();
    expect(screen.getByText("f.md")).toBeDefined();
    // 验证标签样式
    const labels = container.querySelectorAll("[class*='rounded-md']");
    expect(labels.length).toBeGreaterThanOrEqual(6);
  });

  /* ===== 文件排序 ===== */

  it("文件按状态排序：已解析优先", () => {
    const folders: Folder[] = [{ key: "test", label: "测试排序" }];
    const files: FileItem[] = [
      { id: "s1", name: "z-parsed.pdf", type: "PDF", category: "test", size: "1 KB", date: "2025-01-01", status: "parsed" },
      { id: "s2", name: "a-pending.pdf", type: "PDF", category: "test", size: "1 KB", date: "2025-01-01", status: "pending" },
      { id: "s3", name: "b-parsing.pdf", type: "PDF", category: "test", size: "1 KB", date: "2025-01-01", status: "parsing" },
    ];
    render(<FileManager files={files} folders={folders} />);
    fireEvent.click(screen.getByText("测试排序"));
    // 展开后所有文件都可见
    expect(screen.getByText("z-parsed.pdf")).toBeDefined();
    expect(screen.getByText("a-pending.pdf")).toBeDefined();
    expect(screen.getByText("b-parsing.pdf")).toBeDefined();
  });

  /* ===== 紧凑模式渲染 ===== */

  it("文件夹内文件使用紧凑模式", () => {
    const folders: Folder[] = [{ key: "compact", label: "紧凑模式" }];
    const files: FileItem[] = [
      { id: "cmp1", name: "compact.pdf", type: "PDF", category: "compact", size: "1 KB", date: "2025-01-01", status: "parsed" },
    ];
    render(<FileManager files={files} folders={folders} />);
    fireEvent.click(screen.getByText("紧凑模式"));
    const fileBtn = screen.getByText("compact.pdf").closest("button");
    expect(fileBtn).toBeDefined();
    // 紧凑模式下不显示文件大小
    expect(screen.queryByText("1 KB")).toBeNull();
  });
});
