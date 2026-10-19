#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado de las User Stories de una versión y de una de sus subtareas.

Por defecto la subtarea es [DEV] Acceptance tests; con --subtarea se elige otra
(p. ej. "[QA] US Test Design"). Consulta Jira por la REST API (token de .env) e
imprime en markdown un resumen y una tabla por US con su plataforma, su estado y
el estado y assignee de la subtarea. Con --html escribe además una página HTML
sin esqueleto <html>/<body>, lista para publicarla como artifact de claude.ai.

Uso:
    python scripts/informes_mcp/us_acceptance_tests.py [--version 26.11.100]
        [--subtarea "[QA] US Test Design"] [--html ruta.html]
"""
import argparse
import sys
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from jira_tc_report import jira_search  # noqa: E402

JIRA = "https://jira.tid.es/browse/"
DEV_ACCEPTANCE = "[DEV] Acceptance tests"
# Nombre corto para títulos y cabeceras; si la subtarea no está aquí se usa su summary sin el prefijo [XX]
ROTULOS = {DEV_ACCEPTANCE: "Acceptance tests", "[QA] US Test Design": "Diseño QA",
           "[QA] US Test Execution": "Ejecución QA"}
PLATAFORMAS = [("Mobile Android", "Android"), ("Mobile iOS", "iOS"), ("tvOS", "tvOS"),
               ("PC Client", "Web"), ("GoBFF", "BFF"), ("Chromecast", "Chromecast")]
# Orden de presentación: primero lo que bloquea, al final lo cerrado
ORDEN_ESTADO = {"impeded": 0, "open": 1, "in progress": 2, "code review": 3, "resolved": 4, "closed": 5}


def rotulo(nombre):
    return ROTULOS.get(nombre) or nombre.split("]", 1)[-1].strip() or nombre


def buscar_subtarea(issue, nombre):
    """Subtarea de la US cuyo summary contiene `nombre`; si hay clones se prefiere la original."""
    subs = [s for s in issue["fields"].get("subtasks", []) if nombre in s["fields"]["summary"]]
    subs.sort(key=lambda s: s["fields"]["summary"].strip() != nombre)
    return subs[0] if subs else None


def assignees(claves):
    """{clave: displayName} de las subtareas (el campo subtasks no trae el assignee)."""
    res = {}
    claves = list(claves)
    for i in range(0, len(claves), 100):
        for s in jira_search(f'key in ({",".join(claves[i:i + 100])})', ["assignee"]):
            a = s["fields"].get("assignee")
            res[s["key"]] = a["displayName"] if a else None
    return res


def celda(texto):
    return " ".join(str(texto).split()).replace("|", "\\|")


CERRADO = {"resolved", "closed"}
CSS = """
/* Layout: cabecera con cifras, tres avisos y la tabla completa en su propio scroll horizontal */
:root{--bg:#f5f6f8;--card:#fff;--fg:#1c2230;--mut:#626b7d;--line:#e1e4ea;--ok:#e5f5ea;--okf:#16703a;--warn:#fff3d6;--warnf:#865800;--bad:#fde7e6;--badf:#b42318;--na:#eceef2;--naf:#4f5869;--link:#1d5fc4;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,"Cascadia Mono",Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12151b;--card:#1a1f28;--fg:#e5e8ee;--mut:#99a2b2;--line:#2b323e;--ok:#143520;--okf:#7fdc9c;--warn:#382b0f;--warnf:#f3c46c;--bad:#3c1a19;--badf:#f59b97;--na:#252b35;--naf:#b4bccb;--link:#8fb4ff;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12151b;--card:#1a1f28;--fg:#e5e8ee;--mut:#99a2b2;--line:#2b323e;--ok:#143520;--okf:#7fdc9c;--warn:#382b0f;--warnf:#f3c46c;--bad:#3c1a19;--badf:#f59b97;--na:#252b35;--naf:#b4bccb;--link:#8fb4ff;color-scheme:dark}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font:14px/1.45 var(--sans)}
main{max-width:1240px;margin:0 auto;padding-inline:16px;padding-block:24px 40px;display:grid;gap:20px}
h1{font-size:22px;margin:0;text-wrap:balance}h2{font-size:15px;margin:0 0 8px}.sub{color:var(--mut);margin:4px 0 0}
.resumen{display:flex;flex-wrap:wrap;gap:16px}.grupo{display:grid;gap:6px;min-width:0}.grupo>span{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{padding:3px 10px;border-radius:999px;font-size:13px;background:var(--na);color:var(--naf)}.chip b{font-variant-numeric:tabular-nums}
.avisos{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.aviso{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;min-width:0}.aviso ul{margin:0;padding-left:18px;display:grid;gap:4px}.aviso p{margin:0;color:var(--mut)}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:980px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}td.k{font-family:var(--mono);font-size:13px;white-space:nowrap}td.t{max-width:420px}
a{color:var(--link);text-decoration:none}a:hover,a:focus-visible{text-decoration:underline}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.ok{background:var(--ok);color:var(--okf)}.warn{background:var(--warn);color:var(--warnf)}.bad{background:var(--bad);color:var(--badf)}.na,.us{background:var(--na);color:var(--naf)}
.nota{color:var(--mut);font-size:13px;margin:0}
"""


def clase(estado):
    """Color del estado: ok (cerrado), warn (en curso), bad (bloqueado o sin empezar), na (sin subtarea)."""
    e = (estado or "").lower()
    return "na" if not e else "ok" if e in CERRADO else "bad" if e in ("impeded", "open") else "warn"


def render_html(version, nombre, filas, qa):
    corto = rotulo(nombre)
    con = [r for r in filas if r["sub"]]
    # Desarrollo entregado (US Resolved/Closed) con la subtarea bloqueada o sin empezar
    pendientes = [r for r in con if r["estado"].lower() in CERRADO and clase(r["sub_estado"]) == "bad"]
    sin_asignar = [r for r in con if not qa.get(r["sub"])]
    sin_sub = Counter(r["plat"] for r in filas if not r["sub"])

    def enlace(k):
        return f'<a href="{JIRA}{k}">{k}</a>'

    def badge(estado):
        return f'<span class="b {clase(estado)}">{escape(estado or "Sin subtarea")}</span>'

    def lista(rs):
        items = [f"<li>{enlace(r['key'])} {escape(r['plat'])} · {escape(celda(r['summary'])[:70])} {badge(r['sub_estado'])}</li>"
                 for r in rs]
        return "".join(items) or "<li>Ninguna</li>"

    chips_sub = "".join(f'<span class="chip {clase(e)}">{escape(e)} <b>{n}</b></span>'
                        for e, n in Counter(r["sub_estado"] for r in con).most_common())
    chips_us = "".join(f'<span class="chip">{escape(e)} <b>{n}</b></span>'
                       for e, n in Counter(r["estado"] for r in filas).most_common())
    trs = []
    for r in filas:
        a = qa.get(r["sub"])
        asignada = escape(a) if a else ("<i>sin asignar</i>" if r["sub"] else "—")
        trs.append(f'<tr><td class="k">{enlace(r["key"])}</td><td>{escape(r["plat"])}</td>'
                   f'<td><span class="b us">{escape(r["estado"])}</span></td><td class="t">{escape(celda(r["summary"]))}</td>'
                   f'<td class="k">{enlace(r["sub"]) if r["sub"] else "—"}</td><td>{badge(r["sub_estado"])}</td>'
                   f'<td>{asignada}</td></tr>')
    resumen_sin = ", ".join(f"{escape(p)} {n}" for p, n in sin_sub.most_common())
    return f"""<title>{escape(corto)} {version}</title>
<style>{CSS}</style>
<main>
<header><h1>US de la {version} y su subtarea {escape(nombre)}</h1>
<p class="sub">{len(filas)} User Stories de GO y GOMOBILE · {len(con)} con la subtarea · {len(filas) - len(con)} sin ella · corte del {datetime.now():%d/%m/%Y %H:%M}</p></header>
<section class="resumen">
<div class="grupo"><span>Estado de la subtarea</span><div class="chips">{chips_sub}</div></div>
<div class="grupo"><span>Estado de las US</span><div class="chips">{chips_us}</div></div>
</section>
<section class="avisos">
<div class="aviso"><h2>US entregadas con {escape(corto)} sin cerrar ({len(pendientes)})</h2><ul>{lista(pendientes)}</ul></div>
<div class="aviso"><h2>Subtareas sin asignar ({len(sin_asignar)})</h2><ul>{lista(sin_asignar)}</ul></div>
<div class="aviso"><h2>US sin la subtarea ({sum(sin_sub.values())})</h2><p>{resumen_sin}. No todas las US la llevan.</p></div>
</section>
<div class="wrap"><table><thead><tr><th>US</th><th>Plataforma</th><th>Estado US</th><th>Asunto</th><th>{escape(corto)}</th><th>Estado subtarea</th><th>Asignada a</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div>
<p class="nota">Orden: primero las subtareas bloqueadas o sin empezar, después las cerradas y al final las US sin subtarea. Fuente: User Stories de GO y GOMOBILE con fixVersion {version}.</p>
</main>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="26.11.100")
    ap.add_argument("--subtarea", default=DEV_ACCEPTANCE, help='summary de la subtarea, p. ej. "[QA] US Test Design"')
    ap.add_argument("--html", help="además, escribe la página HTML en esta ruta")
    args = ap.parse_args()
    version, nombre = args.version, args.subtarea

    jql = (f'(project = "GO" OR project = "GOMOBILE") AND fixVersion = "{version}" '
           'AND resolution in (EMPTY, Fixed, Done) AND issuetype = "User Story"')
    us = jira_search(jql, ["summary", "status", "components", "subtasks"])

    filas = []
    for u in us:
        f = u["fields"]
        comps = {c["name"] for c in f["components"]}
        plat = ", ".join(col for comp, col in PLATAFORMAS if comp in comps) or "—"
        st = buscar_subtarea(u, nombre)
        filas.append({"key": u["key"], "plat": plat, "estado": f["status"]["name"], "summary": f["summary"],
                      "sub": st["key"] if st else None, "sub_estado": st["fields"]["status"]["name"] if st else None})
    qa = assignees(r["sub"] for r in filas if r["sub"])

    filas.sort(key=lambda r: (r["sub"] is None, ORDEN_ESTADO.get((r["sub_estado"] or "").lower(), 9),
                              r["plat"], r["key"]))

    con = [r for r in filas if r["sub"]]
    print(f"# US de la {version} y su subtarea {nombre}\n")
    print(f"- US: **{len(filas)}** · con la subtarea: **{len(con)}** · sin ella: **{len(filas) - len(con)}**")
    print("- Estado de las US: " + ", ".join(f"{e} {n}" for e, n in Counter(r["estado"] for r in filas).most_common()))
    print("- Estado de la subtarea: " + ", ".join(f"{e} {n}" for e, n in Counter(r["sub_estado"] for r in con).most_common()))
    print(f"\n| US | Plataforma | Estado US | Asunto | {rotulo(nombre)} | Estado subtarea | Asignada a |")
    print("|---|---|---|---|---|---|---|")
    for r in filas:
        sub = f"[{r['sub']}]({JIRA}{r['sub']})" if r["sub"] else "—"
        print(f"| [{r['key']}]({JIRA}{r['key']}) | {r['plat']} | {r['estado']} | {celda(r['summary'])[:80]} | {sub} | "
              f"{r['sub_estado'] or 'Sin subtarea'} | {celda(qa.get(r['sub']) or ('sin asignar' if r['sub'] else '—'))} |")
    if args.html:
        Path(args.html).write_text(render_html(version, nombre, filas, qa), encoding="utf-8")
        print(f"\nHTML: {args.html}")


if __name__ == "__main__":
    main()
