"""Resolución de títulos Letterboxd ↔ IMDb."""

from __future__ import annotations

import logging
from typing import Any

from rapidfuzz import fuzz

from letterboxd_wrapped.metadata.cache import MetadataCache
from letterboxd_wrapped.metadata.imdb import ImdbDatasets
from letterboxd_wrapped.models import FilmRecord
from letterboxd_wrapped.normalization import normalize_title

logger = logging.getLogger(__name__)

CONFIRMED_THRESHOLD = 95.0
PROBABLE_THRESHOLD = 85.0


def _score_candidate(film: FilmRecord, candidate: dict[str, Any]) -> float:
    target = normalize_title(film.name)
    primary = normalize_title(candidate.get("primaryTitle", ""))
    original = normalize_title(candidate.get("originalTitle", ""))

    scores: list[float] = []
    # Coincidencia exacta del título primario vale más que solo originalTitle
    # (evita RiffTrax/parodias que reutilizan originalTitle).
    if primary == target:
        scores.append(100.0)
    elif original == target and primary != target:
        # original igual pero primary distinto → sospechoso
        if target in primary and primary != target:
            scores.append(88.0)
        else:
            scores.append(93.0)
    else:
        stop = {"the", "a", "an", "of", "and", "or", "la", "el", "los", "las", "de"}
        target_tokens = {t for t in target.split() if t not in stop and len(t) > 1}
        for cand in (primary, original):
            if not cand or len(cand) < 3:
                continue
            scores.append(float(fuzz.token_sort_ratio(target, cand)))
            scores.append(float(fuzz.token_set_ratio(target, cand)))
            if len(target) >= 8 and target in cand:
                scores.append(97.0)
            cand_tokens = {t for t in cand.split() if t not in stop and len(t) > 1}
            if target_tokens and target_tokens.issubset(cand_tokens) and len(target_tokens) >= 3:
                scores.append(96.0)
            elif (
                len(target_tokens) >= 4
                and cand_tokens
                and len(target_tokens & cand_tokens) / len(target_tokens) >= 0.75
            ):
                scores.append(91.0)

    if not scores:
        return 0.0
    score = max(scores)
    if candidate.get("titleType") == "movie":
        score += 1.0
    elif candidate.get("titleType") in {"short", "tvShort", "video"}:
        score -= 5.0
    if candidate.get("isAdult"):
        score -= 8
    # Penalizar parodias / rifftrax / fan edits / presentaciones IMAX evidentes
    primary_raw = (candidate.get("primaryTitle") or "").lower()
    for bad in ("rifftrax", "imax", "presents:", "fan cut", "recut", "road to "):
        if bad in primary_raw and bad not in (film.name or "").lower():
            score -= 20
    return max(0.0, min(score, 100.0))


def match_film(film: FilmRecord, imdb: ImdbDatasets) -> dict[str, Any]:
    """Devuelve dict con status, confidence, imdb_id y candidatos."""
    if film.year is None:
        return {
            "status": "unmatched",
            "confidence": 0.0,
            "imdb_id": None,
            "reason": "sin_año",
            "candidates": [],
        }

    candidates = imdb.lookup(film.name, film.year)
    # También probar variaciones mínimas (artículos)
    if not candidates:
        for prefix in ("the ", "a ", "an ", "el ", "la ", "los ", "las "):
            alt = film.name
            if normalize_title(alt).startswith(prefix.strip()):
                continue
            candidates = imdb.lookup(f"{prefix}{film.name}", film.year)
            if candidates:
                break

    if not candidates:
        return {
            "status": "unmatched",
            "confidence": 0.0,
            "imdb_id": None,
            "reason": "sin_candidatos",
            "candidates": [],
        }

    scored = []
    seen: set[str] = set()
    for cand in candidates:
        tid = cand["tconst"]
        if tid in seen:
            continue
        seen.add(tid)
        scored.append((_score_candidate(film, cand), cand))

    # Desempate: movie > tvMovie > short; cobertura de tokens; duración
    type_rank = {"movie": 0, "tvMovie": 1, "short": 2, "tvShort": 3, "video": 4}
    target = normalize_title(film.name)
    stop = {"the", "a", "an", "of", "and", "or", "la", "el", "los", "las", "de"}
    target_tokens = {t for t in target.split() if t not in stop and len(t) > 1}

    def sort_key(item: tuple[float, dict[str, Any]]) -> tuple:
        score, cand = item
        runtime = cand.get("runtimeMinutes") or 0
        primary = normalize_title(cand.get("primaryTitle", ""))
        cand_tokens = {t for t in primary.split() if t not in stop and len(t) > 1}
        coverage = (
            len(target_tokens & cand_tokens) / len(target_tokens) if target_tokens else 0.0
        )
        set_ratio = float(fuzz.token_set_ratio(target, primary)) if primary else 0.0
        return (
            -score,
            type_rank.get(cand.get("titleType", ""), 9),
            -coverage,
            -set_ratio,
            -runtime,
            cand["tconst"],
        )

    scored.sort(key=sort_key)

    best_score, best = scored[0]
    # Conflicto solo si hay empate real tras desempates (misma puntuación, tipo y
    # duración similar). Si la duración difiere claramente, se elige el más largo.
    conflict = False
    if len(scored) > 1 and scored[1][0] >= PROBABLE_THRESHOLD:
        second_score, second = scored[1]
        same_tier = type_rank.get(best.get("titleType", ""), 9) == type_rank.get(
            second.get("titleType", ""), 9
        )
        rt1 = best.get("runtimeMinutes") or 0
        rt2 = second.get("runtimeMinutes") or 0
        runtime_clear = abs(rt1 - rt2) >= 5
        if same_tier and abs(best_score - second_score) < 1.0 and not runtime_clear:
            conflict = True

    if conflict:
        status = "conflict"
        imdb_id = None
    elif best_score >= CONFIRMED_THRESHOLD:
        status = "confirmed"
        imdb_id = best["tconst"]
    elif best_score >= PROBABLE_THRESHOLD:
        status = "probable"
        imdb_id = best["tconst"]
    else:
        status = "unmatched"
        imdb_id = None

    return {
        "status": status,
        "confidence": round(best_score, 2),
        "imdb_id": imdb_id,
        "reason": "ok" if imdb_id else status,
        "candidates": [
            {
                "imdb_id": c["tconst"],
                "primaryTitle": c["primaryTitle"],
                "originalTitle": c["originalTitle"],
                "year": c["startYear"],
                "type": c["titleType"],
                "score": round(s, 2),
            }
            for s, c in scored[:5]
        ],
    }


def match_films(
    films: list[FilmRecord],
    imdb: ImdbDatasets,
    cache: MetadataCache,
    *,
    force: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    subset = films[:limit] if limit else films
    for film in subset:
        cached = cache.get_match(film.key) if not force else None
        if cached and cached.get("status") in {"confirmed", "probable", "unmatched", "conflict"}:
            match = cached
        else:
            match = match_film(film, imdb)
            cache.set_match(film.key, match)

        film.match_status = match["status"]
        film.match_confidence = match.get("confidence")
        film.imdb_id = match.get("imdb_id")
        results.append({"film_key": film.key, "name": film.name, "year": film.year, **match})
    return results
