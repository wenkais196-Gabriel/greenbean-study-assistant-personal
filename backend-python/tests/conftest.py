import os
import sys
import tempfile
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = TESTS_ROOT / "fixtures"
PDF_FIXTURES_ROOT = FIXTURES_ROOT / "pdf"
TEST_TEMP_ROOT = TESTS_ROOT / "tmp" / "pytest" / str(os.getpid())

TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEST_TEMP_ROOT)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def pytest_configure(config):
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = str(TEST_TEMP_ROOT)


def pytest_collection_modifyitems(items):
    """根据测试所在目录自动添加测试层级标记。"""
    for item in items:
        path_parts = Path(str(item.path)).parts
        if "unit" in path_parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in path_parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def pdf_fixtures_dir() -> Path:
    return PDF_FIXTURES_ROOT


@pytest.fixture
def provider_config_factory():
    from app.entities.provider_config import ProviderConfig
    from app.enums.api_mode import ApiMode

    def make_config(name: str = "test-cfg", is_active: bool = False) -> ProviderConfig:
        return ProviderConfig(
            name=name,
            api_mode=ApiMode.OPENAI_COMPAT,
            api_key="sk-test",
            api_host="https://api.test.com",
            model_id="test-model",
            display_name=name,
            is_active=is_active,
        )

    return make_config


@pytest.fixture(scope="session")
def text_two_pages_pdf_path(pdf_fixtures_dir: Path) -> Path:
    """两页文本型 PDF fixture：由 `scripts/make_synthetic_corpus.py` 自产，别手工替换。

    换内容要改生成脚本再重新生成（`--check` 会拦住产物与脚本不一致的情况），
    字符数契约见 `tests/integration/document/test_pdf_ingest_pipeline.py`。
    """
    return pdf_fixtures_dir / "text_two_pages.pdf"


@pytest.fixture(scope="session")
def text_two_pages_pdf_bytes(text_two_pages_pdf_path: Path) -> bytes:
    return text_two_pages_pdf_path.read_bytes()
