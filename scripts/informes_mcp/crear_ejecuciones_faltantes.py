#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crea las Test Case Execution que faltan en una versión, solo para US con el diseño cerrado.

Por cada User Story no cerrada de la versión cuya subtarea [QA] US Test Design está en
Resolved o Closed, cada uno de sus Test Cases (enlace Tests, en los dos sentidos) debe tener
una ejecución con el label de campaña de la plataforma de la US. Los labels salen de
jira_tc_labels_by_version.json (componente -> clave de reporte -> label). Un TC enlazado a US
de varias plataformas recibe una ejecución por plataforma. Los TCs cerrados se saltan.

Tampoco se crea la ejecución de Android, iOS o tvOS a los TCs automatizados en esa plataforma
(pedido del usuario el 19/10/2026): label AUTO_ACCEPTANCE_<Android|iOS|tvOS> o la plataforma
marcada en AutoUSTest Done, y Test Scope distinto de End2End (los E2E se ejecutan a mano).

La ejecución nueva va en Pending, sin asignar, con summary "Execution of <TC>". Jira no deja
poner el componente por la API.

Sin --crear solo muestra lo que haría.

Uso:
    python scripts/informes_mcp/crear_ejecuciones_faltantes.py [--version 26.11.100] [--crear]
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jira_tc_report import JIRA_BASE_URL, SSL_VERIFY, get_headers  # noqa: E402
from refrescar_datos import test_cases  # noqa: E402
from seguimiento_diario import buscar  # noqa: E402

COMPONENTE_REPORTE = {"Mobile Android": "android", "Mobile iOS": "ios", "tvOS": "tvos",
                      "PC Client": "pc", "GoBFF": "gobff"}
QA_TEST_DESIGN = "[QA] US Test Design"
DISENO_CERRADO = {"resolved", "closed"}
TC_CERRADO = {"closed", "deprecated", "obsolete", "discarded", "cancelled"}
AUTOUSTEST_DONE = "customfield_33700"   # AutoUSTest Done (multicheckbox)
TEST_SCOPE = "customfield_10163"
# Componente -> (label de automatizado, opción de AutoUSTest Done): sin ejecución manual si no es End2End
AUTOMATIZADO = {"Mobile Android": ("AUTO_ACCEPTANCE_Android", "Mobile Android"),
                "Mobile iOS": ("AUTO_ACCEPTANCE_iOS", "Mobile iOS"),
                "tvOS": ("AUTO_ACCEPTANCE_tvOS", "tvOS")}


def automatizado(f, componente):
    """True si el TC está automatizado para ese componente y no es End2End."""
    if componente not in AUTOMATIZADO:
        return False
    label, opcion = AUTOMATIZADO[componente]
    scope = [x.get("value") for x in f.get(TEST_SCOPE) or []]
    auto = label in (f.get("labels") or []) or opcion in [x.get("value") for x in f.get(AUTOUSTEST_DONE) or []]
    return auto and "End2End" not in scope


def diseno(u):
    """Estado de la subtarea de diseño (la original si hay clones)."""
    subs = [s for s in u["fields"].get("subtasks", []) if QA_TEST_DESIGN in s["fields"]["summary"]]
    subs.sort(key=lambda s: s["fields"]["summary"].strip() != QA_TEST_DESIGN)
    return subs[0]["fields"]["status"]["name"] if subs else "sin subtarea"


def crear_ejecucion(tc, summary, label, intentos=4):
    payload = {"fields": {"project": {"key": "MULTISTC"}, "issuetype": {"name": "Test Case Execution"},
                          "parent": {"key": tc}, "summary": f"Execution of {summary}"[:255], "labels": [label]}}
    for i in range(intentos):
        try:
            r = requests.post(f"{JIRA_BASE_URL}/rest/api/2/issue", headers={**get_headers(), "Content-Type": "application/json"},
                              json=payload, verify=SSL_VERIFY, timeout=60)
            if r.status_code >= 300:
                raise SystemExit(f"ERROR {r.status_code} creando la ejecución de {tc} ({label}): {r.text[:400]}")
            return r.json()["key"]
        except requests.exceptions.ConnectionError:  # cortes de TLS habituales contra jira.tid.es
            time.sleep(3 * (i + 1))
    raise SystemExit(f"ERROR de conexión persistente creando la ejecución de {tc} ({label})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="26.11.100")
    ap.add_argument("--crear", action="store_true", help="crear de verdad (sin esto solo simula)")
    args = ap.parse_args()

    labels_version = json.load(open(RAIZ / "jira_tc_labels_by_version.json", encoding="utf-8")).get(args.version, {})
    label_de = {comp: labels_version[rep] for comp, rep in COMPONENTE_REPORTE.items() if rep in labels_version}

    us = buscar(f'(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story"'
                f' AND fixVersion = "{args.version}" AND status != Closed',
                ["summary", "status", "components", "issuelinks", "subtasks"])
    abiertas = [(u["key"], diseno(u), len(test_cases(u["fields"]))) for u in us
                if diseno(u).lower() not in DISENO_CERRADO and test_cases(u["fields"])]
    us = [u for u in us if diseno(u).lower() in DISENO_CERRADO]

    necesarias, sin_label = defaultdict(set), Counter()  # (tc, label) -> {US}
    for u in us:
        comps = [c["name"] for c in u["fields"]["components"]]
        labs = [label_de[c] for c in comps if c in label_de]
        if not labs and test_cases(u["fields"]):
            sin_label[f'{u["key"]} ({",".join(comps) or "sin componente"})'] += len(test_cases(u["fields"]))
        for tc in test_cases(u["fields"]):
            for l in labs:
                necesarias[(tc, l)].add(u["key"])

    tcs = sorted({tc for tc, _ in necesarias})
    info, existentes = {}, set()
    for i in range(0, len(tcs), 100):
        bloque = ",".join(tcs[i:i + 100])
        for t in buscar(f"key in ({bloque})", ["summary", "status", "labels", AUTOUSTEST_DONE, TEST_SCOPE]):
            info[t["key"]] = t["fields"]
        for e in buscar(f'issuetype = "Test Case Execution" AND parent in ({bloque})'
                        f' AND labels in ({",".join(sorted(set(label_de.values())))})', ["parent", "labels"]):
            existentes.update((e["fields"]["parent"]["key"], l) for l in e["fields"]["labels"])

    faltan = [p for p in sorted(necesarias) if p not in existentes]
    cerrados = [p for p in faltan if info[p[0]]["status"]["name"].lower() in TC_CERRADO]
    componente_de = {l: c for c, l in label_de.items()}
    autos = [p for p in faltan if p not in set(cerrados) and automatizado(info[p[0]], componente_de[p[1]])]
    crear = [p for p in faltan if p not in set(cerrados) | set(autos)]

    print(f"# Ejecuciones que faltan en la {args.version}\n")
    print(f"- US no cerradas con el diseño en Resolved/Closed: {len(us)} · TCs: {len(tcs)}"
          f" · pares TC+label: {len(necesarias)} · ya tienen ejecución: {len(necesarias) - len(faltan)}")
    print(f"- A crear: **{len(crear)}** " + (str(dict(Counter(l for _, l in crear))) if crear else ""))
    if cerrados:
        print("- Se saltan por TC cerrado: " + ", ".join(f"{tc} ({l})" for tc, l in cerrados))
    if autos:
        print("- Se saltan por TC automatizado: " + ", ".join(f"{tc} ({l})" for tc, l in autos))
    if sin_label:
        print("- US sin label de campaña en esta versión (no se crea nada): " + ", ".join(f"{k}: {n} TCs" for k, n in sin_label.items()))
    if abiertas:
        print(f"- Esperan a que se cierre su diseño ({len(abiertas)} US con TCs): "
              + ", ".join(f"{k} ({d}, {n} TCs)" for k, d, n in abiertas))

    if not crear:
        return
    if not args.crear:
        print("\nSimulación: no se ha creado nada (añade --crear).")
        for tc, l in crear:
            print(f"  {tc} · {l} · US {', '.join(sorted(necesarias[(tc, l)]))}")
        return
    print("\n| Ejecución | TC | Label | US |\n|---|---|---|---|")
    for tc, l in crear:
        key = crear_ejecucion(tc, info[tc]["summary"], l)
        print(f"| {key} | {tc} | {l} | {', '.join(sorted(necesarias[(tc, l)]))} |")


if __name__ == "__main__":
    main()
