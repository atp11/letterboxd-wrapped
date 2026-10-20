"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from letterboxd_wrapped import __version__
from letterboxd_wrapped.curiosities import build_curiosities
from letterboxd_wrapped.excel_report import write_excel
from letterboxd_wrapped.html_report import write_html
from letterboxd_wrapped.importer import export_summary, load_export
from letterboxd_wrapped.metadata.enricher import enrich_films
from letterboxd_wrapped.rankings import compute_rankings
from letterboxd_wrapped.statistics import compute_basic_stats


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="letterboxd_wrapped",
        description="Genera un Letterboxd Wrapped a partir de una exportación ZIP.",
    )
    p.add_argument("--input", "-i", required=True, help="Ruta al ZIP de Letterboxd")
    p.add_argument("--output", "-o", default="./output", help="Directorio de salida")
    p.add_argument("--cache-dir", default="./data/cache", help="Caché de metadatos")
    p.add_argument("--imdb-dir", default="./data/imdb", help="Datasets IMDb locales")
    p.add_argument("--offline", action="store_true", help="No descargar ni consultar APIs")
    p.add_argument("--force-refresh", action="store_true", help="Forzar actualización de metadatos")
    p.add_argument("--limit", type=int, default=None, help="Limitar películas (pruebas)")
    p.add_argument("--basic-only", action="store_true", help="Solo estadísticas básicas sin metadatos")
    p.add_argument("--excel-only", action="store_true", help="Generar solo Excel")
    p.add_argument("--html-only", action="store_true", help="Generar solo HTML")
    p.add_argument("--no-wikidata", action="store_true", help="No consultar Wikidata")
    p.add_argument("--min-rated-directors", type=int, default=3)
    p.add_argument("--coverage-summary", action="store_true", help="Imprimir cobertura al final")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("letterboxd_wrapped")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Cargando exportación %s", args.input)
    export = load_export(args.input)
    summary = export_summary(export)
    log.info("Resumen importación: %s", summary)

    if args.limit:
        export.watched = export.watched[: args.limit]
        log.info("Modo prueba: limitando a %d películas vistas", args.limit)

    basic = compute_basic_stats(export)
    coverage = None
    rankings = None

    if not args.basic_only:
        log.info("Enriqueciendo metadatos…")
        try:
            coverage = enrich_films(
                export.watched,
                cache_dir=args.cache_dir,
                imdb_dir=args.imdb_dir,
                offline=args.offline,
                force=args.force_refresh,
                limit=None,
                use_wikidata=not args.no_wikidata,
                tmdb_api_key=os.environ.get("TMDB_API_KEY"),
            )
            rankings = compute_rankings(
                export, min_rated_directors=args.min_rated_directors
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("Fallo en metadatos; se continúan estadísticas básicas: %s", exc)
            coverage = {
                "omissions": [str(exc)],
                "pending": [],
                "sources": {"imdb": False, "wikidata": False, "tmdb": False},
                "matched_confirmed": 0,
                "matched_probable": 0,
                "unmatched": len(export.watched),
                "conflict": 0,
                "with_cast": 0,
                "with_directors": 0,
                "with_countries": 0,
                "with_collection": 0,
                "with_genres": 0,
                "total_films": len(export.watched),
            }
    else:
        log.info("Modo --basic-only: sin metadatos externos")

    curiosities = build_curiosities(export, basic, rankings)

    excel_path = out_dir / "letterboxd_wrapped.xlsx"
    html_path = out_dir / "letterboxd_wrapped.html"
    summary_path = out_dir / "summary.json"

    if not args.html_only:
        write_excel(excel_path, export, basic, rankings, coverage, curiosities)
        log.info("Excel: %s", excel_path)
    if not args.excel_only:
        write_html(html_path, export, basic, rankings, coverage, curiosities, version=__version__)
        log.info("HTML: %s", html_path)

    payload = {
        "version": __version__,
        "import_summary": summary,
        "resumen": basic["resumen"],
        "curiosities": curiosities,
        "coverage": {
            k: v
            for k, v in (coverage or {}).items()
            if k != "pending"
        }
        if coverage
        else None,
        "pending_count": len((coverage or {}).get("pending") or []),
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Resumen JSON: %s", summary_path)

    # Consola amigable
    print("\n=== Letterboxd Wrapped ===")
    print(f"Usuario: {export.username}")
    print(f"Vistas: {basic['resumen']['peliculas_vistas']} | Puntuadas: {basic['resumen']['peliculas_puntuadas']}")
    print(f"Nota media: {basic['resumen']['nota_media']} | Mediana: {basic['resumen']['nota_mediana']}")
    for c in curiosities[:8]:
        print(f" · {c['title']}: {c['detail']}")
    if args.coverage_summary and coverage:
        print("\n--- Cobertura ---")
        for key in (
            "matched_confirmed",
            "matched_probable",
            "unmatched",
            "conflict",
            "with_cast",
            "with_countries",
            "with_collection",
        ):
            print(f" {key}: {coverage.get(key)}")
        for o in coverage.get("omissions") or []:
            print(f" omitido: {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
