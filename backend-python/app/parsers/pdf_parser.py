# PDF 解析器：解析 PDF 文本、页码和结构信息。
# backend-python/app/parsers/pdf_parser.py
import fitz  # PyMuPDF
from typing import List, Dict, Any

from app.utils.text_utils import repair_broken_accents

PARSER_NAME = "PDFParser"
PARSER_VERSION = "1.1.0"


class PDFParser:
    def parse(self, file_content: bytes) -> List[Dict[str, Any]]:
        """
        解析 PDF 字节流，提取文本并构建初始的 PageIndex 结构。

        ⚠️ PyMuPDF 对部分 PDF 会把法语重音拆成「修饰符 + 基字母」（`général` → `g´en´eral`），
        这会直接劣化下游的向量质量（实测同一句话的余弦相似度从 1.0 掉到 0.38），
        因此在解析阶段就还原，并把修复处数写进 metadata 供观测。

        :param file_content: 前端上传文件的二进制数据
        :return: 包含每页文本和元数据的列表
        """
        # 从内存中的字节流直接打开 PDF，避免本地磁盘二次 I/O
        doc = fitz.open(stream=file_content, filetype="pdf")
        parsed_pages = []

        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # 提取纯文本，并还原被拆开的重音
                text, accent_repairs = repair_broken_accents(page.get_text("text").strip())

                # 构造单页的 PageIndex 节点
                page_node = {
                    "page_number": page_num + 1,
                    "content": text,
                    "char_count": len(text),
                    "parser_name": PARSER_NAME,
                    "parser_version": PARSER_VERSION,
                    "metadata": {
                        "source_type": "pdf",
                        "headings": [],
                        "paragraphs_count": len([p for p in text.split("\n\n") if p.strip()]),
                        "accent_repairs": accent_repairs,
                    }
                }
                parsed_pages.append(page_node)
        finally:
            doc.close()

        return parsed_pages
