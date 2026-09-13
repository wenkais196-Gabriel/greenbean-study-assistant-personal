"""
应用入口：启动时把"当前激活的模型"恢复到 `ProviderRegistry`。

`ProviderRegistry` 是进程内单例 —— 进程重启后它为空，而界面读的是数据库，
两边不一致会让问答莫名其妙回 503。启动钩子负责对齐这两者。
"""
from fastapi.testclient import TestClient

from app.main import app, restore_active_provider


def test_restore_active_provider_delegates_to_service(monkeypatch):
    """恢复动作交给 `ProviderService.restore_active()`；会话工厂懒加载（不建库）。"""
    calls: list[str] = []

    class FakeService:
        def __init__(self, _uow):
            calls.append("init")

        def restore_active(self):
            calls.append("restore")

    monkeypatch.setattr("app.main.ProviderService", FakeService)

    restore_active_provider()

    assert calls == ["init", "restore"]


def test_app_startup_restores_active_provider(monkeypatch):
    """启动事件触发一次恢复 —— 用户不必在重启后再点一次"激活"。"""
    calls: list[str] = []
    monkeypatch.setattr("app.main.restore_active_provider", lambda: calls.append("restore"))

    with TestClient(app):
        pass

    assert calls == ["restore"]
