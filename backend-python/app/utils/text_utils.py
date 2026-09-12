"""
文本工具模块，用于封装清洗、截断和格式化辅助逻辑。
"""
import re
import unicodedata
from typing import List, Optional


def clean_text(text: str) -> str:
    """
    清洗文本：去除多余空白、空行，规范化换行符。
    
    :param text: 原始文本
    :return: 清洗后的文本
    """
    if not text:
        return ""
    
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # 去除连续空白行（保留单个换行）
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # 去除首尾空白
    text = text.strip()
    
    return text


def truncate_text(text: str, max_chars: int = 10000, ellipsis: str = "...") -> str:
    """
    截断文本到指定最大字符数。
    
    :param text: 原始文本
    :param max_chars: 最大字符数
    :param ellipsis: 截断后缀
    :return: 截断后的文本
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + ellipsis


def split_into_paragraphs(text: str) -> List[str]:
    """
    将文本按空行分割为段落列表。
    
    :param text: 原始文本
    :return: 段落列表
    """
    if not text:
        return []
    
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def count_words(text: str) -> int:
    """
    统计文本中的单词数（适用于英文、法文等空格分隔的语言）。
    
    :param text: 文本
    :return: 单词数
    """
    if not text:
        return 0
    return len(text.split())


def contains_chinese(text: str) -> bool:
    """
    检测文本是否包含中文字符。
    
    :param text: 文本
    :return: True 如果包含中文字符
    """
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def contains_french(text: str) -> bool:
    """
    检测文本是否包含法语特殊字符。
    
    :param text: 文本
    :return: True 如果包含法语字符
    """
    return bool(re.search(r"[éèêëàâäùûüôöîïçœæ]", text, re.IGNORECASE))


def detect_language(text: str) -> str:
    """
    简单检测文本主要语言（中/英/法）。
    
    :param text: 文本
    :return: 语言代码 'zh', 'fr', 'en'
    """
    if not text:
        return "en"
    
    sample = text[:500]
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", sample))
    french_chars = len(re.findall(r"[éèêëàâäùûüôöîïçœæ]", sample, re.IGNORECASE))
    
    if chinese_chars > len(sample) * 0.1:
        return "zh"
    elif french_chars > 3:
        return "fr"
    else:
        return "en"

# PDF（PyMuPDF）提取部分文件时，会把法语重音拆成「修饰符 + 基字母」：
#   général → g´en´eral ／ à → `a ／ reconnaître → reconnaˆıtre
# 方向实测全部是"修饰符在字母之前"，因此按「交换位置 + NFC 合成」还原。
BROKEN_ACCENT_MARKS: dict[str, str] = {
    "`": "\u0300",  # U+0060 grave
    "´": "\u0301",  # U+00B4 acute
    "ˆ": "\u0302",  # U+02C6 circumflex
    "˜": "\u0303",  # U+02DC tilde
    "¨": "\u0308",  # U+00A8 diaeresis
    "¸": "\u0327",  # U+00B8 cedilla
}

# 修饰符的两种形态：独立字符（PDF 拆裂产物）与组合符（可能已被拆到字母之前）
_BROKEN_ACCENT_CLASS = "`´ˆ˜¨¸\u0300\u0301\u0302\u0303\u0308\u0327"

# 「修饰符 + 基字母」：只匹配裸字母（含 dotless ı），所以已被正常提取的 `é` 不会被二次改动
_BROKEN_ACCENT_PATTERN = re.compile(
    rf"(?P<mark>[{_BROKEN_ACCENT_CLASS}])(?P<base>[A-Za-z\u0131])"
)


def repair_broken_accents(text: str) -> tuple[str, int]:
    """
    还原 PDF 提取时被拆开的法语重音。

    做法：先把修饰符搬到基字母之后（即 NFD 的 base + combining mark 顺序），
    再交给 NFC 合成预组合字符；`ı`（dotless i）+ circumflex 无法被 NFC 合成，单独替换为 `î`。

    ⚠️ 刻意**不处理** ASCII 的 `^` 与 `~`：技术资料里它们可能是幂运算（`x^n`）或约等号，
    把后一个字母合成重音会破坏原文。

    :param text: 原始文本
    :return: (修复后的文本, 修复处数)；处数供解析器写入 metadata，便于观测污染规模
    """
    if not text:
        return "", 0

    def _swap(match: "re.Match[str]") -> str:
        mark = match.group("mark")
        return match.group("base") + BROKEN_ACCENT_MARKS.get(mark, mark)

    repaired, repairs = _BROKEN_ACCENT_PATTERN.subn(_swap, text)
    repaired = repaired.replace("\u0131\u0302", "\u00ee")  # ı + ˆ → î
    return unicodedata.normalize("NFC", repaired), repairs
