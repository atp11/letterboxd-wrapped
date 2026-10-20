"""Pruebas de métricas principales."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from letterboxd_wrapped.importer import load_export
from letterboxd_wrapped.models import DiaryEntry, FilmRecord, LetterboxdExport
from letterboxd_wrapped.normalization import film_key, normalize_title, parse_rating
from letterboxd_wrapped.rankings import _person_rank
from letterboxd_wrapped.statistics import compute_basic_stats


def _film(name: str, year: int, rating: float | None = None, uri: str | None = None) -> FilmRecord:
    uri = uri or f"https://boxd.it/{name.replace(' ', '')}"
    return FilmRecord(
        key=film_key(name, year, uri),
        name=name,
        year=year,
        letterboxd_uri=uri,
        rating=rating,
    )


def test_parse_rating_scale():
    assert parse_rating("4.5") == 4.5
    assert parse_rating("5") == 5.0
    assert parse_rating(0.5) == 0.5
    assert parse_rating("") is None
    assert parse_rating("6") is None


def test_normalize_title():
    assert normalize_title("The Matrix") == normalize_title("the matrix")
    assert normalize_title("Amélie") == normalize_title("Amelie")


def test_basic_stats_means_only_rated():
    watched = [
        _film("A", 2000, 5),
        _film("B", 2001, 3),
        _film("C", 2002, None),
    ]
    export = LetterboxdExport(
        username="test",
        date_joined=None,
        watched=watched,
        ratings=[f for f in watched if f.rating is not None],
        diary=[],
        watchlist=[],
        likes=[],
    )
    stats = compute_basic_stats(export)
    assert stats["resumen"]["peliculas_vistas"] == 3
    assert stats["resumen"]["peliculas_puntuadas"] == 2
    assert stats["resumen"]["nota_media"] == 4.0
    assert stats["resumen"]["vistas_sin_puntuacion"] == 1


def test_person_rank_dedupes_same_film():
    f = _film("Inception", 2010, 5)
    f.actors = [
        {"id": "nm1", "name": "Leonardo DiCaprio", "category": "actor"},
        {"id": "nm1", "name": "Leonardo DiCaprio", "category": "actor"},  # crédito duplicado
    ]
    rows = _person_rank([f], lambda x: x.actors, catalog_size=1, top_n=5)
    assert len(rows) == 1
    assert rows[0]["films"] == 1


def test_rewatch_count():
    f = _film("X", 2010, 4)
    diary = [
        DiaryEntry(
            name="X",
            year=2010,
            letterboxd_uri=f.letterboxd_uri,
            film_key=f.key,
            logged_date=date(2020, 1, 1),
            watched_date=date(2019, 1, 1),
            rating=4,
            rewatch=False,
            tags="",
        ),
        DiaryEntry(
            name="X",
            year=2010,
            letterboxd_uri=f.letterboxd_uri,
            film_key=f.key,
            logged_date=date(2021, 1, 1),
            watched_date=date(2021, 1, 1),
            rating=4,
            rewatch=True,
            tags="",
        ),
    ]
    export = LetterboxdExport(
        username="t",
        date_joined=None,
        watched=[f],
        ratings=[f],
        diary=diary,
        watchlist=[],
        likes=[],
    )
    stats = compute_basic_stats(export)
    assert stats["resumen"]["revisionados"] == 1
    assert stats["resumen"]["entradas_diario"] == 2


def test_optional_local_zip_consistency():
    """Si hay un ZIP local (ignorado por git), comprueba consistencia básica.

    No fija totales personales en el repositorio: busca letterboxd-*.zip
    o la ruta en LETTERBOXD_TEST_ZIP.
    """
    import os

    env_zip = os.environ.get("LETTERBOXD_TEST_ZIP")
    candidates = [Path(env_zip)] if env_zip else sorted(Path(".").glob("letterboxd-*.zip"))
    zip_path = next((p for p in candidates if p and p.exists()), None)
    if zip_path is None:
        pytest.skip("Sin ZIP local de Letterboxd para prueba de integración")

    export = load_export(zip_path)
    stats = compute_basic_stats(export)["resumen"]
    assert stats["peliculas_vistas"] >= stats["peliculas_puntuadas"]
    assert stats["puntuadas_no_vistas"] == 0 or stats["puntuadas_no_vistas"] >= 0
    assert stats["entradas_diario"] >= stats["revisionados"]
    assert stats["watchlist"] >= 0
    if stats["peliculas_puntuadas"]:
        assert 0.5 <= stats["nota_media"] <= 5.0
        assert 0.5 <= stats["nota_mediana"] <= 5.0
        assert stats["count_4_5_o_5"] + stats["count_2_o_menos"] <= stats["peliculas_puntuadas"]
