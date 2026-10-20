"""Enriquecimiento opcional vía Wikidata SPARQL (países y colecciones).

API pública documentada: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
Uso respetuoso con User-Agent identificable y lotes limitados.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "letterboxd-wrapped/1.0 (local cinephile stats; contact: local-user)"


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_countries_and_collections(
    imdb_ids: list[str],
    *,
    offline: bool = False,
    batch_size: int = 40,
) -> dict[str, dict[str, Any]]:
    """Devuelve {imdb_id: {countries: [...], collection: str|None}}."""
    if offline or not imdb_ids:
        return {}

    out: dict[str, dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})

    for batch in _chunked(sorted(set(imdb_ids)), batch_size):
        values = " ".join(f'"{iid}"' for iid in batch)
        query = f"""
        SELECT ?imdb ?countryLabel ?collectionLabel WHERE {{
          ?item wdt:P345 ?imdb .
          VALUES ?imdb {{ {values} }}
          OPTIONAL {{ ?item wdt:P495 ?country. }}
          OPTIONAL {{ ?item wdt:P179 ?collection. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es,en". }}
        }}
        """
        try:
            resp = session.get(SPARQL_URL, params={"query": query}, timeout=60)
            if resp.status_code == 429:
                logger.warning("Wikidata rate limit; esperando…")
                time.sleep(5)
                resp = session.get(SPARQL_URL, params={"query": query}, timeout=60)
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])
            for row in bindings:
                imdb = row.get("imdb", {}).get("value")
                if not imdb:
                    continue
                entry = out.setdefault(imdb, {"countries": [], "collection": None})
                country = row.get("countryLabel", {}).get("value")
                if country and country not in entry["countries"]:
                    entry["countries"].append(country)
                collection = row.get("collectionLabel", {}).get("value")
                if collection and not entry["collection"]:
                    entry["collection"] = collection
            time.sleep(0.4)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Wikidata batch falló (%d ids): %s", len(batch), exc)
            continue
    logger.info("Wikidata: metadatos para %d/%d títulos", len(out), len(set(imdb_ids)))
    return out
