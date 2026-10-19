#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seguimiento por versión y plataforma (US abiertas, bugs a Resolved, diseño pendiente).

Para cada ámbito (versión + componentes + labels de campaña) vuelca por consola:
  A. User Stories no cerradas: estado, QA de ejecución, avance de sus TCs
     (última ejecución por TC: Passed / Failed / Impeded / Pending / sin ejecución)
     y bugs asociados sin cerrar (sub-bugs hijos + enlazados con "detects").
  B. Bugs y Sub-Bugs que están ahora en Resolved (pendientes de verificar).
  C. User Stories con la subtarea [QA] US Test Design ni Closed ni Resolved (o sin subtarea).
  D. Cifras de resumen de la campaña para redactar los titulares.

Uso:
    python scripts/informes_mcp/seguimiento_versiones.py            # todos los ámbitos
    python scripts/informes_mcp/seguimiento_versiones.py ios android
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from refrescar_datos import nombre, subtareas_qa, test_cases, trozos  # noqa: E402
from seguimiento_diario import TIPOS_BUG, buscar, corto, tabla  # noqa: E402

AMBITOS = {
    "pcbff10": {"titulo": "26.10.100 · PC Client + GoBFF", "version": "26.10.100",
                "comps": ("PC Client", "GoBFF"), "labels": ("CC_26.10.100_Web", "CC_26.10.100_BFF"), "diseno": False},
    "ios": {"titulo": "26.11.100 · iOS", "version": "26.11.100",
            "comps": ("Mobile iOS",), "labels": ("CC_26.11.100_iOS",), "diseno": True},
    "android": {"titulo": "26.11.100 · Android", "version": "26.11.100",
                "comps": ("Mobile Android",), "labels": ("CC_26.11.100_Android",), "diseno": True},
    "tvos": {"titulo": "26.11.100 · tvOS", "version": "26.11.100",
             "comps": ("tvOS",), "labels": ("CC_26.11.100_tvOS",), "diseno": True},
    "pcbff11": {"titulo": "26.11.100 · PC Client + GoBFF", "version": "26.11.100",
                "comps": ("PC Client", "GoBFF"), "labels": ("CC_26.11.100_Web", "CC_26.11.100_BFF"), "diseno": True},
    # A 15/10/2026 no hay ejecuciones con este label: sale sin TCs ejecutados, pero con US, bugs y diseño
    "chromecast": {"titulo": "26.11.100 · Chromecast", "version": "26.11.100",
                   "comps": ("Chromecast",), "labels": ("CC_26.11.100_Chromecast",), "diseno": True},
}
ESTADOS = ["Passed", "Failed", "Impeded", "Pending"]
TIPOS = ("Bug", "Sub-Bug", "Bug SubTask")
ABREV = {"PC Client": "Web", "GoBFF": "BFF", "Mobile iOS": "iOS", "Mobile Android": "Android", "tvOS": "tvOS", "Chromecast": "Chromecast"}


def lista(xs):
    return ",".join(f'"{x}"' for x in xs)


def enlace_jql(keys):
    """Celda markdown "[n](búsqueda de Jira)" con esas claves; "0" si no hay ninguna."""
    if not keys:
        return 0
    jql = f'key in ({",".join(sorted(keys))}) ORDER BY key'
    return f"[{len(keys)}](https://jira.tid.es/issues/?jql={quote(jql)})"


def ambito(a):
    print(f"\n# {a['titulo']}\n")
    comps = a["comps"]
    us = buscar(f'(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story"'
                f' AND fixVersion = "{a["version"]}" AND component in ({lista(comps)}) ORDER BY key',
                ["summary", "status", "components", "issuelinks", "assignee"])
    keys = [u["key"] for u in us]
    subs = subtareas_qa(keys) if keys else {}

    def dueno(k, tipo="eje"):
        s = subs.get(k, {}).get(tipo) or []
        return nombre(s[0]["fields"].get("assignee")).title() if s else ""

    def plat(f):
        return "+".join(ABREV[c["name"]] for c in f["components"] if c["name"] in comps)

    # Ejecuciones de la campaña: la última por TC manda
    ejes = buscar(f"labels in ({lista(a['labels'])})",
                  ["status", "parent", "labels", "updated", "assignee", "issuelinks"])
    por_label = Counter(l for e in ejes for l in e["fields"]["labels"] if l in a["labels"])
    ult = {}
    for e in ejes:
        tc = e["fields"]["parent"]["key"]
        if tc not in ult or ult[tc][1] < e["fields"]["updated"]:
            ult[tc] = (e["fields"]["status"]["name"], e["fields"]["updated"], e["key"])
    tot = Counter(e["fields"]["status"]["name"] for e in ejes)

    # Bugs abiertos por US: sub-bugs hijos + enlazados con "detects"
    abiertas = [u for u in us if u["fields"]["status"]["name"] != "Closed"]
    hijos = defaultdict(list)
    for bloque in trozos([u["key"] for u in abiertas]):
        for s in buscar(f'issuetype in {TIPOS_BUG} AND parent in ({",".join(bloque)}) AND status != Closed',
                        ["status", "parent"]):
            hijos[s["fields"]["parent"]["key"]].append(f'{s["key"]} ({s["fields"]["status"]["name"]})')
    for u in abiertas:
        for l in u["fields"].get("issuelinks") or []:
            o = l.get("outwardIssue") or l.get("inwardIssue")
            if (l["type"]["outward"] != "detects" or not o or o["fields"]["issuetype"]["name"] not in TIPOS
                    or o["fields"]["status"]["name"] == "Closed"
                    or any(h.startswith(o["key"] + " ") for h in hijos[u["key"]])):
                continue
            hijos[u["key"]].append(f'{o["key"]} ({o["fields"]["status"]["name"]}, enlazado)')

    # A. US no cerradas
    print(f"## A. User Stories no cerradas ({len(abiertas)} de {len(us)})\n")
    orden = {"Resolved": 0, "Reopened": 1, "Impeded": 2, "In Progress": 3, "Code Review": 4}
    filas, tc_tot = [], Counter()
    for u in sorted(abiertas, key=lambda u: (orden.get(u["fields"]["status"]["name"], 9), u["key"])):
        f = u["fields"]
        tcs = test_cases(f)
        c = Counter(ult.get(t, ("Sin ejecución",))[0] for t in tcs)
        tc_tot += c
        # Cada cifra enlaza a su búsqueda en Jira: TCs, última ejecución por estado o TCs sin ejecución
        ej = {s: [ult[t][2] for t in tcs if t in ult and ult[t][0] == s] for s in ESTADOS}
        filas.append([u["key"], f["status"]["name"], plat(f), corto(f["summary"], 60),
                      dueno(u["key"]) or "*sin asignar*", enlace_jql(tcs), *(enlace_jql(ej[s]) for s in ESTADOS),
                      enlace_jql([t for t in tcs if t not in ult]), ", ".join(hijos[u["key"]]) or "—"])
    tabla(["US", "Estado", "Plat.", "Asunto", "QA ejecución", "TCs", "P", "F", "I", "Pe", "Sin eje.",
           "Bugs sin cerrar"], filas)

    # B. Bugs en Resolved
    detectados = {l["outwardIssue"]["key"] for e in ejes for l in e["fields"].get("issuelinks") or []
                  if "outwardIssue" in l and l["type"]["outward"] == "detects"}
    campos = ["summary", "issuetype", "status", "parent", "components", "reporter", "assignee", "updated", "fixVersions"]
    bugs = {b["key"]: b for b in buscar(
        f'issuetype in {TIPOS_BUG} AND status = Resolved AND fixVersion = "{a["version"]}"'
        f' AND component in ({lista(comps)})', campos)}
    for bloque in trozos(keys):
        for b in buscar(f'issuetype in {TIPOS_BUG} AND status = Resolved AND parent in ({",".join(bloque)})', campos):
            bugs[b["key"]] = b
    for bloque in trozos(detectados):
        for b in buscar(f'issuetype in {TIPOS_BUG} AND status = Resolved AND key in ({",".join(bloque)})', campos):
            bugs[b["key"]] = b
    print(f"## B. Bugs y Sub-Bugs en Resolved ({len(bugs)})\n")
    filas = []
    for b in sorted(bugs.values(), key=lambda b: b["fields"]["updated"], reverse=True):
        f = b["fields"]
        par = (f.get("parent") or {}).get("key", "")
        filas.append([b["key"], f["issuetype"]["name"], ",".join(c["name"] for c in f["components"]) or "—",
                      ",".join(v["name"] for v in f["fixVersions"]) or "—", par or "—",
                      (dueno(par) or "*sin QA*") if par in subs else f"reporter: {nombre(f.get('reporter')).title()}",
                      f["updated"][:10], corto(f["summary"])])
    tabla(["Bug", "Tipo", "Comp.", "Fix", "US padre", "Verifica", "Actualizado", "Asunto"], filas)

    # C. Diseño de pruebas pendiente
    sin_dis = []
    if a["diseno"]:
        for u in us:
            d = subs.get(u["key"], {}).get("dis") or []
            # Resolved cuenta como diseño hecho (solo falta cerrar la subtarea)
            pend = [s for s in d if s["fields"]["status"]["name"] not in ("Closed", "Resolved")]
            if not d:
                sin_dis.append((u, None))
            for s in pend:
                sin_dis.append((u, s))
        print(f"## C. US con diseño de pruebas pendiente ({len(sin_dis)})\n")
        filas = []
        for u, s in sorted(sin_dis, key=lambda x: (x[1] is None, x[0]["key"])):
            f = u["fields"]
            filas.append([u["key"], f["status"]["name"], plat(f), corto(f["summary"], 60),
                          s["key"] if s else "*sin subtarea*", s["fields"]["status"]["name"] if s else "—",
                          (nombre(s["fields"].get("assignee")).title() or "**sin asignar**") if s else "—",
                          len(test_cases(f))])
        tabla(["US", "Estado US", "Plat.", "Asunto", "Subtarea diseño", "Estado", "Asignada a", "TCs ya enlazados"], filas)

    # D. Resumen
    n = sum(tot.values())
    print("## D. Cifras para el resumen\n")
    print(f"- US: {len(us)} total · {Counter(u['fields']['status']['name'] for u in us).most_common()}")
    print(f"- Ejecuciones ({n}) por label: {dict(por_label)}")
    print("- Ejecuciones por estado: " + ", ".join(
        f"{s} {tot[s]} ({100 * tot[s] / n:.1f}%)" if n else f"{s} 0" for s in ESTADOS))
    print(f"- TCs de US abiertas (última ejecución): {dict(tc_tot)}")
    print(f"- Bugs en Resolved: {len(bugs)} · US abiertas con bugs sin cerrar: "
          f"{sum(1 for u in abiertas if hijos[u['key']])} ({sum(len(h) for h in hijos.values())} bugs)")
    if a["diseno"]:
        print(f"- Diseño pendiente: {len(sin_dis)} · sin asignar: "
              f"{sum(1 for _, s in sin_dis if s and not s['fields'].get('assignee'))}"
              f" · sin subtarea: {sum(1 for _, s in sin_dis if s is None)}")
    print(f"- Ejecuciones por assignee: {Counter(nombre(e['fields'].get('assignee')).title() or 'Sin asignar' for e in ejes).most_common()}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    elegidos = sys.argv[1:] or list(AMBITOS)
    for k in elegidos:
        ambito(AMBITOS[k])


if __name__ == "__main__":
    main()
