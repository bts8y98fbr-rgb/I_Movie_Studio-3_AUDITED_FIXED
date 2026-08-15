from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


class SettingsManager:
    def __init__(self, path: Path, defaults: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.defaults = dict(defaults or {})
        self._lock = RLock()
        self._settings: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if self.path.exists():
                self._settings = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._settings = dict(self.defaults)
                self.save()
            return dict(self._settings)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._settings[key] = value
            self.save()

    def update(self, values: dict[str, Any]) -> None:
        with self._lock:
            self._settings.update(values)
            self.save()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._settings)

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._settings, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
