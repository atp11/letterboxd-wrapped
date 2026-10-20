"""Estadísticas básicas del perfil Letterboxd."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd

from letterboxd_wrapped.models import FilmRecord, LetterboxdExport
from letterboxd_wrapped.normalization import decade_of


RATING_STEPS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


def _rated_films(export: LetterboxdExport) -> list[FilmRecord]:
    return [f for f in export.watched if f.rating is not None]


def compute_basic_stats(export: LetterboxdExport) -> dict[str, Any]:
    watched = export.watched
    ratings = [f.rating for f in watched if f.rating is not None]
    rated_keys = {f.key for f in export.ratings}
    watched_keys = {f.key for f in watched}
    watched_not_rated = [f for f in watched if f.rating is None]
    rated_not_watched = [f for f in export.ratings if f.key not in watched_keys]

    series = pd.Series(ratings, dtype="float64") if ratings else pd.Series(dtype="float64")
    dist = Counter(ratings)
    rating_distribution = [{"rating": r, "count": int(dist.get(r, 0))} for r in RATING_STEPS]

    n_rated = len(ratings)
    pct = lambda n: round(100.0 * n / n_rated, 2) if n_rated else 0.0

    # Décadas / años de estreno (sobre vistas)
    decade_counts: Counter[str] = Counter()
    year_counts: Counter[int] = Counter()
    decade_ratings: dict[str, list[float]] = defaultdict(list)
    year_ratings: dict[int, list[float]] = defaultdict(list)

    for film in watched:
        if film.year is not None:
            year_counts[film.year] += 1
            dec = decade_of(film.year)
            if dec:
                decade_counts[dec] += 1
                if film.rating is not None:
                    decade_ratings[dec].append(film.rating)
            if film.rating is not None:
                year_ratings[film.year].append(film.rating)

    decades_table = []
    for dec in sorted(decade_counts.keys()):
        rs = decade_ratings.get(dec, [])
        decades_table.append(
            {
                "decade": dec,
                "films": decade_counts[dec],
                "rated": len(rs),
                "avg_rating": round(sum(rs) / len(rs), 3) if rs else None,
            }
        )

    years_table = []
    for year, count in year_counts.most_common():
        rs = year_ratings.get(year, [])
        years_table.append(
            {
                "year": year,
                "films": count,
                "rated": len(rs),
                "avg_rating": round(sum(rs) / len(rs), 3) if rs else None,
            }
        )

    # Mejor década por nota (mínimo 5 puntuadas)
    best_decade = None
    best_decade_avg = -1.0
    for row in decades_table:
        if row["rated"] >= 5 and row["avg_rating"] is not None and row["avg_rating"] > best_decade_avg:
            best_decade_avg = row["avg_rating"]
            best_decade = row

    top_rated = sorted(
        [f for f in watched if f.rating is not None],
        key=lambda f: (-(f.rating or 0), f.name),
    )
    worst_rated = sorted(
        [f for f in watched if f.rating is not None],
        key=lambda f: ((f.rating or 0), f.name),
    )

    # Diario
    diary_by_year: Counter[int] = Counter()
    diary_by_month: Counter[str] = Counter()
    rewatch_count = 0
    film_diary_counts: Counter[str] = Counter()
    for entry in export.diary:
        if entry.logged_date:
            diary_by_year[entry.logged_date.year] += 1
            diary_by_month[entry.logged_date.strftime("%Y-%m")] += 1
        if entry.rewatch:
            rewatch_count += 1
        film_diary_counts[entry.film_key] += 1

    multi_diary = [
        {
            "key": key,
            "entries": count,
            "name": next((d.name for d in export.diary if d.film_key == key), key),
            "year": next((d.year for d in export.diary if d.film_key == key), None),
        }
        for key, count in film_diary_counts.most_common()
        if count > 1
    ]

    most_rewatched = multi_diary[0] if multi_diary else None

    resumen = {
        "peliculas_vistas": len(watched),
        "peliculas_puntuadas": n_rated,
        "entradas_diario": len(export.diary),
        "revisionados": rewatch_count,
        "proporcion_revisionados": round(100.0 * rewatch_count / len(export.diary), 2)
        if export.diary
        else 0.0,
        "watchlist": len(export.watchlist),
        "likes": len(export.likes),
        "pct_vistas_con_puntuacion": round(100.0 * n_rated / len(watched), 2) if watched else 0.0,
        "vistas_sin_puntuacion": len(watched_not_rated),
        "puntuadas_no_vistas": len(rated_not_watched),
        "nota_media": round(float(series.mean()), 3) if n_rated else None,
        "nota_mediana": round(float(series.median()), 3) if n_rated else None,
        "pct_5_estrellas": pct(dist.get(5.0, 0)),
        "pct_4_5_o_5": pct(dist.get(4.5, 0) + dist.get(5.0, 0)),
        "pct_2_o_menos": pct(sum(dist.get(r, 0) for r in (0.5, 1.0, 1.5, 2.0))),
        "count_5": dist.get(5.0, 0),
        "count_4_5_o_5": dist.get(4.5, 0) + dist.get(5.0, 0),
        "count_2_o_menos": sum(dist.get(r, 0) for r in (0.5, 1.0, 1.5, 2.0)),
        "decada_mas_vista": decade_counts.most_common(1)[0] if decade_counts else None,
        "anio_mas_representado": year_counts.most_common(1)[0] if year_counts else None,
        "decada_mejor_puntuada": best_decade,
        "pelicula_mas_revisionada": most_rewatched,
        "rated_keys": len(rated_keys),
    }

    return {
        "resumen": resumen,
        "rating_distribution": rating_distribution,
        "decades": decades_table,
        "years": years_table,
        "top_years": years_table[:10],
        "best_rated": [
            {"name": f.name, "year": f.year, "rating": f.rating, "uri": f.letterboxd_uri}
            for f in top_rated[:30]
        ],
        "worst_rated": [
            {"name": f.name, "year": f.year, "rating": f.rating, "uri": f.letterboxd_uri}
            for f in worst_rated[:30]
        ],
        "watched_not_rated": [
            {"name": f.name, "year": f.year, "uri": f.letterboxd_uri} for f in watched_not_rated
        ],
        "rated_not_watched": [
            {"name": f.name, "year": f.year, "rating": f.rating, "uri": f.letterboxd_uri}
            for f in rated_not_watched
        ],
        "diary_by_year": [{"year": y, "entries": c} for y, c in sorted(diary_by_year.items())],
        "diary_by_month": [{"month": m, "entries": c} for m, c in sorted(diary_by_month.items())],
        "multi_diary": multi_diary,
        "favorites": [
            {"name": f.name, "year": f.year, "rating": f.rating, "uri": f.letterboxd_uri}
            for f in watched
            if f.rating is not None and f.rating >= 4.5
        ],
        "rewatches": [
            {
                "name": d.name,
                "year": d.year,
                "logged_date": d.logged_date.isoformat() if d.logged_date else None,
                "watched_date": d.watched_date.isoformat() if d.watched_date else None,
                "rating": d.rating,
            }
            for d in export.diary
            if d.rewatch
        ],
    }
