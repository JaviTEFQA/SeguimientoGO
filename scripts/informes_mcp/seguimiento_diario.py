#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seguimiento diario de la campaña (lo que se pide con "actualiza datos").

Consulta Jira por REST (token de .env) y vuelca por consola:
  1. Ejecuciones de hoy por persona frente al día laborable anterior completo.
  2. Totales de la campaña por persona, ahora y al cierre del día anterior.
  3. Bugs y Sub-Bugs que han pasado a Resolved desde el día anterior.
  4. User Stories de la versión (PC Client + GoBFF) que no están Closed, con
     su estado, el dueño de la subtarea [QA] US Test Execution, el avance de
     sus TCs y los sub-bugs sin cerrar.
  5. User Stories cerradas desde el día anterior.

El dueño de una ejecución sin assignee se hereda de la subtarea
[QA] US Test Execution de su US (ejecución -> TC -> US -> subtarea).

Uso:
    python scripts/informes_mcp/seguimiento_diario.py
    python scripts/informes_mcp/seguimiento_diario.py --version 26.11.100 \\
        --labels CC_26.11.100_Android CC_26.11.100_iOS CC_26.11.100_tvOS CC_26.11.100_Web CC_26.11.100_BFF \\
        --solo-ejecuciones

Con varios labels añade el desglose por label (2b). --solo-ejecuciones se queda en las
secciones 1, 2 y 2b (sin bugs ni US, que en la 26.11 salen de seguimiento_versiones.py).
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jira_tc_report import JIRA_BASE_URL, SSL_VERIFY, get_headers  # noqa: E402
from refrescar_datos import nombre, subtareas_qa, test_cases, trozos  # noqa: E402

VERSION = "26.10.100"
LABELS = ("CC_26.10.100_Web", "CC_26.10.100_BFF")
TIPOS_BUG = '(Bug, Sub-Bug, "Bug SubTask")'
ESTADOS = ["Passed", "Failed", "Impeded", "Pending"]
# Festivos nacionales/Madrid que no cuentan como día laborable anterior
FESTIVOS = {"2026-10-12", "2026-11-02", "2026-11-09", "2026-12-07", "2026-12-08", "2026-12-25"}


def buscar(jql, fields, expand=None):
    """Búsqueda JQL paginada, con expand opcional (changelog)."""
    out, start = [], 0
    while True:
        params = {"jql": jql, "fields": ",".join(fields), "maxResults": 100, "startAt": start}
        if expand:
            params["expand"] = expand
        r = requests.get(f"{JIRA_BASE_URL}/rest/api/2/search", headers=get_headers(),
                         params=params, verify=SSL_VERIFY, timeout=60)
        r.raise_for_status()
        d = r.json()
        out += d["issues"]
        start += len(d["issues"])
        if not d["issues"] or start >= d["total"]:
            return out


def fecha(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z")


def transiciones(issue):
    """[(cuándo, desde, hasta)] de los cambios de estado, ordenados."""
    return sorted((fecha(h["created"]), it["fromString"], it["toString"])
                  for h in issue.get("changelog", {}).get("histories", [])
                  for it in h["items"] if it["field"] == "status")


def estado_en(issue, tr, momento):
    if fecha(issue["fields"]["created"]) > momento:
        return None
    st = tr[0][1] if tr else issue["fields"]["status"]["name"]
    for cuando, _, a in tr:
        if cuando <= momento:
            st = a
    return st


def corto(texto, n=70):
    return " ".join((texto or "").split())[:n]


def tabla(cab, filas):
    print("| " + " | ".join(cab) + " |")
    print("|" + "---|" * len(cab))
    for f in filas:
        print("| " + " | ".join(str(c) for c in f) + " |")
    print()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=VERSION)
    ap.add_argument("--labels", nargs="+", default=list(LABELS), help="labels de campaña de las ejecuciones")
    ap.add_argument("--solo-ejecuciones", action="store_true", help="solo las secciones 1, 2 y 2b")
    args = ap.parse_args()
    version, labels = args.version, args.labels
    ahora = datetime.now().astimezone()
    hoy0 = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    ant0 = hoy0 - timedelta(days=1)
    while ant0.weekday() >= 5 or f"{ant0:%Y-%m-%d}" in FESTIVOS:  # último laborable
        ant0 -= timedelta(days=1)
    ant1 = ant0 + timedelta(days=1)
    ant_hora = ant0 + (ahora - hoy0)  # misma hora del día anterior
    print(f"Corte: {ahora:%A %d/%m/%Y %H:%M} | día anterior: {ant0:%A %d/%m/%Y}\n")

    # ── US de la versión, sus TCs y sus subtareas QA ──────────────────────────
    us = buscar(f'(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story"'
                f' AND fixVersion = "{version}"', ["summary", "status", "components", "issuelinks"])
    subs = subtareas_qa([u["key"] for u in us])
    dueño = {k: nombre(v["eje"][0]["fields"].get("assignee")).title()
             for k, v in subs.items() if v["eje"]}
    us_de_tc = defaultdict(list)
    for u in us:
        for tc in test_cases(u["fields"]):
            us_de_tc[tc].append(u["key"])

    # ── Ejecuciones de la campaña con changelog ───────────────────────────────
    ejes = buscar(f"labels in ({', '.join(labels)})",
                  ["status", "assignee", "parent", "labels", "created", "updated", "issuelinks"], "changelog")

    def persona(e):
        a = nombre(e["fields"].get("assignee"))
        if a:
            return a.title()
        for k in us_de_tc.get(e["fields"]["parent"]["key"], []):
            if dueño.get(k):
                return dueño[k]
        return "Sin asignar"

    dia = {"hoy": defaultdict(Counter), "ant": defaultdict(Counter), "ant_hora": defaultdict(Counter)}
    camp = {"hoy": defaultdict(Counter), "ant": defaultdict(Counter)}
    # Lo mismo agregado por label de campaña, para el desglose 2b
    por_label = {"hoy": defaultdict(Counter), "ant_hora": defaultdict(Counter), "camp": defaultdict(Counter)}
    rojos, ult_eje = [], {}
    for e in ejes:
        tr, who, now = transiciones(e), persona(e), e["fields"]["status"]["name"]
        lab = next((l for l in e["fields"]["labels"] if l in labels), "—")
        camp["hoy"][who][now] += 1
        por_label["camp"][lab][now] += 1
        st_ant = estado_en(e, tr, ant1)
        if st_ant:
            camp["ant"][who][st_ant] += 1
        if tr and tr[-1][0] >= hoy0 and now != "Pending":
            dia["hoy"][who][now] += 1
            por_label["hoy"][lab][now] += 1
            if now in ("Failed", "Impeded"):
                rojos.append((e["key"], e["fields"]["parent"]["key"], now, who))
        if any(ant0 <= x[0] < ant1 for x in tr) and st_ant != "Pending":
            dia["ant"][who][st_ant] += 1
        st_hora = estado_en(e, tr, ant_hora)
        if any(ant0 <= x[0] < ant_hora for x in tr) and st_hora not in (None, "Pending"):
            dia["ant_hora"][who][st_hora] += 1
            por_label["ant_hora"][lab][st_hora] += 1
        hechas = [x[0] for x in tr if x[2] != "Pending"]
        if hechas:
            ult_eje[who] = max(ult_eje.get(who, hechas[0]), max(hechas))

    # 1. Ejecutadas hoy
    print("## 1. Ejecutadas hoy, por persona\n")
    gente = sorted(set(dia["hoy"]) | set(dia["ant"]) | set(dia["ant_hora"]), key=lambda w: -sum(dia["hoy"][w].values()))

    def resumen(c):
        n = sum(c.values())
        return f"{n} ({c['Passed']}P·{c['Failed']}F·{c['Impeded']}I)" if n else "0"

    filas, th, ta, tm = [], Counter(), Counter(), Counter()
    for w in gente:
        h, a, m = dia["hoy"][w], dia["ant"][w], dia["ant_hora"][w]
        th += h; ta += a; tm += m
        n = sum(h.values())
        filas.append([w, h["Passed"], h["Failed"], h["Impeded"], n,
                      f"{100 * h['Passed'] / n:.1f}%" if n else "—",
                      resumen(m), f"{n - sum(m.values()):+d}", sum(a.values())])
    n = sum(th.values())
    filas.append(["**Total**", th["Passed"], th["Failed"], th["Impeded"], n,
                  f"{100 * th['Passed'] / n:.1f}%" if n else "—",
                  resumen(tm), f"{n - sum(tm.values()):+d}", sum(ta.values())])
    tabla(["Persona", "Passed", "Failed", "Impeded", "Total", "% Passed",
           f"{ant0:%a} hasta {ant_hora:%H:%M}", "Δ misma hora", f"{ant0:%a %d/%m} completo"], filas)
    print("Failed/Impeded de hoy:", ", ".join(f"{k} (TC {tc}, {st}, {w})" for k, tc, st, w in rojos) or "—")
    activos_hoy = {w for w, c in dia["hoy"].items() if sum(c.values())}
    print("Sin ejecutar hoy (última ejecución):",
          ", ".join(f"{w} ({ult_eje[w]:%d/%m %H:%M})" for w in sorted(ult_eje)
                    if w not in activos_hoy and w != "Sin asignar" and ult_eje[w] >= hoy0 - timedelta(days=15)) or "—")
    print()

    # 2. Totales de campaña
    print("## 2. Totales de la campaña (porcentajes sobre el total)\n")
    gente = sorted(camp["hoy"], key=lambda w: -sum(camp["hoy"][w].values()))
    filas, th, ta = [], Counter(), Counter()
    for w in gente + ["**Total**"]:
        h = th if w == "**Total**" else camp["hoy"][w]
        a = ta if w == "**Total**" else camp["ant"][w]
        if w != "**Total**":
            th += h; ta += a
        n = sum(h.values())
        delta = ", ".join(f"{h[s] - a[s]:+d} {s[:2] if s == 'Pending' else s[0]}" for s in ESTADOS if h[s] != a[s]) or "="
        filas.append([w, *[h[s] for s in ESTADOS], n, *[f"{100 * h[s] / n:.1f}" for s in ESTADOS], delta])
    tabla(["Persona", *ESTADOS, "Total", "% P", "% F", "% I", "% Pe", f"Δ desde cierre {ant0:%a}"], filas)

    # 2b. Desglose por label (solo si hay varios)
    if len(labels) > 1:
        print("## 2b. Por plataforma (label de campaña)\n")
        filas = []
        for lab in labels:
            h, m, c = por_label["hoy"][lab], por_label["ant_hora"][lab], por_label["camp"][lab]
            n, tot = sum(h.values()), sum(c.values())
            filas.append([lab, h["Passed"], h["Failed"], h["Impeded"], n, sum(m.values()), f"{n - sum(m.values()):+d}",
                          *[c[s] for s in ESTADOS], tot, f"{100 * c['Passed'] / tot:.1f}" if tot else "—"])
        tabla(["Label", "Hoy P", "Hoy F", "Hoy I", "Hoy total", f"{ant0:%a} hasta {ant_hora:%H:%M}", "Δ misma hora",
               *ESTADOS, "Total campaña", "% P"], filas)
    if args.solo_ejecuciones:
        return

    # 3. Bugs a Resolved
    print(f"## 3. Bugs y Sub-Bugs a Resolved desde {ant0:%a %d/%m}\n")
    detectados = {l["outwardIssue"]["key"] for e in ejes for l in e["fields"].get("issuelinks") or []
                  if "outwardIssue" in l and l["type"]["outward"] == "detects"}
    us_keys = [u["key"] for u in us]
    jql = (f'issuetype in {TIPOS_BUG} AND status CHANGED TO Resolved AFTER "{(ant0 - timedelta(days=1)):%Y-%m-%d}"'
           f' AND (fixVersion = "{version}"' +(f' OR key in ({",".join(sorted(detectados))})' if detectados else "") + ")")
    bugs = {b["key"]: b for b in buscar(jql, ["summary", "issuetype", "status", "parent", "components", "reporter"], "changelog")}
    for bloque in trozos(us_keys):  # sub-bugs sin fixVersion pero colgando de US de la versión
        for b in buscar(f'issuetype in {TIPOS_BUG} AND parent in ({",".join(bloque)}) AND status CHANGED TO Resolved'
                        f' AFTER "{(ant0 - timedelta(days=1)):%Y-%m-%d}"',
                        ["summary", "issuetype", "status", "parent", "components", "reporter"], "changelog"):
            bugs[b["key"]] = b
    filas = []
    for b in bugs.values():
        f = b["fields"]
        cuando = max((w for w, _, a in transiciones(b) if a == "Resolved"), default=None)
        if not cuando or cuando < ant0:
            continue
        par = (f.get("parent") or {}).get("key", "")
        filas.append((cuando, [("hoy " if cuando >= hoy0 else f"{cuando:%a} ") + f"{cuando:%H:%M}", b["key"],
                               f["issuetype"]["name"], f["status"]["name"],
                               ",".join(c["name"] for c in f["components"]), par or "—",
                               dueño.get(par, "—") if par else f"reporter: {nombre(f.get('reporter')).title()}", corto(f["summary"])]))
    tabla(["Resolved", "Bug", "Tipo", "Estado actual", "Comp.", "US padre", "Verifica", "Asunto"],
          [f for _, f in sorted(filas, key=lambda x: x[0], reverse=True)])

    # 4. US no cerradas (PC Client + GoBFF)
    print("## 4. User Stories no cerradas (PC Client + GoBFF)\n")
    abiertas = [u for u in us if u["fields"]["status"]["name"] != "Closed"
                and any(c["name"] in ("PC Client", "GoBFF") for c in u["fields"]["components"])]
    tcs = sorted({t for u in abiertas for t in test_cases(u["fields"])})
    ult = {}
    for e in ejes:
        tc = e["fields"]["parent"]["key"]
        if tc not in ult or ult[tc][1] < e["fields"]["updated"]:
            ult[tc] = (e["fields"]["status"]["name"], e["fields"]["updated"])
    hijos = defaultdict(list)
    for bloque in trozos([u["key"] for u in abiertas]):
        for s in buscar(f'issuetype in {TIPOS_BUG} AND parent in ({",".join(bloque)}) AND status != Closed',
                        ["status", "parent"]):
            hijos[s["fields"]["parent"]["key"]].append(f'{s["key"]} ({s["fields"]["status"]["name"]})')
    # Bugs enlazados con "detects" que cuelgan de otra US (p. ej. un sub-bug de la US Web
    # que también rompe la US de BFF): se marcan con la US de la que son hijos
    for u in abiertas:
        for l in u["fields"].get("issuelinks", []):
            o = l.get("outwardIssue") or l.get("inwardIssue")
            if l["type"]["outward"] != "detects" or not o \
                    or o["fields"]["issuetype"]["name"] not in ("Bug", "Sub-Bug", "Bug SubTask") \
                    or o["fields"]["status"]["name"] == "Closed" \
                    or any(h.startswith(o["key"] + " ") for h in hijos[u["key"]]):
                continue
            hijos[u["key"]].append(f'{o["key"]} ({o["fields"]["status"]["name"]}, enlazado)')
    orden ={"Resolved": 0, "Reopened": 1, "Impeded": 2, "Code Review": 3, "In Progress": 4}
    filas = []
    for u in sorted(abiertas, key=lambda u: (orden.get(u["fields"]["status"]["name"], 9), dueño.get(u["key"], ""), u["key"])):
        f = u["fields"]
        c = Counter(ult.get(t, ("Sin ejecución",))[0] for t in test_cases(f))
        n = sum(c.values())
        avance = f'{c["Passed"]}/{n}' + "".join(f' {c[s]}{s[0]}' for s in ("Failed", "Impeded") if c[s]) \
            + (f' {c["Pending"] + c["Sin ejecución"]}Pe' if c["Pending"] + c["Sin ejecución"] else "")
        comp = "Web" if any(x["name"] == "PC Client" for x in f["components"]) else "BFF"
        filas.append([u["key"], f["status"]["name"], comp, corto(f["summary"], 60), dueño.get(u["key"]) or "*sin asignar*",
                      avance if n else "sin TCs", ", ".join(hijos[u["key"]]) or "—"])
    tabla(["US", "Estado", "Plat.", "Asunto", "QA ejecución", "TCs (Passed/total)", "Sub-bugs sin cerrar"], filas)

    # 5. US cerradas
    print(f"## 5. User Stories cerradas desde {ant0:%a %d/%m}\n")
    cerr = buscar(f'(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story"'
                  f' AND status CHANGED TO Closed AFTER "{(ant0 - timedelta(days=1)):%Y-%m-%d}"',
                  ["summary", "components", "fixVersions"], "changelog")
    filas = []
    for u in cerr:
        h = max((h for h in u["changelog"]["histories"] for it in h["items"]
                 if it["field"] == "status" and it["toString"] == "Closed"), key=lambda h: h["created"])
        w = fecha(h["created"])
        if w >= ant0:
            filas.append((w, [("hoy " if w >= hoy0 else f"{w:%a} ") + f"{w:%H:%M}", u["key"],
                              ",".join(c["name"] for c in u["fields"]["components"]),
                              ",".join(v["name"] for v in u["fields"]["fixVersions"]),
                              h["author"]["displayName"].title(), corto(u["fields"]["summary"])]))
    tabla(["Cerrada", "US", "Comp.", "Versión", "Por", "Asunto"], [f for _, f in sorted(filas, key=lambda x: x[0], reverse=True)])


if __name__ == "__main__":
    main()
