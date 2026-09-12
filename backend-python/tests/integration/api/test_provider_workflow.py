import sqlite3

import sqlite_vec
from unittest.mock import patch

import pytest

from app.api.provider_controller import ProviderController
from app.db.init_db import initialize_database
from app.db.orm import create_database_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.enums.api_mode import ApiMode
from app.providers.registry import ProviderRegistry
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.schemas.provider_schema import ProviderConfigCreateRequest
from app.services.provider_service import ProviderService


def load_test_sqlite_vec(connection: sqlite3.Connection) -> None:
    """真加载 sqlite-vec（vec0 模块是建索引表的前提），但把 vec_version 覆盖为固定测试值。"""
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)
    connection.create_function("vec_version", 0, lambda: "test-sqlite-vec")


@patch("app.providers.openai_compat_provider.AsyncOpenAI")
@pytest.mark.asyncio
async def test_create_activate_and_get_active_provider_persists_to_sqlite(
    MockAsyncOpenAI, tmp_path
):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    session_factory = create_session_factory(engine)
    controller = ProviderController(
        ProviderService(SqlAlchemyUnitOfWork(session_factory))
    )

    ProviderRegistry.clear()
    try:
        first = await controller.create_provider(
            ProviderConfigCreateRequest(
                name="provider-a",
                api_mode=ApiMode.OPENAI_COMPAT,
                api_key="sk-provider-a",
                api_host="https://api-a.test.com",
                model_id="model-a",
                display_name="Provider A",
            )
        )
        second = await controller.create_provider(
            ProviderConfigCreateRequest(
                name="provider-b",
                api_mode=ApiMode.OPENAI_COMPAT,
                api_key="sk-provider-b",
                api_host="https://api-b.test.com",
                model_id="model-b",
                display_name="Provider B",
            )
        )

        activated = await controller.activate_provider(second.id)
        current = await controller.get_active_provider()

        with session_factory() as session:
            persisted = ProviderConfigRepository(session).list_all()
    finally:
        ProviderRegistry.clear()
        engine.dispose()

    assert {config.id for config in persisted} == {first.id, second.id}
    assert [config.id for config in persisted if config.is_active] == [second.id]
    assert activated == current
    assert current.name == "provider-b"
    assert current.display_name == "Provider B"
    assert current.model_id == "model-b"
    assert "api_key" not in current.model_dump()
    MockAsyncOpenAI.return_value.chat.completions.create.assert_not_called()
    assert ProviderRegistry.get_active_config() is None
