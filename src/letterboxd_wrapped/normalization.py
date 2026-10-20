"""Normalización de títulos, fechas y puntuaciones."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_title(title: str | None) -> str:
    """Normaliza un título para comparación sin destruir diferencias útiles."""
    if not title:
        return ""
    text = strip_accents(str(title)).lower().strip()
    text = text.replace("&", " and ")
    # Apostrofes: "philosopher's" -> "philosophers" (no espacio suelto)
    text = text.replace("'", "").replace("'", "").replace("'", "")
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def parse_year(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    match = re.search(r"(18|19|20)\d{2}", text)
    if not match:
        return None
    year = int(match.group(0))
    if 1870 <= year <= 2100:
        return year
    return None


def decade_of(year: int | None) -> str | None:
    if year is None:
        return None
    return f"{(year // 10) * 10}s"


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_rating(value: Any) -> float | None:
    """Convierte la nota de Letterboxd (0.5–5 en pasos de 0.5) a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        rating = float(value)
    else:
        text = str(value).strip().replace(",", ".")
        if not text or text.lower() in {"nan", "none", "null", ""}:
            return None
        try:
            rating = float(text)
        except ValueError:
            return None
    # Letterboxd usa media estrella; rechaza valores fuera de rango
    if rating < 0.5 or rating > 5:
        return None
    # Redondea a medio punto si llega con ruido
    rounded = round(rating * 2) / 2
    if rounded < 0.5 or rounded > 5:
        return None
    return rounded


def film_key(name: str | None, year: int | None, uri: str | None = None) -> str:
    """Clave estable para deduplicar películas."""
    if uri:
        return f"uri:{uri.strip()}"
    return f"title:{normalize_title(name)}|{year or ''}"


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text
