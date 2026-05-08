from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from ..domain.settings import AppSettings
from ..infra.storage.settings_repository import SettingsRepository


class SettingsService(QObject):
    settings_changed = Signal(object)   # emits AppSettings

    _instance: SettingsService | None = None

    @classmethod
    def instance(cls) -> SettingsService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._repo = SettingsRepository()
        self._current: AppSettings = self._repo.load()

    def get(self) -> AppSettings:
        return self._current

    def update(self, **kwargs) -> None:
        self._current = replace(self._current, **kwargs)
        self._repo.save(self._current)
        self.settings_changed.emit(self._current)
