"""Modelos de datos del análisis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class FilmRecord:
    key: str
    name: str
    year: int | None
    letterboxd_uri: str
    date_added: date | None = None
    rating: float | None = None
    liked: bool = False
    # Metadatos externos (rellenados tras matching)
    imdb_id: str | None = None
    tmdb_id: int | None = None
    original_title: str | None = None
    localized_title_es: str | None = None
    match_confidence: float | None = None
    match_status: str = "unmatched"  # confirmed | probable | unmatched | conflict
    runtime_minutes: int | None = None
    genres: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    primary_country: str | None = None
    original_language: str | None = None
    title_type: str | None = None  # movie, short, documentary, tvMovie, etc.
    collection: str | None = None
    collection_id: str | None = None
    directors: list[dict[str, Any]] = field(default_factory=list)
    writers: list[dict[str, Any]] = field(default_factory=list)
    actors: list[dict[str, Any]] = field(default_factory=list)
    actresses: list[dict[str, Any]] = field(default_factory=list)
    cast: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiaryEntry:
    name: str
    year: int | None
    letterboxd_uri: str
    film_key: str
    logged_date: date | None
    watched_date: date | None
    rating: float | None
    rewatch: bool
    tags: str


@dataclass
class LetterboxdExport:
    username: str
    date_joined: date | None
    watched: list[FilmRecord]
    ratings: list[FilmRecord]
    diary: list[DiaryEntry]
    watchlist: list[FilmRecord]
    likes: list[FilmRecord]
    reviews_count: int = 0
    lists: dict[str, list[FilmRecord]] = field(default_factory=dict)

    @property
    def watched_by_key(self) -> dict[str, FilmRecord]:
        return {f.key: f for f in self.watched}

    @property
    def ratings_by_key(self) -> dict[str, float]:
        return {f.key: f.rating for f in self.ratings if f.rating is not None}
