"""
Provider 配置的 HTTP 接口（`/api/providers`）端到端：

跑真的 FastAPI 路由 + 真的 SQLite（假的是"外部 LLM"这一层，本文件根本不需要它）。
这里验证的是**界面能不能把模型配起来**：列表 / 新增 / 更新 / 删除 / 激活，
以及两条硬约束 —— 响应里不许出现 `api_key`、重复 name 必须是 409。

⚠️ 关于"激活后 POST /api/chat 不再 503"：这一条在 `test_chat_flow.py` 里由假 provider 覆盖，
本文件断言的是同一机制的下游 —— 激活后 `ProviderRegistry.get_active()` 真的能拿到实例
（`ChatService` 用的就是这个 registry，拿不到就是 503）。
"""
import pytest
from fastapi.testclient import TestClient

from app.api.provider_controller import ProviderController, get_provider_controller
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.enums.api_mode import ApiMode
from app.main import app
from app.providers.registry import ProviderRegistry
from app.services.provider_service import ProviderService

pytestmark = [pytest.mark.integration]

DIMENSION = 8
API_KEY = "sk-secret-value"


@pytest.fixture
def provider_service(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        database_name="providers.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    try:
        yield ProviderService(SqlAlchemyUnitOfWork(create_session_factory(engine)))
    finally:
        engine.dispose()
        # registry 是类级状态：不清干净会串到别的测试
        ProviderRegistry.clear()


@pytest.fixture
def client(provider_service):
    app.dependency_overrides[get_provider_controller] = lambda: ProviderController(provider_service)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _payload(name: str = "deepseek", **overrides) -> dict:
    payload = {
        "name": name,
        "api_mode": ApiMode.OPENAI_COMPAT.value,
        "api_key": API_KEY,
        "api_host": "https://api.deepseek.com",
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek 对话",
    }
    payload.update(overrides)
    return payload


def _create(client: TestClient, name: str = "deepseek", **overrides) -> dict:
    response = client.post("/api/providers", json=_payload(name, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_provider_returns_config_without_api_key(client):
    """新建配置：返回可展示的字段，但**绝不回传密钥**。"""
    body = _create(client)

    assert body["name"] == "deepseek"
    assert body["model_id"] == "deepseek-chat"
    assert body["is_active"] is False
    assert body["id"]
    assert "api_key" not in body


def test_list_providers_hides_api_key(client):
    _create(client, name="deepseek")
    _create(client, name="openai", display_name="OpenAI")

    response = client.get("/api/providers")

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body] == ["deepseek", "openai"]
    assert API_KEY not in response.text, "列表响应里不能出现密钥"


def test_get_provider_by_id(client):
    created = _create(client)

    response = client.get(f"/api/providers/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_provider_returns_404(client):
    assert client.get("/api/providers/does-not-exist").status_code == 404


def test_update_provider_changes_display_name(client):
    created = _create(client)

    response = client.put(
        f"/api/providers/{created['id']}",
        json={"display_name": "DeepSeek 推理版"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "DeepSeek 推理版"


def test_update_unknown_provider_returns_404(client):
    response = client.put("/api/providers/does-not-exist", json={"display_name": "x"})
    assert response.status_code == 404


def test_create_duplicate_name_returns_409(client):
    _create(client, name="deepseek")

    response = client.post("/api/providers", json=_payload("deepseek"))

    assert response.status_code == 409


def test_update_to_taken_name_returns_409(client):
    _create(client, name="deepseek")
    other = _create(client, name="openai", display_name="OpenAI")

    response = client.put(f"/api/providers/{other['id']}", json={"name": "deepseek"})

    assert response.status_code == 409


def test_activate_provider_makes_it_usable(client):
    """激活之后 `ProviderRegistry` 里真的有 provider —— chat 不会再 503。"""
    _create(client, name="deepseek")
    second = _create(client, name="openai", display_name="OpenAI")

    response = client.post(f"/api/providers/{second['id']}/activate")

    assert response.status_code == 200
    assert response.json()["id"] == second["id"]
    assert client.get("/api/providers/active").json()["id"] == second["id"]

    active = ProviderRegistry.get_active()
    assert active.config.model_id == "deepseek-chat"  # 假配置，模型名来自 payload 默认值


def test_active_returns_404_when_nothing_activated(client):
    _create(client)

    assert client.get("/api/providers/active").status_code == 404


def test_activate_unknown_provider_returns_404(client):
    assert client.post("/api/providers/does-not-exist/activate").status_code == 404


def test_delete_provider_removes_it(client):
    created = _create(client)

    response = client.delete(f"/api/providers/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/providers/{created['id']}").status_code == 404


def test_delete_unknown_provider_returns_404(client):
    assert client.delete("/api/providers/does-not-exist").status_code == 404


def test_get_provider_controller_assembles_service_without_touching_disk():
    """依赖注入函数本身也要被覆盖到（其余用例用 `dependency_overrides` 把它盖掉了）。

    它只做装配：`lazy_session_factory` 不建库，建库推迟到第一次真正开会话时。
    """
    controller = get_provider_controller()

    assert isinstance(controller, ProviderController)
    assert isinstance(controller.service, ProviderService)
