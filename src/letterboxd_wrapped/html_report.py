"""Informe HTML autocontenido estilo Letterboxd Wrapped."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from letterboxd_wrapped.models import LetterboxdExport
from letterboxd_wrapped.visualizations import build_all_charts

TEMPLATE = Template(
    r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Letterboxd Wrapped — {{ username }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Libre+Baskerville:wght@700&display=swap" rel="stylesheet"/>
<style>
:root {
  --bg: #0b0b0d;
  --bg2: #141418;
  --card: #1c1c22;
  --text: #f3efe7;
  --muted: #9b968c;
  --accent: #ff8000;
  --accent2: #40bcf4;
  --line: #2c2c34;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "IBM Plex Sans", system-ui, sans-serif;
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(255,128,0,.18), transparent 50%),
    radial-gradient(900px 500px at 90% 0%, rgba(64,188,244,.12), transparent 45%),
    linear-gradient(180deg, #121218 0%, var(--bg) 40%);
  color: var(--text);
  line-height: 1.5;
}
a { color: var(--accent2); text-decoration: none; }
header.hero {
  min-height: 88vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 4rem 1.5rem 3rem;
  max-width: 1100px;
  margin: 0 auto;
}
.brand {
  font-family: "Libre Baskerville", Georgia, serif;
  font-size: clamp(2.6rem, 7vw, 4.8rem);
  letter-spacing: -0.02em;
  margin: 0 0 .4rem;
  background: linear-gradient(90deg, #fff, var(--accent));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: rise .9s ease both;
}
.tagline {
  font-size: clamp(1.05rem, 2.4vw, 1.35rem);
  color: var(--muted);
  max-width: 36rem;
  animation: rise 1s .1s ease both;
}
.meta {
  margin-top: 1.5rem;
  color: var(--muted);
  font-size: .95rem;
  animation: rise 1s .2s ease both;
}
nav {
  position: sticky; top: 0; z-index: 20;
  backdrop-filter: blur(10px);
  background: rgba(11,11,13,.82);
  border-bottom: 1px solid var(--line);
  display: flex; gap: .75rem; flex-wrap: wrap;
  padding: .75rem 1.25rem;
}
nav a { color: var(--muted); font-size: .9rem; }
nav a:hover { color: var(--accent); }
main { max-width: 1100px; margin: 0 auto; padding: 1.5rem; }
section { margin: 3rem 0; animation: rise .7s ease both; }
h2 {
  font-family: "Libre Baskerville", Georgia, serif;
  font-size: 1.7rem;
  margin: 0 0 .75rem;
  border-left: 4px solid var(--accent);
  padding-left: .75rem;
}
.lead { color: var(--muted); margin: 0 0 1.25rem; max-width: 42rem; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: .9rem;
}
.stat {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  transition: transform .25s ease, border-color .25s ease;
}
.stat:hover { transform: translateY(-3px); border-color: var(--accent); }
.stat .n {
  font-size: 1.7rem; font-weight: 700; color: var(--accent);
}
.stat .l { color: var(--muted); font-size: .85rem; }
.chart {
  background: var(--bg2);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: .5rem;
  margin: 1rem 0 1.5rem;
}
table {
  width: 100%; border-collapse: collapse; font-size: .92rem;
  background: var(--card); border-radius: 12px; overflow: hidden;
}
th, td { padding: .55rem .7rem; border-bottom: 1px solid var(--line); text-align: left; }
th { color: var(--accent); font-weight: 600; position: sticky; top: 0; background: #1c1c22; }
tr:hover td { background: rgba(255,128,0,.06); }
.table-wrap { overflow: auto; max-height: 420px; border-radius: 12px; border: 1px solid var(--line); }
.curiosity {
  display: grid; gap: .7rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.curiosity article {
  background: linear-gradient(160deg, #221c16, #1a1a1f 55%);
  border: 1px solid #3a2d1f;
  border-radius: 12px; padding: 1rem;
}
.curiosity h3 { margin: 0 0 .35rem; font-size: 1rem; color: var(--accent); }
.curiosity p { margin: 0; color: var(--text); font-size: .92rem; }
.note { color: var(--muted); font-size: .85rem; margin-top: .75rem; }
footer { text-align: center; color: var(--muted); padding: 2rem 1rem 3rem; font-size: .85rem; }
@keyframes rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: none; }
}
@media (max-width: 640px) {
  header.hero { min-height: auto; padding-top: 3rem; }
}
</style>
</head>
<body>
<header class="hero">
  <p class="meta">Letterboxd Wrapped</p>
  <h1 class="brand">{{ username }}</h1>
  <p class="tagline">Tu año (y toda tu historia) en cine: {{ resumen.peliculas_vistas }} películas vistas, nota media {{ resumen.nota_media }}★.</p>
  <p class="meta">Generado {{ generated }} · {{ resumen.peliculas_puntuadas }} puntuadas · {{ resumen.entradas_diario }} entradas de diario</p>
</header>
<nav>
  <a href="#resumen">Resumen</a>
  <a href="#notas">Notas</a>
  <a href="#tiempo">Tiempo</a>
  <a href="#personas">Personas</a>
  <a href="#mundo">Mundo</a>
  <a href="#curiosidades">Curiosidades</a>
  <a href="#cobertura">Cobertura</a>
</nav>
<main>
<section id="resumen">
  <h2>Resumen del catálogo</h2>
  <p class="lead">Vistas, puntuaciones y actividad del diario, sin mezclar conceptos.</p>
  <div class="grid">
    <div class="stat"><div class="n">{{ resumen.peliculas_vistas }}</div><div class="l">Vistas</div></div>
    <div class="stat"><div class="n">{{ resumen.peliculas_puntuadas }}</div><div class="l">Puntuadas</div></div>
    <div class="stat"><div class="n">{{ resumen.nota_media }}</div><div class="l">Nota media</div></div>
    <div class="stat"><div class="n">{{ resumen.nota_mediana }}</div><div class="l">Mediana</div></div>
    <div class="stat"><div class="n">{{ resumen.entradas_diario }}</div><div class="l">Diario</div></div>
    <div class="stat"><div class="n">{{ resumen.revisionados }}</div><div class="l">Revisionados</div></div>
    <div class="stat"><div class="n">{{ resumen.watchlist }}</div><div class="l">Watchlist</div></div>
    <div class="stat"><div class="n">{{ resumen.pct_4_5_o_5 }}%</div><div class="l">4,5★ o 5★</div></div>
  </div>
</section>

<section id="notas">
  <h2>Puntuaciones</h2>
  <p class="lead">Escala Letterboxd de 0,5 a 5. Las medias usan solo películas puntuadas.</p>
  <div class="chart">{{ charts.ratings | safe }}</div>
  {% if best_rated %}
  <h3 style="margin:1.25rem 0 .5rem;font-size:1.05rem;color:var(--accent);">
    {{ best_rated_note or "Mejor puntuadas" }}
  </h3>
  <div class="table-wrap" style="max-height:640px;">
    <table>
      <thead><tr><th>Película</th><th>Año</th><th>Nota</th></tr></thead>
      <tbody>
      {% for f in best_rated %}
        <tr><td>{{ f.name }}</td><td>{{ f.year }}</td><td>{{ f.rating }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</section>

<section id="tiempo">
  <h2>Décadas y actividad</h2>
  <p class="lead">El año de estreno no es el año en que registraste la entrada en el diario.</p>
  <div class="chart">{{ charts.decades | safe }}</div>
  <div class="chart">{{ charts.diary | safe }}</div>
</section>

{% if rankings %}
<section id="personas">
  <h2>Personas</h2>
  <p class="lead">Cada película cuenta una sola vez por persona, aunque haya varios visionados.</p>
  {% if charts.directors %}<div class="chart">{{ charts.directors | safe }}</div>{% endif %}
  {% if charts.actors %}<div class="chart">{{ charts.actors | safe }}</div>{% endif %}
  {% if charts.actresses %}<div class="chart">{{ charts.actresses | safe }}</div>{% endif %}
  <p class="note">{{ rankings.directors_gender_note }}</p>
</section>

<section id="mundo">
  <h2>Países, géneros y franquicias</h2>
  <p class="lead">{{ rankings.countries_note }}</p>
  {% if charts.countries %}<div class="chart">{{ charts.countries | safe }}</div>{% endif %}
  {% if charts.genres %}<div class="chart">{{ charts.genres | safe }}</div>{% endif %}
  {% if rankings.franchises %}
  <div class="table-wrap">
    <table>
      <thead><tr><th>Franquicia</th><th>Vistas</th><th>Nota media</th><th>Puntuadas</th></tr></thead>
      <tbody>
      {% for f in rankings.franchises[:15] %}
        <tr><td>{{ f.franchise }}</td><td>{{ f.films_seen }}</td><td>{{ f.avg_rating }}</td><td>{{ f.rated }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</section>
{% endif %}

<section id="curiosidades">
  <h2>Curiosidades</h2>
  <p class="lead">Hallazgos automáticos a partir de tus datos reales.</p>
  <div class="curiosity">
  {% for c in curiosities %}
    <article><h3>{{ c.title }}</h3><p>{{ c.detail }}</p></article>
  {% endfor %}
  </div>
</section>

<section id="cobertura">
  <h2>Cobertura de metadatos</h2>
  <p class="lead">Exactitud por encima de rellenar huecos: lo no verificado queda fuera.</p>
  {% if coverage %}
  <div class="grid">
    <div class="stat"><div class="n">{{ coverage.matched_confirmed }}</div><div class="l">Confirmadas</div></div>
    <div class="stat"><div class="n">{{ coverage.matched_probable }}</div><div class="l">Probables</div></div>
    <div class="stat"><div class="n">{{ coverage.unmatched }}</div><div class="l">Sin match</div></div>
    <div class="stat"><div class="n">{{ coverage.conflict }}</div><div class="l">Conflictos</div></div>
    <div class="stat"><div class="n">{{ coverage.with_cast }}</div><div class="l">Con elenco</div></div>
    <div class="stat"><div class="n">{{ coverage.with_countries }}</div><div class="l">Con países</div></div>
  </div>
  {% if coverage.omissions %}
  <ul class="note">{% for o in coverage.omissions %}<li>{{ o }}</li>{% endfor %}</ul>
  {% endif %}
  {% endif %}
</section>
</main>
<footer>
  Informe local · Letterboxd Wrapped {{ version }} · Fuentes: exportación Letterboxd, IMDb datasets{% if coverage and coverage.sources.wikidata %}, Wikidata{% endif %}{% if coverage and coverage.sources.tmdb %}, TMDB{% endif %}.
</footer>
</body>
</html>
"""
)


def write_html(
    path: str | Path,
    export: LetterboxdExport,
    basic: dict[str, Any],
    rankings: dict[str, Any] | None,
    coverage: dict[str, Any] | None,
    curiosities: list[dict[str, str]],
    version: str = "1.0.0",
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    charts = build_all_charts(basic, rankings)
    html = TEMPLATE.render(
        username=export.username,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        resumen=basic["resumen"],
        best_rated=basic.get("best_rated") or [],
        best_rated_note=basic.get("best_rated_note"),
        charts=charts,
        rankings=rankings,
        coverage=coverage,
        curiosities=curiosities,
        version=version,
    )
    path.write_text(html, encoding="utf-8")
    return path
