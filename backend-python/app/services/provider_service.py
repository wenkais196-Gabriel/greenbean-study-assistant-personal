from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.entities.provider_config import ProviderConfig
from app.providers.registry import ProviderRegistry
from app.repositories.provider_config_repository import ProviderConfigRepository


class ProviderNameConflictError(ValueError):
    """同一个 `name` 只能有一份配置。

    数据库上本来就带着唯一约束，这里提前给出**可读**的错误，
    让 HTTP 层能回 409 而不是把 IntegrityError 变成 500。
    """


class ProviderService:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self.uow = uow

    def create(self, data: dict) -> ProviderConfig:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            name = data.get("name", "")
            if repo.get_by_name(name) is not None:
                raise ProviderNameConflictError(f"配置名已存在: {name}")

            config = ProviderConfig(**data)
            repo.save(config)
            uow.commit()
        return config

    def update(self, config_id: str, data: dict) -> ProviderConfig | None:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            config = repo.get_by_id(config_id)
            if config is None:
                return None

            new_name = data.get("name")
            if new_name is not None and new_name != config.name:
                existing = repo.get_by_name(new_name)
                if existing is not None and existing.id != config_id:
                    raise ProviderNameConflictError(f"配置名已存在: {new_name}")

            for key, value in data.items():
                if value is not None:
                    setattr(config, key, value)
            repo.save(config)
            uow.commit()

            if ProviderRegistry.get_active_config() and ProviderRegistry.get_active_config().id == config_id:
                ProviderRegistry.activate(config)
        return config

    def activate(self, config_id: str) -> ProviderConfig | None:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            config = repo.get_by_id(config_id)
            if config is None:
                return None
            repo.deactivate_all()
            config.is_active = True
            repo.save(config)
            uow.commit()

        ProviderRegistry.activate(config)
        return config

    def get_active(self) -> ProviderConfig | None:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            return repo.get_active()

    def restore_active(self) -> ProviderConfig | None:
        """把库里标记为"当前激活"的配置重新装进 `ProviderRegistry`。

        `ProviderRegistry` 是**进程内**单例：进程重启后它是空的，而
        `GET /api/providers/active` 读的是数据库 —— 两边会不一致
        （界面显示"已激活"，实际问答回 503）。启动时恢复一次即可对齐。
        """
        config = self.get_active()
        if config is not None:
            ProviderRegistry.activate(config)
        return config

    def get_by_id(self, config_id: str) -> ProviderConfig | None:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            return repo.get_by_id(config_id)

    def list_all(self) -> list[ProviderConfig]:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            return repo.list_all()

    def delete(self, config_id: str) -> bool:
        with self.uow as uow:
            repo = ProviderConfigRepository(uow.session)
            config = repo.get_by_id(config_id)
            if config is None:
                return False
            was_active = config.is_active
            result = repo.delete(config_id)
            uow.commit()

            if was_active:
                ProviderRegistry.clear()
        return result
