"""Caché persistente en JSON/sqlite-lite (archivos JSON por clave)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MetadataCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._films_path = self.root / "films_metadata.json"
        self._matches_path = self.root / "matches.json"
        self.films: dict[str, dict[str, Any]] = self._load(self._films_path)
        self.matches: dict[str, dict[str, Any]] = self._load(self._matches_path)

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer caché %s: %s", path, exc)
            return {}

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._films_path.open("w", encoding="utf-8") as fh:
            json.dump(self.films, fh, ensure_ascii=False, indent=2)
        with self._matches_path.open("w", encoding="utf-8") as fh:
            json.dump(self.matches, fh, ensure_ascii=False, indent=2)

    def get_film(self, film_key: str) -> dict[str, Any] | None:
        return self.films.get(film_key)

    def set_film(self, film_key: str, data: dict[str, Any]) -> None:
        self.films[film_key] = data

    def get_match(self, film_key: str) -> dict[str, Any] | None:
        return self.matches.get(film_key)

    def set_match(self, film_key: str, data: dict[str, Any]) -> None:
        self.matches[film_key] = data
