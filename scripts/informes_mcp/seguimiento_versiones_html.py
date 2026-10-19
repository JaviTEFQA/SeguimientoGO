# -*- coding: utf-8 -*-
"""Convierte la salida markdown de seguimiento_versiones.py (26.11.100) en una página para claude.ai.

La página no lleva esqueleto <html>/<body> (lo pone claude.ai al publicar): un resumen por
plataforma con la barra de ejecuciones, los avisos comunes y una pestaña por plataforma con
sus tablas A (US no cerradas), B (bugs en Resolved) y C (diseño pendiente). Con --diario
añade delante la pestaña "Ejecuciones diarias" (hoy por persona, totales y desglose por label).

Uso:
    python scripts/informes_mcp/seguimiento_versiones.py android ios pcbff11 tvos chromecast > corte.md
    python scripts/informes_mcp/seguimiento_diario.py --version 26.11.100 --labels ... --solo-ejecuciones > diario.md
    python scripts/informes_mcp/seguimiento_versiones_html.py corte.md pagina.html [titulares.json] [--diario diario.md]
"""
import argparse
import json
import re
from datetime import datetime
from html import escape

_ap = argparse.ArgumentParser()
_ap.add_argument("entrada")
_ap.add_argument("salida")
_ap.add_argument("titulares", nargs="?")
_ap.add_argument("--diario", help="salida de seguimiento_diario.py --solo-ejecuciones")
_args = _ap.parse_args()
ENTRADA, SALIDA, TITULARES_JSON, DIARIO = _args.entrada, _args.salida, _args.titulares, _args.diario
JIRA = "https://jira.tid.es/browse/"

PLATS = [  # (id de pestaña, título en el md, nombre corto)
    ("android", "26.11.100 · Android", "Android"),
    ("ios", "26.11.100 · iOS", "iOS"),
    ("pc", "26.11.100 · PC Client + GoBFF", "PC + BFF"),
    ("tvos", "26.11.100 · tvOS", "tvOS"),
    ("chromecast", "26.11.100 · Chromecast", "Chromecast"),
]
# Titulares (redactados a mano en cada corte): {"global": [...], "plataformas": {id: [...]}, "notas": {id: "..."}}
# Admiten HTML en línea (<b>); las claves de Jira se enlazan solas. Sin fichero, la página sale sin titulares.
_tit = json.load(open(TITULARES_JSON, encoding="utf-8")) if TITULARES_JSON else {}
GLOBAL = _tit.get("global", [])
TITULARES = _tit.get("plataformas", {})
NOTAS = _tit.get("notas", {})

texto = open(ENTRADA, encoding="utf-8").read()
bloques = {}
for tit in [p[1] for p in PLATS]:
    m = re.search(rf"^# {re.escape(tit)}\n(.*?)(?=^# |\Z)", texto, re.S | re.M)
    bloques[tit] = m.group(1) if m else ""

RE_KEY = re.compile(r"\b((?:GO|GOMOBILE|GOSPECS|MULTISTC)-\d+)\b")
RE_CIFRA_ENLACE = re.compile(r"\[(\d+)\]\((https://jira\.tid\.es/[^)\s]+)\)")
CERR = {"resolved", "closed"}


def badge(e):
    v = e.strip().lower()
    c = "ok" if v in CERR else "bad" if v in ("impeded", "open") else "warn" if v in ("in progress", "code review") else "na"
    return f'<span class="b {c}">{escape(e.strip())}</span>'


def fmt(cab, val):
    v = val.strip()
    if v in ("—", ""):
        return '<td class="na">—</td>'
    if v.startswith("**") and v.endswith("**"):
        return f'<td><span class="b bad">{escape(v.strip("*"))}</span></td>'
    if v.startswith("*") and v.endswith("*"):
        return f'<td class="mut"><i>{escape(v.strip("*"))}</i></td>'
    if cab in ("Estado", "Estado US"):
        return f"<td>{badge(v)}</td>"
    cls = {"P": "nok", "Passed": "nok", "Hoy P": "nok", "F": "nbad", "Failed": "nbad", "Hoy F": "nbad",
           "I": "nbad", "Impeded": "nbad", "Hoy I": "nbad", "Pe": "nwarn", "Pending": "nwarn", "Sin eje.": "nmut"}.get(cab, "")
    m = RE_CIFRA_ENLACE.fullmatch(v)
    if m:  # cifra con su búsqueda de Jira (tabla A): "[n](url)"
        return f'<td class="n {cls}"><a href="{escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a></td>'
    if v.isdigit():
        return f'<td class="n {cls if v != "0" else "cero"}">{v}</td>'
    if re.fullmatch(r"[+-]?\d+(\.\d+)?%?|[+-]\d+.*|\d+ \(.*\)", v):  # porcentajes, deltas y "3 (3P·0F·0I)"
        return f'<td class="n">{escape(v.replace(".", ",") if re.fullmatch(r"\d+\.\d+%?", v) else v)}</td>'
    h = RE_KEY.sub(lambda m: f'<a href="{JIRA}{m.group(1)}">{m.group(1)}</a>', escape(v))
    cls = ' class="k"' if RE_KEY.fullmatch(v) else ""
    return f"<td{cls}>{h}</td>"


def tabla(md):
    filas = [l for l in md.splitlines() if l.startswith("|")]
    if len(filas) < 3:
        return '<p class="vacio">Nada en esta sección.</p>'
    cabs = [c.strip() for c in filas[0].strip("|").split("|")]
    quitar = {"Plat."} if len({l.split("|")[3].strip() for l in filas[2:] if len(l.split("|")) > 3}) <= 1 else set()
    th = "".join(f"<th>{escape(c)}</th>" for c in cabs if c not in quitar)
    trs = []
    for l in filas[2:]:
        vals = [c for c in l.strip().strip("|").split("|")]
        total = vals[0].strip().startswith("**")  # fila **Total** de las tablas de ejecuciones
        if total:
            vals = [x.replace("**", "") for x in vals]
        trs.append(f'<tr{" class=\"total\"" if total else ""}>' + "".join(fmt(c, v) for c, v in zip(cabs, vals) if c not in quitar) + "</tr>")
    return f'<div class="wrap"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def seccion(md, letra):
    m = re.search(rf"^## {letra}\. (.*?)\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return (m.group(1).strip(), m.group(2)) if m else ("", "")


def cifras(md):
    d = {}
    m = re.search(r"Passed (\d+).*?Failed (\d+).*?Impeded (\d+).*?Pending (\d+)", md)
    d["P"], d["F"], d["I"], d["Pe"] = (int(x) for x in m.groups()) if m else (0, 0, 0, 0)
    m = re.search(r"- US: (\d+) total", md); d["us"] = int(m.group(1)) if m else 0
    m = re.search(r"User Stories no cerradas \((\d+) de", md); d["abiertas"] = int(m.group(1)) if m else 0
    m = re.search(r"Bugs en Resolved: (\d+)", md); d["bugs"] = int(m.group(1)) if m else 0
    m = re.search(r"Diseño pendiente: (\d+) · sin asignar: (\d+)", md)
    d["dis"], d["dis_sin"] = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    return d


def barra(d):
    tot = d["P"] + d["F"] + d["I"] + d["Pe"]
    if not tot:
        return '<div class="bar vacia" role="img" aria-label="Sin ejecuciones"></div>'
    segs = "".join(f'<i class="s{k}" style="width:{d[k] * 100 / tot:.2f}%"></i>' for k in ("P", "F", "I", "Pe") if d[k])
    return f'<div class="bar" role="img" aria-label="{d["P"]} Passed, {d["F"]} Failed, {d["I"]} Impeded, {d["Pe"]} Pending">{segs}</div>'


def enlazar(t):
    return RE_KEY.sub(lambda m: f'<a href="{JIRA}{m.group(1)}">{m.group(1)}</a>', t)


tarjetas, paneles, botones = [], [], []
PRIMERA = "diario" if DIARIO else PLATS[0][0]
if DIARIO:
    dtxt = open(DIARIO, encoding="utf-8").read()

    def dsec(num):
        m = re.search(rf"^## {re.escape(num)}\. (.*?)\n(.*?)(?=^## |\Z)", dtxt, re.S | re.M)
        return (m.group(1).strip(), m.group(2)) if m else ("", "")

    def linea(prefijo):
        m = re.search(rf"^{re.escape(prefijo)}:\s*(.*)$", dtxt, re.M)
        return enlazar(escape(m.group(1))) if m else "—"

    mc = re.search(r"^Corte: (.*)$", dtxt, re.M)
    partes = []
    for num, nombre in (("1", "Ejecutadas hoy, por persona"), ("2", "Totales de la campaña por persona"),
                        ("2b", "Por plataforma (label de campaña)")):
        _, cuerpo = dsec(num)
        extra = ""
        if num == "1":
            extra = (f'<p class="nota"><b>Failed / Impeded de hoy:</b> {linea("Failed/Impeded de hoy")}</p>'
                     f'<p class="nota"><b>Sin ejecutar hoy (última ejecución):</b> {linea("Sin ejecutar hoy (última ejecución)")}</p>')
        if cuerpo:
            partes.append(f"<section><h3>{nombre}</h3>{tabla(cuerpo)}{extra}</section>")
    tits = "".join(f"<li>{enlazar(t)}</li>" for t in TITULARES.get("diario", []))
    botones.append('<button type="button" role="tab" class="tab" id="tab-diario" data-tab="diario" aria-selected="true">Ejecuciones diarias</button>')
    paneles.append(f'<div class="panel" role="tabpanel" id="panel-diario" aria-labelledby="tab-diario">'
                   f'<h2>Ejecuciones diarias · 26.11.100</h2>'
                   f'<p class="sub">{escape(mc.group(1)) if mc else ""} · comparación con el día laborable anterior a la misma hora</p>'
                   f'{f"<ul class=\"tit\">{tits}</ul>" if tits else ""}{"".join(partes)}</div>')

for i, (pid, tit, corto) in enumerate(PLATS):
    md = bloques[tit]
    d = cifras(md)
    tot = d["P"] + d["F"] + d["I"] + d["Pe"]
    pct = f'{d["P"] * 100 / tot:.1f}'.replace(".", ",") + " %" if tot else "—"
    tarjetas.append(f'''<button class="card" type="button" data-tab="{pid}" id="card-{pid}">
<span class="cn">{corto}</span>
<span class="big">{pct}<small> Passed</small></span>
{barra(d)}
<span class="meta">{tot} ejecuciones · {d["P"]} P · {d["F"]} F · {d["I"]} I · {d["Pe"]} Pe</span>
<dl><div><dt>US abiertas</dt><dd>{d["abiertas"]} / {d["us"]}</dd></div><div><dt>Bugs Resolved</dt><dd>{d["bugs"]}</dd></div>
<div><dt>Diseño pendiente</dt><dd>{d["dis"]}{f' <em>({d["dis_sin"]} sin asignar)</em>' if d["dis_sin"] else ""}</dd></div></dl></button>''')
    botones.append(f'<button type="button" role="tab" class="tab" id="tab-{pid}" data-tab="{pid}" aria-selected="{"true" if pid == PRIMERA else "false"}">{corto}</button>')
    secs = []
    for letra, nombre in (("A", "User Stories no cerradas"), ("B", "Bugs y Sub-Bugs en Resolved"), ("C", "Diseño de pruebas pendiente")):
        t, cuerpo = seccion(md, letra)
        n = re.search(r"\(([^)]*)\)\s*$", t)
        nota = f'<p class="nota">{escape(NOTAS[pid])}</p>' if letra == "B" and pid in NOTAS else ""
        secs.append(f'<section><h3>{nombre} <span class="cnt">{escape(n.group(1)) if n else ""}</span></h3>{tabla(cuerpo)}{nota}</section>')
    tits = "".join(f"<li>{RE_KEY.sub(lambda m: f'<a href=\"{JIRA}{m.group(1)}\">{m.group(1)}</a>', t)}</li>" for t in TITULARES.get(pid, []))
    paneles.append(f'<div class="panel" role="tabpanel" id="panel-{pid}" aria-labelledby="tab-{pid}"{"" if pid == PRIMERA else " hidden"}>'
                   f'<h2>{escape(tit)}</h2>{f'<ul class="tit">{tits}</ul>' if tits else ""}{"".join(secs)}</div>')

corte = datetime.now().strftime("%d/%m/%Y %H:%M")

html = f"""<title>Seguimiento 26.11.100</title>
<style>
/* Layout: cinco tarjetas de plataforma (resumen y acceso), avisos comunes y una pestaña por plataforma con sus tablas */
:root{{--bg:#f4f6f8;--card:#fff;--fg:#1b2230;--mut:#5f6879;--line:#dfe3e9;--acc:#2754c5;--accbg:#e8eefc;
--ok:#e3f4e8;--okf:#13703a;--warn:#fff2d4;--warnf:#855700;--bad:#fde6e4;--badf:#b42318;--na:#eceff3;--naf:#4f5869;
--sP:#2f9e5b;--sF:#d6453b;--sI:#e08a1e;--sPe:#c9ced8;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,"Cascadia Mono",Consolas,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#11141a;--card:#191e27;--fg:#e4e8ef;--mut:#98a1b1;--line:#2a313d;--acc:#8fb0ff;--accbg:#1c2744;
--ok:#133420;--okf:#7fdc9c;--warn:#372a0e;--warnf:#f2c46b;--bad:#3b1918;--badf:#f59a96;--na:#242a34;--naf:#b3bbca;--sP:#4cc27e;--sF:#ef6b60;--sI:#f0a43f;--sPe:#4a5262;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#11141a;--card:#191e27;--fg:#e4e8ef;--mut:#98a1b1;--line:#2a313d;--acc:#8fb0ff;--accbg:#1c2744;
--ok:#133420;--okf:#7fdc9c;--warn:#372a0e;--warnf:#f2c46b;--bad:#3b1918;--badf:#f59a96;--na:#242a34;--naf:#b3bbca;--sP:#4cc27e;--sF:#ef6b60;--sI:#f0a43f;--sPe:#4a5262;color-scheme:dark}}
*{{box-sizing:border-box}}body{{background:var(--bg);color:var(--fg);font:14px/1.45 var(--sans)}}
main{{max-width:1280px;margin:0 auto;padding-inline:16px;padding-block:24px 48px;display:grid;gap:20px}}
h1{{font-size:24px;margin:0;text-wrap:balance}}h2{{font-size:18px;margin:0}}h3{{font-size:15px;margin:0 0 8px;display:flex;gap:8px;align-items:baseline}}
.sub{{color:var(--mut);margin:4px 0 0}}.cnt{{color:var(--mut);font-weight:400;font-variant-numeric:tabular-nums}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}
.card{{all:unset;box-sizing:border-box;cursor:pointer;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;display:grid;gap:8px;min-width:0}}
.card:hover{{border-color:var(--acc)}}.card:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}.card.on{{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc)}}
.cn{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);font-weight:600}}
.big{{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}}.big small{{font-size:13px;font-weight:500;color:var(--mut)}}
.bar{{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--sPe)}}.bar i{{display:block;height:100%}}.bar.vacia{{background:var(--na)}}
.sP{{background:var(--sP)}}.sF{{background:var(--sF)}}.sI{{background:var(--sI)}}.sPe{{background:var(--sPe)}}
.meta{{font-size:12px;color:var(--mut);font-variant-numeric:tabular-nums}}
dl{{margin:0;display:grid;gap:3px}}dl div{{display:flex;justify-content:space-between;gap:8px}}dt{{color:var(--mut)}}dd{{margin:0;font-weight:600;font-variant-numeric:tabular-nums;text-align:right}}dd em{{font-style:normal;font-weight:500;color:var(--badf)}}
.leyenda{{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--mut)}}.leyenda span{{display:inline-flex;align-items:center;gap:6px}}.leyenda i{{width:10px;height:10px;border-radius:2px;display:inline-block}}
.comun{{background:var(--accbg);border-radius:10px;padding:14px 16px}}.comun h2{{font-size:15px;margin-bottom:6px}}.comun ul,.tit{{margin:0;padding-left:18px;display:grid;gap:5px}}
.tabs{{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line)}}
.tab{{all:unset;cursor:pointer;padding:8px 14px;border-radius:8px 8px 0 0;color:var(--mut);font-weight:600}}.tab:hover{{color:var(--fg)}}
.tab[aria-selected="true"]{{color:var(--acc);box-shadow:inset 0 -2px 0 var(--acc)}}.tab:focus-visible{{outline:2px solid var(--acc)}}
.panel{{display:grid;gap:18px}}.tit{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px 12px 32px}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;min-width:860px}}th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}tbody tr:last-child td{{border-bottom:0}}
th{{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);white-space:nowrap}}
td.k{{font-family:var(--mono);font-size:12.5px;white-space:nowrap}}td.n{{text-align:right;font-variant-numeric:tabular-nums}}td.cero{{color:var(--mut);opacity:.55;text-align:right}}
td.nok{{color:var(--okf);font-weight:700}}td.nbad{{color:var(--badf);font-weight:700}}td.nwarn{{color:var(--warnf)}}td.nmut{{color:var(--mut)}}td.na,td.mut{{color:var(--mut)}}
a{{color:var(--acc);text-decoration:none}}a:hover,a:focus-visible{{text-decoration:underline}}
.b{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}}
.ok{{background:var(--ok);color:var(--okf)}}.warn{{background:var(--warn);color:var(--warnf)}}.bad{{background:var(--bad);color:var(--badf)}}.na{{background:var(--na);color:var(--naf)}}
.vacio,.nota{{color:var(--mut);margin:0;font-size:13px}}.nota{{margin-top:6px}}.nota b{{color:var(--fg)}}
tr.total td{{font-weight:700;border-top:2px solid var(--line)}}
@media (prefers-reduced-motion:no-preference){{.card,.tab{{transition:border-color .15s,color .15s}}}}
</style>
<main>
<header><h1>Seguimiento de la 26.11.100</h1>
<p class="sub">Android, iOS, PC + BFF, tvOS y Chromecast por separado · corte del {corte} · las US cuentan como diseñadas con la subtarea en Closed o Resolved</p></header>
<div class="cards">{"".join(tarjetas)}</div>
<div class="leyenda"><span><i class="sP"></i>Passed</span><span><i class="sF"></i>Failed</span><span><i class="sI"></i>Impeded</span><span><i class="sPe"></i>Pending</span></div>
{f'<section class="comun"><h2>Afecta a todas las plataformas</h2><ul>{"".join(f"<li>{g}</li>" for g in GLOBAL)}</ul></section>' if GLOBAL else ""}
<div class="tabs" role="tablist" aria-label="Plataforma">{"".join(botones)}</div>
{"".join(paneles)}
</main>
<script>
(function(){{
  var ids={(["diario"] if DIARIO else []) + [p[0] for p in PLATS]};
  function show(id){{
    if(ids.indexOf(id)<0) id=ids[0];
    ids.forEach(function(x){{
      document.getElementById('panel-'+x).hidden = x!==id;
      document.getElementById('tab-'+x).setAttribute('aria-selected', x===id ? 'true':'false');
      var c=document.getElementById('card-'+x); if(c) c.classList.toggle('on', x===id);
    }});
  }}
  document.querySelectorAll('[data-tab]').forEach(function(b){{
    b.addEventListener('click', function(){{
      show(b.dataset.tab);
      if(b.classList.contains('card')) document.getElementById('tab-'+b.dataset.tab).scrollIntoView({{block:'start', behavior:'smooth'}});
    }});
  }});
  show((location.hash||'').slice(1));
}})();
</script>
"""
open(SALIDA, "w", encoding="utf-8").write(html)
print("OK", len(html), "bytes")
