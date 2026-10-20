"""Integración opcional con TMDB API (requiere TMDB_API_KEY)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"


class TmdbClient:
    def __init__(self, api_key: str | None = None, *, offline: bool = False) -> None:
        self.api_key = api_key or os.environ.get("TMDB_API_KEY") or ""
        self.offline = offline
        self.enabled = bool(self.api_key) and not offline
        self._session = requests.Session()

    def find_by_imdb(self, imdb_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            resp = self._session.get(
                f"{TMDB_BASE}/find/{imdb_id}",
                params={"api_key": self.api_key, "external_source": "imdb_id"},
                timeout=30,
            )
            if resp.status_code == 429:
                time.sleep(2)
                resp = self._session.get(
                    f"{TMDB_BASE}/find/{imdb_id}",
                    params={"api_key": self.api_key, "external_source": "imdb_id"},
                    timeout=30,
                )
            resp.raise_for_status()
            data = resp.json()
            movies = data.get("movie_results") or []
            return movies[0] if movies else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("TMDB find %s: %s", imdb_id, exc)
            return None

    def movie_details(self, tmdb_id: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            resp = self._session.get(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                params={
                    "api_key": self.api_key,
                    "language": "es-ES",
                    "append_to_response": "credits",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("TMDB movie %s: %s", tmdb_id, exc)
            return None
