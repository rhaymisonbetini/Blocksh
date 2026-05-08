from __future__ import annotations

import json
from dataclasses import asdict, fields

from ...domain.settings import AppSettings
from ...infra.config.settings import SETTINGS_PATH

_DEFAULTS = {f.name: f.default for f in fields(AppSettings)}


class SettingsRepository:
    def load(self) -> AppSettings:
        try:
            data = json.loads(SETTINGS_PATH.read_text())
        except Exception:
            data = {}
        merged = {**_DEFAULTS, **{k: v for k, v in data.items() if k in _DEFAULTS}}
        return AppSettings(**merged)

    def save(self, s: AppSettings) -> None:
        try:
            SETTINGS_PATH.write_text(json.dumps(asdict(s), indent=2))
        except Exception:
            pass
