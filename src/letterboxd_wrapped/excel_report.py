"""Generación del libro Excel formateado."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.table import Table, TableStyleInfo

from letterboxd_wrapped.models import LetterboxdExport

HEADER_FILL = PatternFill("solid", fgColor="1A1A1F")
HEADER_FONT = Font(bold=True, color="FF8000")
ACCENT_FILL = PatternFill("solid", fgColor="FFF4E8")


def _autosize(ws, max_width: int = 48) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        length = 0
        for cell in col:
            if cell.value is not None:
                length = max(length, min(len(str(cell.value)), max_width))
        ws.column_dimensions[letter].width = max(10, length + 2)


def _style_header(ws) -> None:
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _excel_safe(value: Any) -> Any:
    """Convierte valores no soportados por openpyxl (dict/list) a texto."""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _write_df(wb: Workbook, title: str, df: pd.DataFrame) -> None:
    ws = wb.create_sheet(title[:31])
    if df is None or df.empty:
        ws.append(["Sin datos"])
        return
    safe = df.copy()
    for col in safe.columns:
        safe[col] = safe[col].map(_excel_safe)
    for r_idx, row in enumerate(dataframe_to_rows(safe, index=False, header=True), 1):
        ws.append(list(row))
    _style_header(ws)
    _autosize(ws)


def write_excel(
    path: str | Path,
    export: LetterboxdExport,
    basic: dict[str, Any],
    rankings: dict[str, Any] | None,
    coverage: dict[str, Any] | None,
    curiosities: list[dict[str, str]],
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    # Quitar hoja por defecto tras crear Resumen
    default = wb.active
    wb.remove(default)

    r = basic["resumen"]
    resumen_rows = [
        ("Generado", datetime.now().isoformat(timespec="seconds")),
        ("Usuario", export.username),
        ("Películas marcadas como vistas", r["peliculas_vistas"]),
        ("Películas puntuadas", r["peliculas_puntuadas"]),
        ("Entradas del diario", r["entradas_diario"]),
        ("Entradas marcadas como revisionado", r["revisionados"]),
        ("Proporción revisionados (%)", r["proporcion_revisionados"]),
        ("Títulos en watchlist", r["watchlist"]),
        ("Likes", r["likes"]),
        ("% vistas con puntuación", r["pct_vistas_con_puntuacion"]),
        ("Vistas sin puntuación", r["vistas_sin_puntuacion"]),
        ("Puntuadas no vistas", r["puntuadas_no_vistas"]),
        ("Nota media", r["nota_media"]),
        ("Mediana de puntuación", r["nota_mediana"]),
        ("% con 5 estrellas", r["pct_5_estrellas"]),
        ("% con 4,5 o 5", r["pct_4_5_o_5"]),
        ("% con 2 o menos", r["pct_2_o_menos"]),
        ("Películas 4,5 o 5", r["count_4_5_o_5"]),
        ("Películas 2 o menos", r["count_2_o_menos"]),
    ]
    if r.get("decada_mas_vista"):
        resumen_rows.append(("Década más vista", f"{r['decada_mas_vista'][0]} ({r['decada_mas_vista'][1]})"))
    if r.get("anio_mas_representado"):
        resumen_rows.append(
            ("Año más representado", f"{r['anio_mas_representado'][0]} ({r['anio_mas_representado'][1]})")
        )
    if rankings and rankings.get("directors_gender_note"):
        resumen_rows.append(("Nota dirección", rankings["directors_gender_note"]))
    if rankings and rankings.get("countries_note"):
        resumen_rows.append(("Nota países", rankings["countries_note"]))

    ws = wb.create_sheet("Resumen", 0)
    ws.append(["Métrica", "Valor"])
    for row in resumen_rows:
        ws.append(list(row))
    _style_header(ws)
    _autosize(ws)

    # Curiosidades
    _write_df(wb, "Curiosidades", pd.DataFrame(curiosities))

    watched_df = pd.DataFrame(
        [
            {
                "Date": f.date_added.isoformat() if f.date_added else None,
                "Name": f.name,
                "Year": f.year,
                "Letterboxd URI": f.letterboxd_uri,
                "Rating": f.rating,
                "Liked": f.liked,
                "IMDb": f.imdb_id,
                "Match": f.match_status,
                "Confidence": f.match_confidence,
                "Original title": f.original_title,
                "Title ES": f.localized_title_es,
                "Runtime": f.runtime_minutes,
                "Genres": ", ".join(f.genres),
                "Countries": ", ".join(f.countries),
                "Collection": f.collection,
                "Type": f.title_type,
                "Directors": ", ".join(p["name"] for p in f.directors),
            }
            for f in export.watched
        ]
    )
    _write_df(wb, "Películas vistas", watched_df)

    rated_df = watched_df[watched_df["Rating"].notna()].copy()
    _write_df(wb, "Películas puntuadas", rated_df)

    _write_df(wb, "Distribución notas", pd.DataFrame(basic["rating_distribution"]))
    _write_df(wb, "Décadas", pd.DataFrame(basic["decades"]))
    _write_df(wb, "Años estreno", pd.DataFrame(basic["years"]))
    _write_df(wb, "Diario por año", pd.DataFrame(basic["diary_by_year"]))

    diary_df = pd.DataFrame(
        [
            {
                "Date": d.logged_date.isoformat() if d.logged_date else None,
                "Name": d.name,
                "Year": d.year,
                "Letterboxd URI": d.letterboxd_uri,
                "Rating": d.rating,
                "Rewatch": "Yes" if d.rewatch else None,
                "Tags": d.tags,
                "Watched Date": d.watched_date.isoformat() if d.watched_date else None,
                "Year logged": d.logged_date.year if d.logged_date else None,
                "Watched year": d.watched_date.year if d.watched_date else None,
            }
            for d in export.diary
        ]
    )
    _write_df(wb, "Diario completo", diary_df)

    watchlist_df = pd.DataFrame(
        [
            {
                "Date": f.date_added.isoformat() if f.date_added else None,
                "Name": f.name,
                "Year": f.year,
                "Letterboxd URI": f.letterboxd_uri,
            }
            for f in export.watchlist
        ]
    )
    _write_df(wb, "Watchlist", watchlist_df)

    if rankings:
        _write_df(wb, "Top actores", pd.DataFrame(rankings.get("actors") or []))
        _write_df(wb, "Top actrices", pd.DataFrame(rankings.get("actresses") or []))
        _write_df(wb, "Top directores", pd.DataFrame(rankings.get("directors") or []))
        # Hoja vacía intencional con nota
        diras = rankings.get("directoras") or []
        if not diras:
            diras = [{"nota": rankings.get("directors_gender_note", "")}]
        _write_df(wb, "Top directoras", pd.DataFrame(diras))
        _write_df(wb, "Top guionistas", pd.DataFrame(rankings.get("writers") or []))
        countries_df = pd.DataFrame(rankings.get("countries_all") or rankings.get("countries") or [])
        _write_df(wb, "Países", countries_df)
        _write_df(wb, "Géneros", pd.DataFrame(rankings.get("genres") or []))
        _write_df(wb, "Franquicias", pd.DataFrame(rankings.get("franchises") or []))
        _write_df(wb, "Colaboraciones", pd.DataFrame(rankings.get("collaborations") or []))
        _write_df(wb, "Mejores directores", pd.DataFrame(rankings.get("best_directors") or []))
    else:
        for name in (
            "Top actores",
            "Top actrices",
            "Top directores",
            "Top directoras",
            "Top guionistas",
            "Países",
            "Géneros",
            "Franquicias",
        ):
            _write_df(wb, name, pd.DataFrame([{"nota": "Metadatos externos no disponibles"}]))

    _write_df(wb, "Películas favoritas", pd.DataFrame(basic.get("favorites") or []))
    _write_df(wb, "Revisionados", pd.DataFrame(basic.get("rewatches") or []))
    _write_df(wb, "Mejor puntuadas", pd.DataFrame(basic.get("best_rated") or []))
    _write_df(wb, "Peor puntuadas", pd.DataFrame(basic.get("worst_rated") or []))

    pending = (coverage or {}).get("pending") or []
    _write_df(wb, "Correspondencias pendientes", pd.DataFrame(pending))

    if coverage:
        cov_rows = [
            {"métrica": k, "valor": v}
            for k, v in coverage.items()
            if k not in {"pending", "sources", "omissions"}
        ]
        cov_rows.extend(
            {"métrica": f"source_{k}", "valor": v} for k, v in (coverage.get("sources") or {}).items()
        )
        cov_rows.extend({"métrica": "omisión", "valor": o} for o in (coverage.get("omissions") or []))
        _write_df(wb, "Cobertura metadatos", pd.DataFrame(cov_rows))

    wb.save(path)
    return path
