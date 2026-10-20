"""Gráficos Plotly embebibles (CDN o JSON offline-friendly)."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from plotly.offline import plot as plotly_plot


PALETTE = {
    "bg": "#0d0d0f",
    "card": "#1a1a1f",
    "text": "#f2efe9",
    "muted": "#9a958c",
    "accent": "#ff8000",  # Letterboxd orange
    "accent2": "#40bcf4",
    "bar": "#ff8000",
}


def _layout(**kwargs: Any) -> dict[str, Any]:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Helvetica, sans-serif", color=PALETTE["text"]),
        margin=dict(l=40, r=20, t=40, b=40),
        xaxis=dict(gridcolor="#2a2a30", zeroline=False),
        yaxis=dict(gridcolor="#2a2a30", zeroline=False),
    )
    base.update(kwargs)
    return base


def fig_to_html(fig: go.Figure, include_plotlyjs: bool | str = False) -> str:
    return plotly_plot(
        fig,
        output_type="div",
        include_plotlyjs=include_plotlyjs,
        config={"displayModeBar": False, "responsive": True},
    )


def rating_distribution_chart(distribution: list[dict[str, Any]]) -> go.Figure:
    xs = [str(d["rating"]) for d in distribution]
    ys = [d["count"] for d in distribution]
    fig = go.Figure(
        go.Bar(x=xs, y=ys, marker_color=PALETTE["bar"], hovertemplate="%{x}★: %{y}<extra></extra>")
    )
    fig.update_layout(_layout(title="Distribución de puntuaciones", xaxis_title="Estrellas", yaxis_title="Películas"))
    return fig


def decades_chart(decades: list[dict[str, Any]]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Películas",
            x=[d["decade"] for d in decades],
            y=[d["films"] for d in decades],
            marker_color=PALETTE["accent"],
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Nota media",
            x=[d["decade"] for d in decades],
            y=[d["avg_rating"] for d in decades],
            yaxis="y2",
            mode="lines+markers",
            marker_color=PALETTE["accent2"],
        )
    )
    fig.update_layout(
        _layout(
            title="Décadas: volumen vs nota media",
            yaxis=dict(title="Películas", gridcolor="#2a2a30"),
            yaxis2=dict(title="Nota media", overlaying="y", side="right", range=[0, 5], gridcolor="#2a2a30"),
            legend=dict(orientation="h"),
        )
    )
    return fig


def diary_activity_chart(by_month: list[dict[str, Any]]) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=[m["month"] for m in by_month],
            y=[m["entries"] for m in by_month],
            fill="tozeroy",
            line=dict(color=PALETTE["accent2"]),
            hovertemplate="%{x}: %{y}<extra></extra>",
        )
    )
    fig.update_layout(_layout(title="Actividad del diario (por mes)", xaxis_title="Mes", yaxis_title="Entradas"))
    return fig


def top_bar_chart(rows: list[dict[str, Any]], name_key: str, value_key: str, title: str) -> go.Figure:
    rows = list(reversed(rows[:15]))
    fig = go.Figure(
        go.Bar(
            x=[r[value_key] for r in rows],
            y=[r[name_key] for r in rows],
            orientation="h",
            marker_color=PALETTE["accent"],
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )
    fig.update_layout(_layout(title=title, height=max(360, 28 * len(rows))))
    return fig


def build_all_charts(basic: dict[str, Any], rankings: dict[str, Any] | None) -> dict[str, str]:
    charts: dict[str, str] = {}
    charts["ratings"] = fig_to_html(rating_distribution_chart(basic["rating_distribution"]), include_plotlyjs="cdn")
    charts["decades"] = fig_to_html(decades_chart(basic["decades"]))
    charts["diary"] = fig_to_html(diary_activity_chart(basic["diary_by_month"]))
    if rankings:
        if rankings.get("genres"):
            charts["genres"] = fig_to_html(
                top_bar_chart(rankings["genres"], "genre", "films", "Géneros más frecuentes")
            )
        if rankings.get("countries"):
            charts["countries"] = fig_to_html(
                top_bar_chart(rankings["countries"], "country", "films", "Países de producción")
            )
        if rankings.get("directors"):
            charts["directors"] = fig_to_html(
                top_bar_chart(rankings["directors"], "name", "films", "Dirección más vista")
            )
        if rankings.get("actors"):
            charts["actors"] = fig_to_html(
                top_bar_chart(rankings["actors"], "name", "films", "Actores más vistos")
            )
        if rankings.get("actresses"):
            charts["actresses"] = fig_to_html(
                top_bar_chart(rankings["actresses"], "name", "films", "Actrices más vistas")
            )
    return charts
