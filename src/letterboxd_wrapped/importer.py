"""Importación de exportaciones ZIP de Letterboxd."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from pathlib import Path
from typing import Any

from letterboxd_wrapped.models import DiaryEntry, FilmRecord, LetterboxdExport
from letterboxd_wrapped.normalization import (
    film_key,
    parse_date,
    parse_rating,
    parse_year,
    safe_str,
)

logger = logging.getLogger(__name__)


def _read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
            reader = csv.DictReader(text)
            if not reader.fieldnames:
                return []
            rows: list[dict[str, str]] = []
            for raw in reader:
                row: dict[str, str] = {}
                for k, v in raw.items():
                    key = (k or "").strip()
                    if isinstance(v, list):
                        # CSV con columnas duplicadas: DictReader puede devolver listas
                        value = " ".join(str(x) for x in v if x is not None).strip()
                    else:
                        value = "" if v is None else str(v).strip()
                    row[key] = value
                rows.append(row)
            return rows
    except KeyError:
        logger.warning("CSV no encontrado en el ZIP: %s", name)
        return []


def _read_list_csv_from_zip(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    """Lee listas Letterboxd (cabecera de metadatos + bloque Position/Name/Year/URL)."""
    try:
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
            lines = text.read().splitlines()
    except KeyError:
        return []

    # Busca la fila de cabecera de ítems
    header_idx = None
    for i, line in enumerate(lines):
        lower = line.lower()
        if lower.startswith("position,") and "name" in lower and "year" in lower:
            header_idx = i
            break
    if header_idx is None:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = { (k or "").strip(): ("" if v is None else str(v).strip()) for k, v in raw.items() }
        # Homogeneiza URL → Letterboxd URI
        if not row.get("Letterboxd URI") and row.get("URL"):
            row["Letterboxd URI"] = row["URL"]
        rows.append(row)
    return rows


def _pick(row: dict[str, str], *candidates: str) -> str:
    lower_map = {k.lower(): v for k, v in row.items()}
    for cand in candidates:
        if cand in row and row[cand]:
            return row[cand]
        if cand.lower() in lower_map and lower_map[cand.lower()]:
            return lower_map[cand.lower()]
    return ""


def _film_from_row(row: dict[str, str], *, with_rating: bool = False) -> FilmRecord | None:
    name = safe_str(_pick(row, "Name", "Title", "Film"))
    uri = safe_str(_pick(row, "Letterboxd URI", "URI", "Url", "URL", "url"))
    year = parse_year(_pick(row, "Year", "Release Year"))
    if not name and not uri:
        return None
    rating = parse_rating(_pick(row, "Rating", "Stars")) if with_rating else None
    if with_rating and "Rating" not in {k for k in row} and rating is None:
        # Algunas exportaciones usan Rating solo si with_rating
        rating = parse_rating(_pick(row, "Rating"))
    return FilmRecord(
        key=film_key(name, year, uri or None),
        name=name or "(sin título)",
        year=year,
        letterboxd_uri=uri,
        date_added=parse_date(_pick(row, "Date", "Date Added")),
        rating=rating,
    )


def _dedupe_films(films: list[FilmRecord]) -> list[FilmRecord]:
    seen: dict[str, FilmRecord] = {}
    for film in films:
        existing = seen.get(film.key)
        if existing is None:
            seen[film.key] = film
            continue
        # Conserva rating si llega después; prefiere URI más completa
        if film.rating is not None and existing.rating is None:
            existing.rating = film.rating
        if film.letterboxd_uri and not existing.letterboxd_uri:
            existing.letterboxd_uri = film.letterboxd_uri
        if film.date_added and (existing.date_added is None or film.date_added > existing.date_added):
            existing.date_added = film.date_added
    return list(seen.values())


def load_export(zip_path: str | Path) -> LetterboxdExport:
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el ZIP: {path}")

    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        profile_rows = _read_csv_from_zip(zf, "profile.csv") if "profile.csv" in names else []
        username = "usuario"
        date_joined = None
        if profile_rows:
            username = safe_str(_pick(profile_rows[0], "Username")) or username
            date_joined = parse_date(_pick(profile_rows[0], "Date Joined"))

        watched_rows = _read_csv_from_zip(zf, "watched.csv")
        ratings_rows = _read_csv_from_zip(zf, "ratings.csv")
        diary_rows = _read_csv_from_zip(zf, "diary.csv")
        watchlist_rows = _read_csv_from_zip(zf, "watchlist.csv")
        likes_rows = _read_csv_from_zip(zf, "likes/films.csv") if "likes/films.csv" in names else []
        reviews_rows = _read_csv_from_zip(zf, "reviews.csv") if "reviews.csv" in names else []

        watched = _dedupe_films([f for r in watched_rows if (f := _film_from_row(r))])
        ratings = _dedupe_films(
            [f for r in ratings_rows if (f := _film_from_row(r, with_rating=True)) and f.rating is not None]
        )
        watchlist = _dedupe_films([f for r in watchlist_rows if (f := _film_from_row(r))])
        likes = _dedupe_films([f for r in likes_rows if (f := _film_from_row(r))])
        liked_keys = {f.key for f in likes}

        # Enlazar rating y like a películas vistas
        rating_map = {f.key: f.rating for f in ratings}
        for film in watched:
            film.rating = rating_map.get(film.key)
            film.liked = film.key in liked_keys

        diary: list[DiaryEntry] = []
        for row in diary_rows:
            name = safe_str(_pick(row, "Name", "Title", "Film"))
            uri = safe_str(_pick(row, "Letterboxd URI", "URI"))
            year = parse_year(_pick(row, "Year"))
            if not name and not uri:
                continue
            rewatch_raw = safe_str(_pick(row, "Rewatch", "Is Rewatch")).lower()
            rewatch = rewatch_raw in {"yes", "true", "1", "y", "sí", "si"}
            # La URI del diario apunta a la *entrada*, no a la película:
            # la identidad de film usa nombre+año (o URI de watched si existe).
            watched_match = next(
                (
                    w
                    for w in watched
                    if w.name == name and w.year == year
                ),
                None,
            )
            diary.append(
                DiaryEntry(
                    name=name or "(sin título)",
                    year=year,
                    letterboxd_uri=uri,
                    film_key=watched_match.key if watched_match else film_key(name, year, None),
                    logged_date=parse_date(_pick(row, "Date")),
                    watched_date=parse_date(_pick(row, "Watched Date", "WatchedDate")),
                    rating=parse_rating(_pick(row, "Rating")),
                    rewatch=rewatch,
                    tags=safe_str(_pick(row, "Tags")),
                )
            )

        lists: dict[str, list[FilmRecord]] = {}
        for member in zf.namelist():
            if member.startswith("lists/") and member.endswith(".csv"):
                list_name = Path(member).stem
                rows = _read_list_csv_from_zip(zf, member)
                lists[list_name] = _dedupe_films([f for r in rows if (f := _film_from_row(r))])

    export = LetterboxdExport(
        username=username,
        date_joined=date_joined,
        watched=watched,
        ratings=ratings,
        diary=diary,
        watchlist=watchlist,
        likes=likes,
        reviews_count=len(reviews_rows),
        lists=lists,
    )
    logger.info(
        "Exportación cargada: %s — %d vistas, %d puntuadas, %d diario, %d watchlist",
        username,
        len(export.watched),
        len(export.ratings),
        len(export.diary),
        len(export.watchlist),
    )
    return export


def export_summary(export: LetterboxdExport) -> dict[str, Any]:
    watched_keys = {f.key for f in export.watched}
    rated_keys = {f.key for f in export.ratings}
    return {
        "username": export.username,
        "watched": len(export.watched),
        "rated": len(export.ratings),
        "diary": len(export.diary),
        "rewatches": sum(1 for d in export.diary if d.rewatch),
        "watchlist": len(export.watchlist),
        "likes": len(export.likes),
        "rated_not_watched": len(rated_keys - watched_keys),
        "watched_not_rated": len(watched_keys - rated_keys),
    }
