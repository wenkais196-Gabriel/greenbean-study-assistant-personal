from unittest.mock import MagicMock, patch

import pytest

from app.enums.api_mode import ApiMode
from app.providers.registry import ProviderRegistry
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services.provider_service import ProviderNameConflictError, ProviderService


class TestProviderService:
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        ProviderRegistry.clear()
        yield
        ProviderRegistry.clear()

    @pytest.fixture
    def mock_uow(self):
        uow = MagicMock()
        uow.__enter__.return_value = uow
        uow.__exit__.return_value = None
        uow.session = MagicMock()
        return uow

    def test_create(self, mock_uow):
        service = ProviderService(uow=mock_uow)
        # 名字未被占用：`get_by_name` 返回 None 才走得下去
        with patch.object(ProviderConfigRepository, "get_by_name", return_value=None):
            result = service.create(
                {
                    "name": "new-cfg",
                    "api_mode": ApiMode.OPENAI_COMPAT,
                    "api_key": "sk-new",
                    "api_host": "https://api.new.com",
                    "model_id": "new-model",
                    "display_name": "New",
                }
            )
        assert result.name == "new-cfg"
        mock_uow.commit.assert_called_once()

    def test_create_duplicate_name_raises(self, mock_uow, provider_config_factory):
        """重名必须在写库之前拦下来（否则数据库唯一约束会变成 500）。"""
        existing = provider_config_factory(name="new-cfg")
        service = ProviderService(uow=mock_uow)
        with patch.object(ProviderConfigRepository, "get_by_name", return_value=existing):
            with pytest.raises(ProviderNameConflictError, match="new-cfg"):
                service.create(
                    {
                        "name": "new-cfg",
                        "api_mode": ApiMode.OPENAI_COMPAT,
                        "api_key": "sk-new",
                        "api_host": "https://api.new.com",
                        "model_id": "new-model",
                        "display_name": "New",
                    }
                )
        mock_uow.commit.assert_not_called()

    def test_get_by_id(self, mock_uow, provider_config_factory):
        with patch.object(
            ProviderConfigRepository,
            "get_by_id",
            return_value=provider_config_factory(),
        ):
            assert ProviderService(uow=mock_uow).get_by_id("some-id").name == "test-cfg"

    def test_get_by_id_returns_none(self, mock_uow):
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=None):
            assert ProviderService(uow=mock_uow).get_by_id("missing") is None

    def test_list_all(self, mock_uow, provider_config_factory):
        with patch.object(
            ProviderConfigRepository,
            "list_all",
            return_value=[provider_config_factory()],
        ):
            assert len(ProviderService(uow=mock_uow).list_all()) == 1

    def test_delete(self, mock_uow, provider_config_factory):
        with patch.object(
            ProviderConfigRepository,
            "get_by_id",
            return_value=provider_config_factory(),
        ):
            with patch.object(ProviderConfigRepository, "delete", return_value=True):
                assert ProviderService(uow=mock_uow).delete("some-id") is True

    def test_delete_nonexistent(self, mock_uow):
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=None):
            assert ProviderService(uow=mock_uow).delete("missing") is False

    @patch("app.services.provider_service.ProviderRegistry")
    def test_activate(self, MockRegistry, mock_uow, provider_config_factory):
        config = provider_config_factory(name="to-activate")
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "save"):
                with patch.object(ProviderConfigRepository, "deactivate_all"):
                    result = ProviderService(uow=mock_uow).activate("some-id")
                    assert result.is_active is True
                    MockRegistry.activate.assert_called_once_with(config)

    @patch("app.services.provider_service.ProviderRegistry")
    def test_activate_nonexistent(self, MockRegistry, mock_uow):
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=None):
            assert ProviderService(uow=mock_uow).activate("missing") is None
            MockRegistry.activate.assert_not_called()

    def test_update(self, mock_uow, provider_config_factory):
        config = provider_config_factory(name="original")
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            # 改名时才会查重；查出来没人占用
            with patch.object(ProviderConfigRepository, "get_by_name", return_value=None):
                with patch.object(ProviderConfigRepository, "save"):
                    result = ProviderService(uow=mock_uow).update(
                        config.id, {"name": "updated"}
                    )
                    assert result.name == "updated"
                    mock_uow.commit.assert_called_once()

    def test_update_to_taken_name_raises(self, mock_uow, provider_config_factory):
        """改名撞上别人的名字：抛冲突，不落库。"""
        config = provider_config_factory(name="original")
        other = provider_config_factory(name="taken")
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "get_by_name", return_value=other):
                with pytest.raises(ProviderNameConflictError, match="taken"):
                    ProviderService(uow=mock_uow).update(config.id, {"name": "taken"})
        mock_uow.commit.assert_not_called()

    def test_update_keeping_own_name_is_not_a_conflict(self, mock_uow, provider_config_factory):
        """改成自己原来的名字（大小写/内容相同）不该算冲突。"""
        config = provider_config_factory(name="original")
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "get_by_name", return_value=config):
                with patch.object(ProviderConfigRepository, "save"):
                    result = ProviderService(uow=mock_uow).update(
                        config.id, {"name": "original", "display_name": "Renamed"}
                    )
        assert result.display_name == "Renamed"

    def test_update_nonexistent(self, mock_uow):
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=None):
            assert ProviderService(uow=mock_uow).update("missing", {"name": "nope"}) is None

    @patch("app.services.provider_service.ProviderRegistry")
    def test_update_reactivates_when_active(
        self, MockRegistry, mock_uow, provider_config_factory
    ):
        config = provider_config_factory(name="active-cfg", is_active=True)
        MockRegistry.get_active_config.return_value = config
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "save"):
                result = ProviderService(uow=mock_uow).update(
                    config.id, {"display_name": "Updated"}
                )
                assert result.display_name == "Updated"
                MockRegistry.activate.assert_called_once_with(config)

    def test_get_active(self, mock_uow, provider_config_factory):
        config = provider_config_factory(is_active=True)
        with patch.object(ProviderConfigRepository, "get_active", return_value=config):
            assert ProviderService(uow=mock_uow).get_active().is_active is True

    def test_get_active_returns_none(self, mock_uow):
        with patch.object(ProviderConfigRepository, "get_active", return_value=None):
            assert ProviderService(uow=mock_uow).get_active() is None

    @patch("app.services.provider_service.ProviderRegistry")
    def test_delete_active_clears_registry(
        self, MockRegistry, mock_uow, provider_config_factory
    ):
        config = provider_config_factory(is_active=True)
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "delete", return_value=True):
                assert ProviderService(uow=mock_uow).delete("active-id") is True
                MockRegistry.clear.assert_called_once()

    def test_delete_inactive_does_not_clear_registry(
        self, mock_uow, provider_config_factory
    ):
        config = provider_config_factory(is_active=False)
        with patch.object(ProviderConfigRepository, "get_by_id", return_value=config):
            with patch.object(ProviderConfigRepository, "delete", return_value=True):
                assert ProviderService(uow=mock_uow).delete("inactive-id") is True
