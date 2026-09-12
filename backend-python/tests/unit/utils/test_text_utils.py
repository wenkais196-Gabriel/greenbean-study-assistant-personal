"""
文本工具模块测试，覆盖 text_utils.py 全部函数。
"""
import pytest
from app.utils.text_utils import (
    clean_text,
    truncate_text,
    split_into_paragraphs,
    count_words,
    contains_chinese,
    contains_french,
    detect_language,
    repair_broken_accents,
)


class TestCleanText:
    """测试 clean_text 函数"""

    def test_normal_text(self):
        assert clean_text("Hello World") == "Hello World"

    def test_strip_whitespace(self):
        assert clean_text("  Hello  ") == "Hello"

    def test_unify_newlines(self):
        result = clean_text("Line1\r\nLine2\rLine3")
        assert result == "Line1\nLine2\nLine3"

    def test_collapse_multiple_newlines(self):
        result = clean_text("Line1\n\n\n\nLine2")
        assert result == "Line1\n\nLine2"

    def test_empty_text(self):
        assert clean_text("") == ""

    def test_none_text(self):
        assert clean_text(None) == ""

    def test_only_whitespace(self):
        assert clean_text("   \n\n  ") == ""


class TestTruncateText:
    """测试 truncate_text 函数"""

    def test_short_text(self):
        assert truncate_text("Hello", 10) == "Hello"

    def test_exact_length(self):
        assert truncate_text("Hello", 5) == "Hello"

    def test_truncate(self):
        result = truncate_text("Hello World", 5)
        assert result == "Hello..."

    def test_custom_ellipsis(self):
        result = truncate_text("Hello World", 5, ellipsis=">>")
        assert result == "Hello>>"

    def test_empty_text(self):
        assert truncate_text("", 10) == ""


class TestSplitIntoParagraphs:
    """测试 split_into_paragraphs 函数"""

    def test_single_paragraph(self):
        assert split_into_paragraphs("Hello World") == ["Hello World"]

    def test_multiple_paragraphs(self):
        text = "Para1\n\nPara2\n\nPara3"
        result = split_into_paragraphs(text)
        assert result == ["Para1", "Para2", "Para3"]

    def test_empty_text(self):
        assert split_into_paragraphs("") == []

    def test_extra_blank_lines(self):
        text = "Para1\n\n\n\nPara2"
        result = split_into_paragraphs(text)
        assert result == ["Para1", "Para2"]


class TestCountWords:
    """测试 count_words 函数"""

    def test_normal_text(self):
        assert count_words("Hello World") == 2

    def test_multiple_spaces(self):
        assert count_words("Hello   World") == 2

    def test_empty_text(self):
        assert count_words("") == 0

    def test_chinese_text(self):
        # 中文按空格分词，所以整句算 1 个词
        assert count_words("你好世界") == 1


class TestContainsChinese:
    """测试 contains_chinese 函数"""

    def test_chinese_text(self):
        assert contains_chinese("你好世界") is True

    def test_mixed_text(self):
        assert contains_chinese("Hello 你好 World") is True

    def test_english_text(self):
        assert contains_chinese("Hello World") is False

    def test_french_text(self):
        assert contains_chinese("Bonjour le monde") is False

    def test_empty_text(self):
        assert contains_chinese("") is False


class TestContainsFrench:
    """测试 contains_french 函数"""

    def test_french_text(self):
        assert contains_french("français") is True
        assert contains_french("étudiant") is True
        assert contains_french("être") is True
        assert contains_french("déjà") is True
        assert contains_french("hôpital") is True
        assert contains_french("œuf") is True
        assert contains_french("ça") is True

    def test_non_french_text(self):
        assert contains_french("Bonjour") is False  # 没有特殊字符
        assert contains_french("Hello World") is False
        assert contains_french("你好世界") is False

    def test_empty_text(self):
        assert contains_french("") is False


class TestDetectLanguage:
    """测试 detect_language 函数"""

    def test_detect_chinese(self):
        assert detect_language("你好世界，这是一段中文文本") == "zh"

    def test_detect_english(self):
        assert detect_language("Hello World, this is English") == "en"

    def test_detect_french(self):
        # 需要至少 4 个法语特殊字符才能触发 french_chars > 3
        assert detect_language("J'étudie le français à l'école") == "fr"
        # "C'est déjà très bien" 只有 3 个特殊字符 (é, à, è)，不够触发法语检测
        assert detect_language("C'est déjà très bien") == "en"

    def test_mixed_chinese_english(self):
        # 中文占比 > 10%
        assert detect_language("你好 Hello World") == "zh"

    def test_empty_text(self):
        assert detect_language("") == "en"

    def test_short_text(self):
        assert detect_language("Hi") == "en"

class TestRepairBrokenAccents:
    """测试 repair_broken_accents 函数（PDF 提取把重音拆成「修饰符 + 基字母」时的还原）"""

    def test_repairs_acute_before_letter(self):
        repaired, repairs = repair_broken_accents("g´en´eral")

        assert repaired == "général"
        assert repairs == 2

    def test_repairs_multiple_marks_in_a_sentence(self):
        repaired, repairs = repair_broken_accents("Introduction `a l'IA et mani`ere g´en´erale")

        assert repaired == "Introduction à l'IA et manière générale"
        # `à`、`manière`、`générale`（两处重音）→ 共 4 处
        assert repairs == 4

    def test_repairs_dotless_i_circumflex(self):
        """`reconnaître` 会被拆成 `reconnaˆıtre`（dotless ı + circumflex），NFC 合不出 î，需单独还原。"""
        repaired, repairs = repair_broken_accents("reconnaˆıtre")

        assert repaired == "reconnaître"
        assert repairs == 1

    def test_repairs_cedilla(self):
        repaired, repairs = repair_broken_accents("¸c")

        assert repaired == "ç"
        assert repairs == 1

    def test_leaves_correctly_extracted_accents_untouched(self):
        text = "général déjà français"

        repaired, repairs = repair_broken_accents(text)

        assert repaired == text
        assert repairs == 0

    def test_does_not_touch_caret_and_tilde(self):
        """`^` 与 `~` 在技术资料里可能是幂运算 / 约等号，不能被合成重音。"""
        text = "x^n ~ 1 et 2^3"

        repaired, repairs = repair_broken_accents(text)

        assert repaired == text
        assert repairs == 0

    def test_empty_text(self):
        assert repair_broken_accents("") == ("", 0)
