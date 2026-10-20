"""Descarga y consulta de datasets públicos de IMDb (https://datasets.imdbws.com/).

Licencia: uso no comercial / condiciones de IMDb datasets. No redistribuimos
los ficheros completos; solo se cachean localmente para el análisis.
"""

from __future__ import annotations

import gzip
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen

from letterboxd_wrapped.normalization import normalize_title

logger = logging.getLogger(__name__)

IMDB_BASE = "https://datasets.imdbws.com"
NEEDED_FILES = (
    "title.basics.tsv.gz",
    "title.akas.tsv.gz",
    "title.crew.tsv.gz",
    "title.principals.tsv.gz",
    "name.basics.tsv.gz",
)

# Tipos de título relevantes para cine
MOVIE_TYPES = {"movie", "tvMovie", "short", "tvShort", "video"}


class ImdbDatasets:
    def __init__(self, data_dir: str | Path, *, offline: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self._basics_index: dict[tuple[str, int], list[dict[str, Any]]] | None = None
        self._basics_by_id: dict[str, dict[str, Any]] | None = None

    def ensure_files(self, files: Iterable[str] = NEEDED_FILES) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for name in files:
            path = self.data_dir / name
            if path.exists() and path.stat().st_size > 0:
                paths[name] = path
                continue
            if self.offline:
                logger.warning("Modo offline: falta %s", name)
                continue
            self._download(name, path)
            if path.exists():
                paths[name] = path
        return paths

    def _download(self, name: str, dest: Path) -> None:
        url = f"{IMDB_BASE}/{name}"
        logger.info("Descargando %s …", url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; letterboxd-wrapped/1.0; local analysis)"
            },
        )
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                with urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                tmp.replace(dest)
                logger.info("Descargado %s (%.1f MB)", name, dest.stat().st_size / 1e6)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Intento %d/%d fallido para %s: %s", attempt, retries, name, exc)
                time.sleep(2 * attempt)
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
        logger.error("No se pudo descargar %s", name)

    def load_basics_index(self) -> None:
        if self._basics_index is not None:
            return
        paths = self.ensure_files(["title.basics.tsv.gz"])
        path = paths.get("title.basics.tsv.gz")
        if not path:
            self._basics_index = {}
            self._basics_by_id = {}
            return

        index: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
        by_id: dict[str, dict[str, Any]] = {}
        logger.info("Indexando title.basics …")
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                title_type = parts[col["titleType"]]
                if title_type not in MOVIE_TYPES:
                    continue
                start = parts[col["startYear"]]
                if start == "\\N":
                    continue
                try:
                    year = int(start)
                except ValueError:
                    continue
                tconst = parts[col["tconst"]]
                primary = parts[col["primaryTitle"]]
                original = parts[col["originalTitle"]]
                runtime = parts[col["runtimeMinutes"]]
                genres = parts[col["genres"]]
                record = {
                    "tconst": tconst,
                    "titleType": title_type,
                    "primaryTitle": primary,
                    "originalTitle": original,
                    "startYear": year,
                    "runtimeMinutes": int(runtime) if runtime not in {"\\N", ""} else None,
                    "genres": [g for g in genres.split(",") if g and g != "\\N"]
                    if genres != "\\N"
                    else [],
                    "isAdult": parts[col["isAdult"]] == "1",
                }
                by_id[tconst] = record
                by_year[year].append(record)
                titles = {primary, original}
                # Subtítulos tras " - " / ": " (p.ej. Return of the Jedi).
                # Solo si son suficientemente específicos (>= 10 chars normalizados).
                for title in list(titles):
                    for sep in (" - ", ": "):
                        if sep in title:
                            sub = title.split(sep)[-1].strip()
                            if len(normalize_title(sub)) >= 10:
                                titles.add(sub)
                for title in titles:
                    key = (normalize_title(title), year)
                    if key[0] and len(key[0]) >= 3:
                        index[key].append(record)
        self._basics_index = dict(index)
        self._basics_by_year = dict(by_year)
        self._basics_by_id = by_id
        logger.info("Índice IMDb: %d títulos, %d claves", len(by_id), len(self._basics_index))

    def lookup(self, title: str, year: int | None) -> list[dict[str, Any]]:
        self.load_basics_index()
        assert self._basics_index is not None
        if year is None:
            return []
        key = (normalize_title(title), year)
        hits = list(self._basics_index.get(key, []))
        if hits:
            return hits
        # Fallback robusto (mismo año, preferentemente movie):
        # 1) subtítulo indexado / subcadena
        # 2) todos los tokens significativos del query ⊆ título candidato
        # 3) token_sort_ratio alto (Philosopher's vs Sorcerer's Stone)
        from rapidfuzz import fuzz

        norm = normalize_title(title)
        if len(norm) < 6:
            return []
        stop = {"the", "a", "an", "of", "and", "or", "la", "el", "los", "las", "de"}
        target_tokens = {t for t in norm.split() if t not in stop and len(t) > 1}
        year_pool = getattr(self, "_basics_by_year", {}).get(year, [])
        extra: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in year_pool:
            if rec.get("titleType") not in {"movie", "tvMovie"}:
                continue
            for field in ("primaryTitle", "originalTitle"):
                cand = normalize_title(rec.get(field, ""))
                if len(cand) < 6:
                    continue
                cand_tokens = {t for t in cand.split() if t not in stop and len(t) > 1}
                ok = False
                if norm in cand:
                    ok = True
                elif target_tokens and target_tokens.issubset(cand_tokens):
                    ok = True
                elif len(target_tokens) >= 3 and fuzz.token_set_ratio(norm, cand) >= 85:
                    ok = True
                elif (
                    len(target_tokens) >= 4
                    and len(target_tokens & cand_tokens) / len(target_tokens) >= 0.75
                ):
                    # p.ej. Philosopher's Stone vs Sorcerer's Stone
                    ok = True
                if ok and rec["tconst"] not in seen:
                    seen.add(rec["tconst"])
                    extra.append(rec)
                    break
        return extra

    def get_by_id(self, tconst: str) -> dict[str, Any] | None:
        self.load_basics_index()
        assert self._basics_by_id is not None
        return self._basics_by_id.get(tconst)

    def load_akas_for(self, tconsts: set[str]) -> dict[str, dict[str, str]]:
        """Devuelve {tconst: {region: title}} priorizando ES/ES-ES."""
        paths = self.ensure_files(["title.akas.tsv.gz"])
        path = paths.get("title.akas.tsv.gz")
        result: dict[str, dict[str, str]] = defaultdict(dict)
        if not path or not tconsts:
            return {}
        logger.info("Extrayendo akas para %d títulos …", len(tconsts))
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                tid = parts[col["titleId"]]
                if tid not in tconsts:
                    continue
                region = parts[col["region"]]
                title = parts[col["title"]]
                if region in {"ES", "XWW", "US", "GB"} and title and title != "\\N":
                    result[tid][region] = title
        return dict(result)

    def load_crew_for(self, tconsts: set[str]) -> dict[str, dict[str, list[str]]]:
        paths = self.ensure_files(["title.crew.tsv.gz"])
        path = paths.get("title.crew.tsv.gz")
        result: dict[str, dict[str, list[str]]] = {}
        if not path or not tconsts:
            return result
        logger.info("Extrayendo crew para %d títulos …", len(tconsts))
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                tid = parts[col["tconst"]]
                if tid not in tconsts:
                    continue
                directors = parts[col["directors"]]
                writers = parts[col["writers"]]
                result[tid] = {
                    "directors": [] if directors == "\\N" else directors.split(","),
                    "writers": [] if writers == "\\N" else writers.split(","),
                }
        return result

    def load_principals_for(
        self, tconsts: set[str], *, max_cast: int = 15
    ) -> dict[str, list[dict[str, Any]]]:
        paths = self.ensure_files(["title.principals.tsv.gz"])
        path = paths.get("title.principals.tsv.gz")
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if not path or not tconsts:
            return {}
        logger.info("Extrayendo principals para %d títulos …", len(tconsts))
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                tid = parts[col["tconst"]]
                if tid not in tconsts:
                    continue
                category = parts[col["category"]]
                if category not in {"actor", "actress", "self", "director", "writer"}:
                    continue
                try:
                    ordering = int(parts[col["ordering"]])
                except ValueError:
                    ordering = 99
                job = parts[col["job"]]
                result[tid].append(
                    {
                        "nconst": parts[col["nconst"]],
                        "category": category,
                        "ordering": ordering,
                        "job": None if job == "\\N" else job,
                    }
                )
        # Limitar elenco por película
        trimmed: dict[str, list[dict[str, Any]]] = {}
        for tid, people in result.items():
            people_sorted = sorted(people, key=lambda p: p["ordering"])
            cast = [p for p in people_sorted if p["category"] in {"actor", "actress", "self"}][
                :max_cast
            ]
            crew = [p for p in people_sorted if p["category"] in {"director", "writer"}]
            trimmed[tid] = cast + crew
        return trimmed

    def load_names(self, nconsts: set[str]) -> dict[str, str]:
        paths = self.ensure_files(["name.basics.tsv.gz"])
        path = paths.get("name.basics.tsv.gz")
        names: dict[str, str] = {}
        if not path or not nconsts:
            return names
        logger.info("Extrayendo nombres para %d personas …", len(nconsts))
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                nid = parts[col["nconst"]]
                if nid in nconsts:
                    names[nid] = parts[col["primaryName"]]
                    if len(names) >= len(nconsts):
                        break
        return names
