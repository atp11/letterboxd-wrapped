"""Apartado automático de curiosidades a partir de datos reales."""

from __future__ import annotations

from typing import Any

from letterboxd_wrapped.models import LetterboxdExport


def build_curiosities(
    export: LetterboxdExport,
    basic: dict[str, Any],
    rankings: dict[str, Any] | None,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    r = basic["resumen"]

    def add(title: str, detail: str) -> None:
        if detail:
            items.append({"title": title, "detail": detail})

    if r.get("anio_mas_representado"):
        year, n = r["anio_mas_representado"]
        add("Año de estreno más representado", f"{year} ({n} películas)")

    if r.get("decada_mas_vista"):
        dec, n = r["decada_mas_vista"]
        add("Década favorita por volumen", f"{dec} ({n} películas)")

    if r.get("decada_mejor_puntuada"):
        d = r["decada_mejor_puntuada"]
        add(
            "Década favorita por puntuación",
            f"{d['decade']} — media {d['avg_rating']} ({d['rated']} puntuadas)",
        )

    if rankings:
        if rankings.get("actors"):
            a = rankings["actors"][0]
            add("Actor más visto", f"{a['name']} ({a['films']} películas, media {a['avg_rating']})")
        if rankings.get("actresses"):
            a = rankings["actresses"][0]
            add(
                "Actriz más vista",
                f"{a['name']} ({a['films']} películas, media {a['avg_rating']})",
            )
        if rankings.get("directors"):
            d = rankings["directors"][0]
            add("Director/a más visto/a", f"{d['name']} ({d['films']} películas)")
        if rankings.get("best_directors"):
            d = rankings["best_directors"][0]
            add(
                "Director/a mejor valorado/a",
                f"{d['name']} — media {d['avg_rating']} ({d['rated']} puntuadas)",
            )
        if rankings.get("writers"):
            w = rankings["writers"][0]
            add("Guionista más frecuente", f"{w['name']} ({w['films']} películas)")
        if rankings.get("countries"):
            c = rankings["countries"][0]
            add(
                "País más representado",
                f"{c['country']} ({c['films']} películas; {c['pct_catalog']}% del catálogo; "
                f"criterio inclusivo en coproducciones)",
            )
        if rankings.get("genres"):
            g = rankings["genres"][0]
            add("Género que más ves", f"{g['genre']} ({g['films']} películas)")
            by_rating = [x for x in rankings["genres"] if x.get("rated", 0) >= 5 and x.get("avg_rating")]
            if by_rating:
                best_g = max(by_rating, key=lambda x: x["avg_rating"])
                add(
                    "Género que mejor puntúas",
                    f"{best_g['genre']} — media {best_g['avg_rating']} ({best_g['rated']} puntuadas)",
                )
        if rankings.get("franchises"):
            fr = rankings["franchises"][0]
            add("Franquicia más vista", f"{fr['franchise']} ({fr['films_seen']} películas)")
        if rankings.get("longest"):
            f = rankings["longest"][0]
            add("Película más larga", f"{f['name']} ({f['year']}) — {f['runtime']} min")
        if rankings.get("top_genre_decade_combos"):
            combo = rankings["top_genre_decade_combos"][0]
            add("Combinación género·década más frecuente", f"{combo['combo']} ({combo['films']})")
        if rankings.get("favorite_people"):
            p = rankings["favorite_people"][0]
            add(
                "Persona más presente en tus favoritas (4,5+)",
                f"{p['name']} ({p['films']} películas)",
            )

    if r.get("pelicula_mas_revisionada"):
        m = r["pelicula_mas_revisionada"]
        add(
            "Película con más entradas en el diario",
            f"{m['name']} ({m['year']}) — {m['entries']} entradas",
        )

    years = [f.year for f in export.watched if f.year is not None]
    if years:
        oldest = min(export.watched, key=lambda f: f.year if f.year is not None else 9999)
        newest = max(export.watched, key=lambda f: f.year if f.year is not None else -1)
        add("Película más antigua vista", f"{oldest.name} ({oldest.year})")
        add("Película más reciente vista", f"{newest.name} ({newest.year})")

    if r.get("nota_media") is not None:
        add("Nota media del perfil", f"{r['nota_media']} ★ (mediana {r['nota_mediana']})")

    return items
