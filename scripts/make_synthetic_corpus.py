"""
生成合成课程语料：一套**完全自产、不含任何第三方受著作权保护材料**的演示与评测文档。

为什么要这个脚本（而不是直接提交一堆来历不明的 PDF）：
  - 真实语料（法国大学课件）有著作权，既不能进仓库分发，也不能出现在公开的 demo 录屏里；
  - 但从零手搓二进制文件无法复核、也无法重跑，出了问题只能靠猜。
  所以这里把**内容与生成方式都写进代码**，产物只是它的输出 —— 可审计、可重放。

**写什么**在 `synthetic_corpus_content.py`（六份讲义、格式样例、测试 fixture 的全部文本），
**怎么渲染与校验**在这个文件。语料有十几万字，混在一起会让生成逻辑淹没在文本里。

生成物（路径相对仓库根；`--root` 可整体改写前缀）：

  eval/fixtures/synthetic/pdf/*.pdf                     六份法语讲义（L1 评测主语料；run_eval.py 只索引这里的 PDF）
  eval/fixtures/synthetic/docx/*.docx                   Word 格式覆盖
  eval/fixtures/synthetic/pptx/*.pptx                   PPT 格式覆盖（1 张 slide = 1 个 DocumentUnit）
  eval/fixtures/synthetic/img/*.png                     图片格式覆盖（OCR 需要本机装 Tesseract）
  backend-python/tests/fixtures/pdf/text_two_pages.pdf  测试用两页 PDF，替换上游带进仓库的
                                                        那份真实课程作业说明

内容全部为**虚构**：虚构校名（Université de démonstration）、虚构教师、虚构邮箱与日期。
技术主题只使用公开事实（图灵 1950 年的论文、1956 年 Dartmouth 会议、SAT/CNF、交叉验证等）——
事实、算法与术语本身不受著作权保护。

⚠️ **但这些文本由语言模型生成、未经原创性核查，本项目不声称任何原创性** —— 其中像启发式
   可采纳性这类定义句属于领域内的惯常表述，抽查确认与多份公开课程材料措辞相近。完整声明见
   `synthetic_corpus_content.py` 顶部。

用法：
    python scripts/make_synthetic_corpus.py                # 生成到仓库内约定位置
    python scripts/make_synthetic_corpus.py --root <目录>   # 换一个前缀目录（产物路径相对它）
    python scripts/make_synthetic_corpus.py --check        # 只校验磁盘产物是否与脚本输出一致

确定性：PDF / DOCX / PNG 连字节都可复现（PDF 靠固定元数据 + `no_new_id`，DOCX 靠固定核心属性），
PPTX 的 zip 条目时间戳由 python-pptx 写成"当前时间"，所以 PPTX 只保证**内容**一致。
`--check` 因此按**内容**比对（PDF 比每页文本、DOCX/PPTX 比 zip 条目、PNG 比像素），而不是比字节 ——
字节还会随生成库的版本变化，比字节会在换环境时误报。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import zipfile
from collections.abc import Callable
from datetime import datetime
from functools import partial
from pathlib import Path

import docx
import fitz  # PyMuPDF
import pptx
from PIL import Image, ImageDraw

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:  # 让 `python scripts/make_synthetic_corpus.py` 能找到内容模块
    sys.path.insert(0, str(SCRIPTS_DIR))

from synthetic_corpus_content import (  # noqa: E402  （必须在 sys.path 调整之后导入）
    DOCUMENTS,
    DOCX_PARAGRAPHS,
    DOCX_TITLE,
    PNG_ROWS,
    PNG_TITLE,
    PPTX_SLIDES,
    PPTX_TITLE,
    TEST_FIXTURE_PAGES,
    TEST_FIXTURE_TITLE,
    Document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
# 产物路径（见 ARTIFACTS）以仓库根为基准；--root 用来把这一前缀整体换掉
DEFAULT_ROOT = REPO_ROOT

# 固定时间戳：产物必须可复现，元数据里不能出现"生成那一刻"
FIXED_TIME = datetime(2026, 1, 1, 0, 0, 0)
PDF_DATE = "D:20260101000000Z"
PRODUCER = "make_synthetic_corpus.py"

PDF_FONT = "helv"
PDF_FONT_BOLD = "hebo"
PDF_FONT_SIZE = 11
PDF_TITLE_SIZE = 16
PDF_LINE_HEIGHT = 1.45
PDF_MARGIN_X = 56.0
PDF_TOP = 56.0
PDF_BOTTOM = 800.0
PDF_GAP = 8.0

# PyMuPDF 的内置字体是 Base14（WinAnsi 编码）：ASCII、法语重音、«» 和 ° 都正确，
# 但 œ / ’ / — / – / • / € 会被静默替换成 "·"（实测），所以正文必须避开它们。
SAFE_NON_ASCII = "àâäçéèêëîïôöùûüÿÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ«»°"

PDF_DIR = "eval/fixtures/synthetic/pdf"
DOCX_DIR = "eval/fixtures/synthetic/docx"
PPTX_DIR = "eval/fixtures/synthetic/pptx"
PNG_DIR = "eval/fixtures/synthetic/img"
TEST_FIXTURE_PATH = "backend-python/tests/fixtures/pdf/text_two_pages.pdf"


def _assert_safe_chars(text: str, where: str) -> None:
    """PDF 内置字体是 WinAnsi 编码，非安全字符会被静默替换成 "·" —— 与其事后发现，不如直接拦住。"""
    bad = sorted({c for c in text if not c.isascii() and c not in SAFE_NON_ASCII and c != "\n"})
    if bad:
        raise ValueError(f"{where} 含 PDF 内置字体无法表示的字符：{bad}")


def _render_pdf(
    pages: tuple[tuple[str, tuple[str, ...]], ...],
    title: str,
    subject: str,
) -> bytes:
    """把 (标题, 段落) 列表渲染成 PDF：每页 = 一个 DocumentUnit，页码取决于传入顺序。"""
    document = fitz.open()
    try:
        for index, (page_title, paragraphs) in enumerate(pages, start=1):
            _assert_safe_chars(page_title, f"{title} 第 {index} 页标题")
            page = document.new_page()
            page.insert_textbox(
                fitz.Rect(PDF_MARGIN_X, PDF_TOP, 539.0, 100.0),
                page_title,
                fontname=PDF_FONT_BOLD,
                fontsize=PDF_TITLE_SIZE,
                lineheight=1.2,
            )
            cursor = 112.0
            for paragraph in paragraphs:
                _assert_safe_chars(paragraph, f"{title} 第 {index} 页正文")
                spare = page.insert_textbox(
                    fitz.Rect(PDF_MARGIN_X, cursor, 539.0, PDF_BOTTOM),
                    paragraph,
                    fontname=PDF_FONT,
                    fontsize=PDF_FONT_SIZE,
                    lineheight=PDF_LINE_HEIGHT,
                )
                if spare < 0:
                    raise ValueError(f"{title} 第 {index} 页内容溢出页面，请拆分为更多页")
                cursor = PDF_BOTTOM - spare + PDF_GAP
        document.set_metadata(
            {
                "title": title,
                "author": PRODUCER,
                "subject": subject,
                "producer": PRODUCER,
                "creator": PRODUCER,
                "creationDate": PDF_DATE,
                "modDate": PDF_DATE,
            }
        )
        # no_new_id：不重写文档 /ID，否则每次生成都会得到不同字节（实测）
        return document.tobytes(deflate=True, garbage=4, no_new_id=True)
    finally:
        document.close()


def build_document_pdf(document: Document) -> bytes:
    """渲染一份讲义。"""
    return _render_pdf(document.pages, document.title, document.subject)


def build_test_fixture_pdf() -> bytes:
    """两页测试文档，替换上游带进仓库的那份真实课程作业说明。"""
    return _render_pdf(TEST_FIXTURE_PAGES, TEST_FIXTURE_TITLE, "fixture de test autoproduite")


def build_docx() -> bytes:
    document = docx.Document()
    document.core_properties.title = DOCX_TITLE
    document.core_properties.author = PRODUCER
    document.core_properties.last_modified_by = PRODUCER
    document.core_properties.created = FIXED_TIME
    document.core_properties.modified = FIXED_TIME
    document.add_heading(DOCX_TITLE, level=1)
    for paragraph in DOCX_PARAGRAPHS:
        document.add_paragraph(paragraph)
    return _save_zip_container(document)


def build_pptx() -> bytes:
    presentation = pptx.Presentation()
    presentation.core_properties.title = PPTX_TITLE
    presentation.core_properties.author = PRODUCER
    presentation.core_properties.last_modified_by = PRODUCER
    presentation.core_properties.created = FIXED_TIME
    presentation.core_properties.modified = FIXED_TIME
    for title, bullets in PPTX_SLIDES:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = title
        body = slide.shapes.placeholders[1].text_frame
        for index, bullet in enumerate(bullets):
            paragraph = body.paragraphs[0] if index == 0 else body.add_paragraph()
            paragraph.text = bullet
    return _save_zip_container(presentation)


def build_png() -> bytes:
    image = Image.new("RGB", (720, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 20), PNG_TITLE, fill="black")
    for row_index, row in enumerate(PNG_ROWS):
        y = 70 + row_index * 30
        for column_index, cell in enumerate(row):
            draw.text((24 + column_index * 170, y), cell, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _save_zip_container(document) -> bytes:
    """python-docx / python-pptx 的 save() 接受文件路径，这里统一收到内存里。"""
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_artifacts() -> dict[str, Callable[[], bytes]]:
    """产物清单：key 是**相对仓库根**的路径（--root 可换前缀），value 是生成函数。

    路径写在这里而不是散落各处：它同时是 --check 的比对清单和文档的事实来源。
    """
    artifacts: dict[str, Callable[[], bytes]] = {
        f"{PDF_DIR}/{document.filename}": partial(build_document_pdf, document)
        for document in DOCUMENTS
    }
    artifacts[f"{DOCX_DIR}/tp-donnees-et-evaluation.docx"] = build_docx
    artifacts[f"{PPTX_DIR}/seance-recherche-arborescente.pptx"] = build_pptx
    artifacts[f"{PNG_DIR}/tableau-metriques.png"] = build_png
    artifacts[TEST_FIXTURE_PATH] = build_test_fixture_pdf
    return artifacts


ARTIFACTS: dict[str, Callable[[], bytes]] = _build_artifacts()


def content_digest(data: bytes, suffix: str) -> str:
    """把产物归一到「内容」层面再比较。

    不直接比字节：PDF 的 /ID、DOCX/PPTX 的 zip 条目时间戳、PNG 的编码细节都可能随
    生成库的版本变化，比字节会在换环境时误报"需要重新生成"。内容才是这个脚本的契约。
    """
    if suffix == ".pdf":
        with fitz.open(stream=data, filetype="pdf") as document:
            parts = [page.get_text().encode("utf-8") for page in document]
    elif suffix in {".docx", ".pptx"}:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = [archive.read(name) for name in sorted(archive.namelist())]
    elif suffix == ".png":
        with Image.open(io.BytesIO(data)) as image:
            parts = [image.convert("RGB").tobytes()]
    else:
        parts = [data]
    return hashlib.sha256(b"\x00".join(parts)).hexdigest()


def document_page_counts() -> list[tuple[str, int]]:
    """各讲义的页数：golden set 的页码依赖它，重建评测集时先看这里。"""
    return [(document.filename, len(document.pages)) for document in DOCUMENTS]


def generate(root: Path) -> list[tuple[Path, int]]:
    written: list[tuple[Path, int]] = []
    for relative, builder in ARTIFACTS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = builder()
        path.write_bytes(data)
        written.append((path, len(data)))
    return written


def check(root: Path) -> int:
    """比对磁盘产物与当前脚本的输出：内容不一致说明产物被手改过，或脚本改了没重新生成。"""
    mismatches: list[str] = []
    missing: list[str] = []
    for relative, builder in ARTIFACTS.items():
        path = root / relative
        if not path.exists():
            missing.append(relative)
            continue
        expected = content_digest(builder(), path.suffix)
        actual = content_digest(path.read_bytes(), path.suffix)
        if expected != actual:
            mismatches.append(relative)

    for relative in missing:
        print(f"缺失：{relative}")
    for relative in mismatches:
        print(f"与脚本输出不一致：{relative}")
    if missing or mismatches:
        print(f"\n❌ {len(missing) + len(mismatches)} 个产物需要重新生成（python scripts/make_synthetic_corpus.py）")
        return 1
    print(f"✅ {len(ARTIFACTS)} 个产物与当前脚本一致（{root}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成合成课程语料（自产内容，无第三方著作权）")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="产物根目录：ARTIFACTS 里的路径都相对它")
    parser.add_argument("--check", action="store_true", help="只校验磁盘产物是否与当前脚本一致")
    args = parser.parse_args()

    root = Path(args.root)
    if args.check:
        return check(root)

    for path, size in generate(root):
        print(f"生成 {path.relative_to(root)}（{size} 字节）")
    total_pages = 0
    for filename, pages in document_page_counts():
        total_pages += pages
        print(f"  {filename}：{pages} 页")
    print(f"\n共 {len(ARTIFACTS)} 个产物（六份讲义合计 {total_pages} 页），根目录：{root}")
    print("重新校验一致性：python scripts/make_synthetic_corpus.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
