"""Orquesta matching IMDb + crew/cast + Wikidata/TMDB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from letterboxd_wrapped.matching import match_films
from letterboxd_wrapped.metadata.cache import MetadataCache
from letterboxd_wrapped.metadata.imdb import ImdbDatasets
from letterboxd_wrapped.metadata.tmdb import TmdbClient
from letterboxd_wrapped.metadata.wikidata import fetch_countries_and_collections
from letterboxd_wrapped.models import FilmRecord

logger = logging.getLogger(__name__)


def _person(nconst: str, name: str, category: str, job: str | None = None) -> dict[str, Any]:
    return {"id": nconst, "name": name, "category": category, "job": job}


def enrich_films(
    films: list[FilmRecord],
    *,
    cache_dir: str | Path,
    imdb_dir: str | Path,
    offline: bool = False,
    force: bool = False,
    limit: int | None = None,
    use_wikidata: bool = True,
    tmdb_api_key: str | None = None,
) -> dict[str, Any]:
    cache = MetadataCache(cache_dir)
    imdb = ImdbDatasets(imdb_dir, offline=offline)
    tmdb = TmdbClient(tmdb_api_key, offline=offline)

    coverage = {
        "total_films": len(films[:limit] if limit else films),
        "matched_confirmed": 0,
        "matched_probable": 0,
        "unmatched": 0,
        "conflict": 0,
        "with_cast": 0,
        "with_directors": 0,
        "with_countries": 0,
        "with_collection": 0,
        "with_genres": 0,
        "sources": {
            "imdb": False,
            "wikidata": False,
            "tmdb": tmdb.enabled,
        },
        "pending": [],
        "omissions": [],
    }

    # 1) Matching
    try:
        imdb.ensure_files(["title.basics.tsv.gz"])
        coverage["sources"]["imdb"] = (Path(imdb_dir) / "title.basics.tsv.gz").exists()
    except Exception as exc:  # noqa: BLE001
        coverage["omissions"].append(f"IMDb basics no disponible: {exc}")

    matches = match_films(films, imdb, cache, force=force, limit=limit)
    for m in matches:
        st = m["status"]
        if st == "confirmed":
            coverage["matched_confirmed"] += 1
        elif st == "probable":
            coverage["matched_probable"] += 1
        elif st == "conflict":
            coverage["conflict"] += 1
            coverage["pending"].append(m)
        else:
            coverage["unmatched"] += 1
            coverage["pending"].append(m)

    subset = films[:limit] if limit else films
    matched_ids = {f.imdb_id for f in subset if f.imdb_id}
    if not matched_ids:
        cache.save()
        coverage["omissions"].append("Sin coincidencias IMDb; rankings de personas omitidos.")
        return coverage

    # Reutilizar caché completa si todas las películas matched ya tienen metadatos
    need_fetch = force or any(
        not (cache.get_film(f.key) and cache.get_film(f.key).get("imdb_id") == f.imdb_id)
        for f in subset
        if f.imdb_id
    )

    akas: dict[str, dict[str, str]] = {}
    crew_map: dict[str, dict[str, list[str]]] = {}
    principals: dict[str, list[dict[str, Any]]] = {}
    names: dict[str, str] = {}
    wd: dict[str, dict[str, Any]] = {}

    if need_fetch:
        # 2) Metadatos básicos + akas
        try:
            akas = imdb.load_akas_for(matched_ids)
        except Exception as exc:  # noqa: BLE001
            coverage["omissions"].append(f"IMDb akas: {exc}")

        try:
            crew_map = imdb.load_crew_for(matched_ids)
        except Exception as exc:  # noqa: BLE001
            coverage["omissions"].append(f"IMDb crew: {exc}")
        try:
            principals = imdb.load_principals_for(matched_ids)
        except Exception as exc:  # noqa: BLE001
            coverage["omissions"].append(f"IMDb principals: {exc}")

        nconsts: set[str] = set()
        for crew in crew_map.values():
            nconsts.update(crew.get("directors", []))
            nconsts.update(crew.get("writers", []))
        for plist in principals.values():
            for p in plist:
                nconsts.add(p["nconst"])

        try:
            names = imdb.load_names(nconsts)
        except Exception as exc:  # noqa: BLE001
            coverage["omissions"].append(f"IMDb names: {exc}")

        # 3) Wikidata países / colecciones
        if use_wikidata and not offline:
            try:
                wd = fetch_countries_and_collections(list(matched_ids), offline=offline)
                coverage["sources"]["wikidata"] = bool(wd)
            except Exception as exc:  # noqa: BLE001
                coverage["omissions"].append(f"Wikidata: {exc}")
    else:
        logger.info("Reutilizando caché de metadatos para %d películas", len(matched_ids))
        # Detectar si la caché ya trae países/colecciones
        if any((cache.get_film(f.key) or {}).get("countries") for f in subset if f.imdb_id):
            coverage["sources"]["wikidata"] = True

    # 4) Aplicar a FilmRecord (+ caché)
    for film in subset:
        if not film.imdb_id:
            continue
        cached = None if force else cache.get_film(film.key)
        if cached and cached.get("imdb_id") == film.imdb_id:
            _apply_cached(film, cached)
        else:
            basic = imdb.get_by_id(film.imdb_id) or {}
            aka = akas.get(film.imdb_id, {})
            film.original_title = basic.get("originalTitle")
            film.localized_title_es = aka.get("ES") or aka.get("XWW")
            film.runtime_minutes = basic.get("runtimeMinutes")
            film.genres = list(basic.get("genres") or [])
            film.title_type = basic.get("titleType")

            directors = []
            for nid in crew_map.get(film.imdb_id, {}).get("directors", []):
                if nid in names:
                    directors.append(_person(nid, names[nid], "director"))
            writers = []
            for nid in crew_map.get(film.imdb_id, {}).get("writers", []):
                if nid in names:
                    writers.append(_person(nid, names[nid], "writer"))

            actors, actresses, cast = [], [], []
            for p in principals.get(film.imdb_id, []):
                name = names.get(p["nconst"])
                if not name:
                    continue
                person = _person(p["nconst"], name, p["category"], p.get("job"))
                cast.append(person)
                if p["category"] == "actor":
                    actors.append(person)
                elif p["category"] == "actress":
                    actresses.append(person)

            film.directors = directors
            film.writers = writers
            film.actors = actors
            film.actresses = actresses
            film.cast = cast

            wd_entry = wd.get(film.imdb_id, {})
            film.countries = list(wd_entry.get("countries") or [])
            film.primary_country = film.countries[0] if film.countries else None
            film.collection = wd_entry.get("collection")

            # TMDB opcional: completar país/colección/idioma/tmdb_id
            if tmdb.enabled and (not film.countries or not film.collection):
                found = tmdb.find_by_imdb(film.imdb_id)
                if found:
                    film.tmdb_id = found.get("id")
                    details = tmdb.movie_details(film.tmdb_id) if film.tmdb_id else None
                    if details:
                        if not film.localized_title_es and details.get("title"):
                            film.localized_title_es = details["title"]
                        if not film.countries:
                            film.countries = [
                                c.get("name") for c in details.get("production_countries") or [] if c.get("name")
                            ]
                            film.primary_country = film.countries[0] if film.countries else None
                        if not film.collection and details.get("belongs_to_collection"):
                            film.collection = details["belongs_to_collection"].get("name")
                            film.collection_id = str(details["belongs_to_collection"].get("id"))
                        film.original_language = details.get("original_language")

            payload = {
                "imdb_id": film.imdb_id,
                "tmdb_id": film.tmdb_id,
                "original_title": film.original_title,
                "localized_title_es": film.localized_title_es,
                "runtime_minutes": film.runtime_minutes,
                "genres": film.genres,
                "title_type": film.title_type,
                "countries": film.countries,
                "primary_country": film.primary_country,
                "collection": film.collection,
                "collection_id": film.collection_id,
                "original_language": film.original_language,
                "directors": film.directors,
                "writers": film.writers,
                "actors": film.actors,
                "actresses": film.actresses,
                "cast": film.cast,
                "match_status": film.match_status,
                "match_confidence": film.match_confidence,
            }
            cache.set_film(film.key, payload)

        if film.genres:
            coverage["with_genres"] += 1
        if film.directors:
            coverage["with_directors"] += 1
        if film.actors or film.actresses:
            coverage["with_cast"] += 1
        if film.countries:
            coverage["with_countries"] += 1
        if film.collection:
            coverage["with_collection"] += 1

    cache.save()
    return coverage


def _apply_cached(film: FilmRecord, cached: dict[str, Any]) -> None:
    film.imdb_id = cached.get("imdb_id")
    film.tmdb_id = cached.get("tmdb_id")
    film.original_title = cached.get("original_title")
    film.localized_title_es = cached.get("localized_title_es")
    film.runtime_minutes = cached.get("runtime_minutes")
    film.genres = list(cached.get("genres") or [])
    film.title_type = cached.get("title_type")
    film.countries = list(cached.get("countries") or [])
    film.primary_country = cached.get("primary_country")
    film.collection = cached.get("collection")
    film.collection_id = cached.get("collection_id")
    film.original_language = cached.get("original_language")
    film.directors = list(cached.get("directors") or [])
    film.writers = list(cached.get("writers") or [])
    film.actors = list(cached.get("actors") or [])
    film.actresses = list(cached.get("actresses") or [])
    film.cast = list(cached.get("cast") or [])
    film.match_status = cached.get("match_status") or film.match_status
    film.match_confidence = cached.get("match_confidence")
