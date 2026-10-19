#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera los JSON de datos/ consultando la REST API de Jira (sin MCP).

Escribe solo los volcados que leen los generadores de esta carpeta, con la
misma estructura que tenian los hechos con el conector MCP:

  us_subtareas.json                              -> us_subtareas_qa.py
  us2.json, tcinfo2.json, eje2.json, sub2.json   -> us_tc_ejecuciones_bugs.py
  cuadro.json, v2611.json                        -> homologas_por_tecnologia.py
  v2611_full.json, cruce.json                    -> cobertura_tcs_version.py

Uso:
    python scripts/informes_mcp/refrescar_datos.py
"""
import io
import json
import os
import re
import sys
from pathlib import Path

# Reutiliza credenciales y busqueda paginada de jira_tc_report.py (raiz del repo)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jira_tc_report import jira_search  # noqa: E402

DATOS = Path(__file__).resolve().parent / "datos"
VERSION = "26.10.100"
VERSION_SIG = "26.11.100"
LABELS = ("CC_26.10.100_Web", "CC_26.10.100_BFF")
QA_TEST_DESIGN = "[QA] US Test Design"
QA_TEST_EXECUTION = "[QA] US Test Execution"
TODO = 100000  # sin tope de resultados

# Componente de Jira -> nombre de columna en los informes
COMP = {"PC Client": "PC Client", "Mobile Android": "Android", "Mobile iOS": "iOS",
        "tvOS": "tvOS", "GoBFF": "GoBFF", "Chromecast": "Chromecast"}
MOVIL = {"Mobile Android": "android", "Mobile iOS": "ios", "tvOS": "tvos"}
RE_JEFE = re.compile(r"\[?\s*(JEFE-\d+)\s*\]?", re.I)
RE_PREFIJO = re.compile(r"^(\[[^\]]*\]\s*)?(Web|BFF|Android|iOS|tvOS|Chromecast)[\.\s-]+", re.I)


def guarda(nombre, datos):
    with io.open(DATOS / nombre, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"  {nombre}: {len(datos)}")


def trozos(claves, n=100):
    claves = sorted(claves)
    for i in range(0, len(claves), n):
        yield claves[i:i + n]


def nombre(persona):
    return (persona or {}).get("displayName") or ""


def componente(f):
    for c in f.get("components") or []:
        if c["name"] in COMP:
            return c["name"]
    return ""


def fixes(f):
    return ", ".join(v["name"] for v in f.get("fixVersions") or [])


def enlaces(f, etiqueta, direccion="out"):
    """Issues enlazados con esa etiqueta de enlace en ese sentido."""
    campo, lado = ("outwardIssue", "outward") if direccion == "out" else ("inwardIssue", "inward")
    return [l[campo] for l in f.get("issuelinks") or []
            if campo in l and l["type"][lado] == etiqueta]


def test_cases(f):
    """Test Cases de una US. El enlace Tests puede estar guardado en cualquiera
    de los dos sentidos, asi que se miran ambos."""
    tcs = []
    for l in f.get("issuelinks") or []:
        i = l.get("outwardIssue") or l.get("inwardIssue")
        if (i and l["type"]["name"] == "Tests"
                and i["fields"]["issuetype"]["name"] == "Test Case" and i["key"] not in tcs):
            tcs.append(i["key"])
    return tcs


def bugs(f):
    return [{"key": b["key"], "tipo": b["fields"]["issuetype"]["name"],
             "status": b["fields"]["status"]["name"],
             "prio": (b["fields"].get("priority") or {}).get("name", ""),
             "summary": b["fields"]["summary"]}
            for b in enlaces(f, "detects")]


def gospecs(f):
    return [i["key"] for i in enlaces(f, "is a dependency for", "in") if i["key"].startswith("GOSPECS-")]


def us_version(version, extra=""):
    return jira_search(
        '(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story"'
        f' AND fixVersion = "{version}"{extra} ORDER BY key ASC',
        ["summary", "status", "components", "fixVersions", "assignee", "issuelinks"], TODO)


def subtareas_qa(us_keys):
    """{us_key: {"dis": [issue], "eje": [issue]}} con las subtareas QA de cada US."""
    out = {k: {"dis": [], "eje": []} for k in us_keys}
    for bloque in trozos(us_keys):
        for s in jira_search(f"parent in ({','.join(bloque)})",
                             ["summary", "status", "assignee", "parent"], TODO):
            p, suma = s["fields"]["parent"]["key"], s["fields"]["summary"]
            if QA_TEST_DESIGN in suma:
                out[p]["dis"].append(s)
            elif QA_TEST_EXECUTION in suma:
                out[p]["eje"].append(s)
    return out


def corto(persona):
    """"LUIS ALBERTO BAYO MARTIN" -> "Luis Alberto" (nombre + primer apellido)."""
    return " ".join(nombre(persona).title().split()[:2])


# ── us_subtareas.json ─────────────────────────────────────────────────────────
def refresca_subtareas():
    us = jira_search(
        f'project = "GO" AND issuetype = "User Story" AND fixVersion = "{VERSION}"'
        ' AND component in ("PC Client", GoBFF) AND status != Closed ORDER BY key ASC',
        ["summary", "status", "components"], TODO)
    subs = subtareas_qa([u["key"] for u in us])
    filas = []
    for u in us:
        f = u["fields"]
        jefe = RE_JEFE.search(f["summary"])
        titulo = RE_JEFE.sub("", RE_PREFIJO.sub("", f["summary"].strip()), count=1)
        filas.append({
            "key": u["key"], "comp": componente(f), "status": f["status"]["name"],
            "titulo": titulo.strip(" -.:"), "jefe": jefe.group(1).upper() if jefe else "",
            **{t: [{"key": s["key"], "st": s["fields"]["status"]["name"],
                    "as": corto(s["fields"].get("assignee"))} for s in subs[u["key"]][t]]
               for t in ("dis", "eje")},
        })
    guarda("us_subtareas.json", filas)


# ── us2 / tcinfo2 / eje2 / sub2 ───────────────────────────────────────────────
def refresca_us_tc():
    us = jira_search(
        f'project = "GO" AND issuetype = "User Story" AND fixVersion = "{VERSION}"'
        ' AND component in ("PC Client", GoBFF) AND status in (Resolved, Reopened)'
        " ORDER BY status DESC, key ASC",
        ["summary", "status", "components", "issuelinks"], TODO)
    us2 = [{"key": u["key"], "summary": u["fields"]["summary"],
            "status": u["fields"]["status"]["name"],
            "comp": "Web" if componente(u["fields"]) == "PC Client" else "BFF",
            "tcs": test_cases(u["fields"])} for u in us]
    us2.sort(key=lambda u: u["comp"] != "Web")  # Web primero, orden estable
    todos = sorted({tc for u in us2 for tc in u["tcs"]})

    tcinfo = {}
    for bloque in trozos(todos):
        for t in jira_search(f"key in ({','.join(bloque)})", ["summary", "issuelinks"], TODO):
            tcinfo[t["key"]] = {"summary": t["fields"]["summary"], "bugs": bugs(t["fields"])}

    # Ultima ejecucion de campaña por TC (la de "updated" mas reciente)
    eje = {}
    for bloque in trozos(todos):
        for e in jira_search(
                f"parent in ({','.join(bloque)}) AND labels in ({', '.join(LABELS)})",
                ["status", "assignee", "updated", "parent", "issuelinks"], TODO):
            f = e["fields"]
            tc = f["parent"]["key"]
            if tc in eje and eje[tc]["_upd"] >= f["updated"]:
                continue
            eje[tc] = {"key": e["key"], "status": f["status"]["name"], "tc": tc,
                       "assignee": nombre(f.get("assignee")) or "Sin asignar",
                       "updated": f["updated"][:10], "bugs": bugs(f), "_upd": f["updated"]}
    for v in eje.values():
        del v["_upd"]

    sub2 = {}
    for k, s in subtareas_qa([u["key"] for u in us2]).items():
        if s["eje"]:
            x = s["eje"][0]["fields"]
            sub2[k] = {"key": s["eje"][0]["key"], "status": x["status"]["name"],
                       "assignee": nombre(x.get("assignee")) or "Unassigned"}

    guarda("us2.json", us2)
    guarda("tcinfo2.json", tcinfo)
    guarda("eje2.json", eje)
    guarda("sub2.json", sub2)


# ── cuadro / v2611 / v2611_full / cruce ───────────────────────────────────────
def familias(spec_keys):
    """{spec: [hijos]} con las US de las que depende cada GOSPECS."""
    fam = {}
    for bloque in trozos(spec_keys):
        for s in jira_search(f"key in ({','.join(bloque)})", ["issuelinks"], TODO):
            fam[s["key"]] = [i["key"] for i in enlaces(s["fields"], "depends on")]
    return fam


def detalle_us(keys):
    out = {}
    for bloque in trozos(keys):
        for u in jira_search(f"key in ({','.join(bloque)})",
                             ["summary", "status", "components", "fixVersions",
                              "issuetype", "issuelinks"], TODO):
            f = u["fields"]
            if f["issuetype"]["name"] != "User Story":
                continue
            out[u["key"]] = {"comp": componente(f), "estado": f["status"]["name"],
                             "fix": fixes(f), "ntc": len(test_cases(f))}
    return out


def refresca_homologas():
    pc = jira_search(
        f'project = "GO" AND issuetype = "User Story" AND fixVersion = "{VERSION}"'
        ' AND component = "PC Client" ORDER BY key ASC',
        ["summary", "status", "issuelinks"], TODO)
    sig = us_version(VERSION_SIG)

    spec_de = {u["key"]: (gospecs(u["fields"]) or [None])[0] for u in pc + sig}
    fam = familias({s for s in spec_de.values() if s})
    hijos = detalle_us({h for hs in fam.values() for h in hs})

    cuadro = []
    for u in pc:
        f, spec = u["fields"], spec_de[u["key"]]
        fila = {"pc": u["key"], "sum": f["summary"], "estado": f["status"]["name"],
                "ntc": len(test_cases(f)), "spec": spec,
                "android": None, "ios": None, "tvos": None}
        for h in fam.get(spec, []):
            d = hijos.get(h)
            if d and d["comp"] in MOVIL and not fila[MOVIL[d["comp"]]]:
                fila[MOVIL[d["comp"]]] = {"key": h, "estado": d["estado"],
                                          "ntc": d["ntc"], "fix": d["fix"]}
        cuadro.append(fila)

    full, lista, cruce = {}, [], {}
    for u in sig:
        f = u["fields"]
        comp = COMP.get(componente(f), componente(f))
        v = {"summary": f["summary"], "status": f["status"]["name"], "comp": comp,
             "asig": nombre(f.get("assignee")) or "Unassigned",
             "ntc": len(test_cases(f))}
        lista.append({"key": u["key"], **v})
        full[u["key"]] = {**v, "spec": spec_de[u["key"]]}
        if not v["ntc"] and spec_de[u["key"]]:
            otras = [{"key": h, "comp": COMP.get(d["comp"], d["comp"]), "ntc": d["ntc"], "fix": d["fix"]}
                     for h in fam.get(spec_de[u["key"]], [])
                     if h != u["key"] and (d := hijos.get(h)) and d["ntc"]]
            if otras:
                cruce[u["key"]] = otras

    guarda("cuadro.json", cuadro)
    guarda("v2611.json", lista)
    guarda("v2611_full.json", full)
    guarda("cruce.json", cruce)


def main():
    print("Refrescando datos/ desde Jira …")
    refresca_subtareas()
    refresca_us_tc()
    refresca_homologas()


if __name__ == "__main__":
    main()
