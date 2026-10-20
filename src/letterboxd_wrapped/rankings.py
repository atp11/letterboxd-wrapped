"""Rankings de personas, países, géneros y franquicias."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable, Iterable

from letterboxd_wrapped.models import FilmRecord, LetterboxdExport
from letterboxd_wrapped.normalization import decade_of


def _person_rank(
    films: list[FilmRecord],
    getter: Callable[[FilmRecord], Iterable[dict[str, Any]]],
    *,
    catalog_size: int,
    min_rated_for_avg: int = 1,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Cuenta películas distintas por persona (no visionados repetidos)."""
    film_sets: dict[str, set[str]] = defaultdict(set)
    rated_sets: dict[str, set[str]] = defaultdict(set)
    rating_sums: dict[str, float] = defaultdict(float)
    five_star: dict[str, set[str]] = defaultdict(set)
    high_star: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    decades: dict[str, Counter[str]] = defaultdict(Counter)

    for film in films:
        for person in getter(film):
            pid = person.get("id") or person.get("name")
            if not pid:
                continue
            names[pid] = person.get("name") or str(pid)
            film_sets[pid].add(film.key)
            if film.rating is not None:
                rated_sets[pid].add(film.key)
                # Evitar sumar dos veces la misma película
                # (si la persona aparece dos veces en créditos, el set ya deduplica)
            if film.year is not None:
                dec = decade_of(film.year)
                if dec:
                    decades[pid][dec] += 1  # se ajusta abajo

    # Recalcular décadas y ratings sin doble conteo por créditos duplicados
    decades = defaultdict(Counter)
    rating_sums = defaultdict(float)
    rated_sets = defaultdict(set)
    five_star = defaultdict(set)
    high_star = defaultdict(set)
    film_sets = defaultdict(set)
    names = {}

    for film in films:
        seen_in_film: set[str] = set()
        for person in getter(film):
            pid = person.get("id") or person.get("name")
            if not pid or pid in seen_in_film:
                continue
            seen_in_film.add(pid)
            names[pid] = person.get("name") or str(pid)
            film_sets[pid].add(film.key)
            if film.year is not None:
                dec = decade_of(film.year)
                if dec:
                    decades[pid][dec] += 1
            if film.rating is not None:
                if film.key not in rated_sets[pid]:
                    rated_sets[pid].add(film.key)
                    rating_sums[pid] += film.rating
                if film.rating == 5.0:
                    five_star[pid].add(film.key)
                if film.rating >= 4.5:
                    high_star[pid].add(film.key)

    rows = []
    for pid, keys in film_sets.items():
        n = len(keys)
        n_rated = len(rated_sets[pid])
        avg = round(rating_sums[pid] / n_rated, 3) if n_rated >= min_rated_for_avg else None
        rows.append(
            {
                "id": pid,
                "name": names[pid],
                "films": n,
                "pct_catalog": round(100.0 * n / catalog_size, 2) if catalog_size else 0.0,
                "rated": n_rated,
                "avg_rating": avg,
                "five_stars": len(five_star[pid]),
                "high_ratings": len(high_star[pid]),
                "decades": dict(decades[pid]),
            }
        )
    rows.sort(key=lambda r: (-r["films"], -(r["avg_rating"] or 0), r["name"]))
    return rows[:top_n] if top_n else rows


def compute_rankings(
    export: LetterboxdExport,
    *,
    min_rated_directors: int = 3,
    top_n: int = 20,
) -> dict[str, Any]:
    films = export.watched
    catalog = len(films)
    enriched = [f for f in films if f.imdb_id]

    actors = _person_rank(films, lambda f: f.actors, catalog_size=catalog, top_n=top_n)
    actresses = _person_rank(films, lambda f: f.actresses, catalog_size=catalog, top_n=top_n)
    # Ranking conjunto si no hay distinción
    if not actors and not actresses:
        performers = _person_rank(
            films,
            lambda f: [p for p in f.cast if p.get("category") in {"actor", "actress", "self"}],
            catalog_size=catalog,
            top_n=top_n,
        )
        performers_note = (
            "No fue posible distinguir actor/actriz con categorías fiables; "
            "se muestra un ranking conjunto de intérpretes."
        )
    else:
        performers = []
        performers_note = None

    directors_all = _person_rank(
        films, lambda f: f.directors, catalog_size=catalog, top_n=0, min_rated_for_avg=1
    )
    # Sin género inferido: un solo ranking de dirección; hojas "directoras" vacías
    # con explicación, salvo que la fuente aporte categoría sexada (IMDb no lo hace
    # para directors).
    directors = directors_all[:top_n]
    directoras: list[dict[str, Any]] = []
    directors_gender_note = (
        "IMDb no distingue director/directora en title.crew. "
        "Se presenta un ranking único de dirección. "
        "La hoja 'Top directoras' queda vacía a propósito para no inferir género por nombre."
    )

    writers = _person_rank(films, lambda f: f.writers, catalog_size=catalog, top_n=top_n)

    best_directors = [
        d
        for d in directors_all
        if d["rated"] >= min_rated_directors and d["avg_rating"] is not None
    ]
    best_directors.sort(key=lambda r: (-(r["avg_rating"] or 0), -r["rated"], r["name"]))

    most_five_star_directors = sorted(
        directors_all, key=lambda r: (-r["five_stars"], -r["films"], r["name"])
    )[:top_n]
    most_five_star_actors = sorted(
        actors, key=lambda r: (-r["five_stars"], -r["films"], r["name"])
    )[:top_n]
    most_high_actors = sorted(
        actors, key=lambda r: (-r["high_ratings"], -r["films"], r["name"])
    )[:top_n]
    most_high_actresses = sorted(
        actresses, key=lambda r: (-r["high_ratings"], -r["films"], r["name"])
    )[:top_n]
    most_five_star_actresses = sorted(
        actresses, key=lambda r: (-r["five_stars"], -r["films"], r["name"])
    )[:top_n]

    # Países
    country_films: dict[str, set[str]] = defaultdict(set)
    primary_country_films: dict[str, set[str]] = defaultdict(set)
    for film in films:
        for c in film.countries:
            country_films[c].add(film.key)
        if film.primary_country:
            primary_country_films[film.primary_country].add(film.key)

    countries = []
    for c, keys in country_films.items():
        rated = [f.rating for f in films if f.key in keys and f.rating is not None]
        countries.append(
            {
                "country": c,
                "films": len(keys),
                "pct_catalog": round(100.0 * len(keys) / catalog, 2) if catalog else 0.0,
                "as_primary": len(primary_country_films.get(c, set())),
                "rated": len(rated),
                "avg_rating": round(sum(rated) / len(rated), 3) if rated else None,
            }
        )
    countries.sort(key=lambda r: (-r["films"], r["country"]))

    # Coproducciones (2+ países)
    co_counter: Counter[str] = Counter()
    for film in films:
        if len(film.countries) >= 2:
            label = " + ".join(sorted(film.countries))
            co_counter[label] += 1
    coproductions = [
        {"countries": k, "films": v} for k, v in co_counter.most_common(top_n)
    ]

    # Géneros
    genre_films: dict[str, set[str]] = defaultdict(set)
    for film in films:
        for g in film.genres:
            genre_films[g].add(film.key)
    genres = []
    for g, keys in genre_films.items():
        rated = [f for f in films if f.key in keys and f.rating is not None]
        five = [f for f in rated if f.rating == 5.0]
        genres.append(
            {
                "genre": g,
                "films": len(keys),
                "pct_catalog": round(100.0 * len(keys) / catalog, 2) if catalog else 0.0,
                "rated": len(rated),
                "avg_rating": round(sum(f.rating for f in rated) / len(rated), 3) if rated else None,
                "five_stars": len(five),
                "pct_five": round(100.0 * len(five) / len(rated), 2) if rated else None,
            }
        )
    genres.sort(key=lambda r: (-r["films"], r["genre"]))

    # Duración
    runtimes = [f.runtime_minutes for f in films if f.runtime_minutes]
    runtime_stats = None
    longest = shortest = []
    if runtimes:
        import statistics

        runtime_stats = {
            "count": len(runtimes),
            "mean": round(statistics.mean(runtimes), 1),
            "median": round(statistics.median(runtimes), 1),
            "min": min(runtimes),
            "max": max(runtimes),
        }
        with_rt = [f for f in films if f.runtime_minutes]
        longest = sorted(with_rt, key=lambda f: -(f.runtime_minutes or 0))[:10]
        shortest = sorted(with_rt, key=lambda f: (f.runtime_minutes or 0))[:10]

    # Tipos
    type_counts = Counter(f.title_type for f in films if f.title_type)
    genre_set_lower = {g.lower() for g in genre_films}
    type_breakdown = {
        "title_types": dict(type_counts),
        "animation_films": len(genre_films.get("Animation", set())),
        "documentary_films": len(genre_films.get("Documentary", set())),
        "short_films": type_counts.get("short", 0) + type_counts.get("tvShort", 0),
        "live_action_approx": catalog - len(genre_films.get("Animation", set())),
        "note": (
            "Animación/documental se basan en géneros IMDb; "
            "live-action es aproximación (total − Animation)."
        ),
    }

    def _is_real_franchise(name: str) -> bool:
        lower = name.lower()
        noise = (
            "lista de",
            "list of",
            "anexo:",
            "category:",
            "categoría:",
            "bbc",
            "100 mejores",
            "best films",
            "feature films",  # p.ej. "DreamWorks Animation feature films" como lista
        )
        if any(n in lower for n in noise):
            return False
        return True

    # Franquicias (filtramos listas/categorías de Wikidata que no son sagas)
    coll_films: dict[str, set[str]] = defaultdict(set)
    for film in films:
        if film.collection and _is_real_franchise(film.collection):
            coll_films[film.collection].add(film.key)
    franchises = []
    for name, keys in coll_films.items():
        rated = [f.rating for f in films if f.key in keys and f.rating is not None]
        franchises.append(
            {
                "franchise": name,
                "films_seen": len(keys),
                "rated": len(rated),
                "avg_rating": round(sum(rated) / len(rated), 3) if rated else None,
                "pct_of_saga": None,  # tamaño total de saga no fiable sin fuente completa
            }
        )
    franchises.sort(key=lambda r: (-r["films_seen"], -(r["avg_rating"] or 0)))
    best_franchise = None
    for fr in franchises:
        if fr["rated"] >= 2 and fr["avg_rating"] is not None:
            if best_franchise is None or fr["avg_rating"] > best_franchise["avg_rating"]:
                best_franchise = fr

    # Colaboraciones director-actor
    collab: Counter[tuple[str, str, str, str]] = Counter()
    for film in films:
        for d in film.directors:
            for a in list(film.actors) + list(film.actresses):
                collab[
                    (
                        d.get("id") or "",
                        d.get("name") or "",
                        a.get("id") or "",
                        a.get("name") or "",
                    )
                ] += 1
    collaborations = [
        {
            "director_id": k[0],
            "director": k[1],
            "person_id": k[2],
            "person": k[3],
            "films": v,
        }
        for k, v in collab.most_common(top_n)
        if v >= 2
    ]

    # Favoritas (4.5+) — personas más presentes
    favorites = [f for f in films if f.rating is not None and f.rating >= 4.5]
    fav_people = _person_rank(
        favorites,
        lambda f: list(f.actors) + list(f.actresses) + list(f.directors),
        catalog_size=max(len(favorites), 1),
        top_n=top_n,
    )

    # Desviación respecto a media del perfil
    rated = [f for f in films if f.rating is not None]
    mean = sum(f.rating for f in rated) / len(rated) if rated else None
    outliers = []
    if mean is not None:
        for f in rated:
            delta = round(f.rating - mean, 3)
            outliers.append(
                {
                    "name": f.name,
                    "year": f.year,
                    "rating": f.rating,
                    "delta_vs_mean": delta,
                    "uri": f.letterboxd_uri,
                }
            )
        outliers.sort(key=lambda r: -abs(r["delta_vs_mean"]))

    # Evolución géneros/países por década
    genre_by_decade: dict[str, Counter[str]] = defaultdict(Counter)
    country_by_decade: dict[str, Counter[str]] = defaultdict(Counter)
    for film in films:
        dec = decade_of(film.year)
        if not dec:
            continue
        for g in film.genres:
            genre_by_decade[dec][g] += 1
        for c in film.countries:
            country_by_decade[dec][c] += 1

    # Combo género+década
    combo: Counter[str] = Counter()
    for film in films:
        dec = decade_of(film.year)
        if not dec:
            continue
        for g in film.genres:
            combo[f"{g} · {dec}"] += 1

    return {
        "actors": actors,
        "actresses": actresses,
        "performers": performers,
        "performers_note": performers_note,
        "directors": directors,
        "directoras": directoras,
        "directors_gender_note": directors_gender_note,
        "best_directors": best_directors[:top_n],
        "most_five_star_directors": most_five_star_directors,
        "most_five_star_actors": most_five_star_actors,
        "most_five_star_actresses": most_five_star_actresses,
        "most_high_actors": most_high_actors,
        "most_high_actresses": most_high_actresses,
        "writers": writers,
        "countries": countries[:top_n],
        "countries_all": countries,
        "countries_note": (
            "Una coproducción cuenta en cada país participante; "
            "los porcentajes no son categorías excluyentes."
        ),
        "coproductions": coproductions,
        "genres": genres,
        "runtime_stats": runtime_stats,
        "longest": [
            {"name": f.name, "year": f.year, "runtime": f.runtime_minutes, "rating": f.rating}
            for f in longest
        ],
        "shortest": [
            {"name": f.name, "year": f.year, "runtime": f.runtime_minutes, "rating": f.rating}
            for f in shortest
        ],
        "type_breakdown": type_breakdown,
        "franchises": franchises,
        "best_franchise": best_franchise,
        "collaborations": collaborations,
        "favorite_people": fav_people,
        "rating_outliers": outliers[:40],
        "genre_by_decade": {k: dict(v) for k, v in genre_by_decade.items()},
        "country_by_decade": {k: dict(v) for k, v in country_by_decade.items()},
        "top_genre_decade_combos": [
            {"combo": k, "films": v} for k, v in combo.most_common(15)
        ],
        "enriched_films": len(enriched),
        "catalog_size": catalog,
        "profile_mean": round(mean, 3) if mean is not None else None,
    }
