"""Crea una Test Case Execution con label RFA_26.10.100_Web por cada TC de la regresión de PC,
asignada a quien ejecutó por última vez el TC en la campaña CC_26.10.100_Web.

Quién ejecutó = autor del último cambio de estado a Passed/Failed/Impeded de la ejecución más
reciente; si no hay, el assignee de esa ejecución; si tampoco, el QA de la subtarea
[QA] US Test Execution de la US. Sin --crear solo simula. Guarda el resultado en rfa.json.
"""
import json, sys, time
from pathlib import Path
import requests

R = Path(__file__).resolve().parents[3]
S = Path(__file__).parent
sys.path.insert(0, str(R)); sys.path.insert(0, str(R / "scripts/informes_mcp")); sys.path.insert(0, str(S))
from jira_tc_report import JIRA_BASE_URL, SSL_VERIFY, get_headers
from refrescar_datos import trozos, subtareas_qa
from seguimiento_diario import buscar
from seleccion_regresion import E2E, IMP

LABEL, CAMP = "RFA_26.10.100_Web", "CC_26.10.100_Web"
crear = "--crear" in sys.argv
sys.stdout.reconfigure(encoding="utf-8")

d = json.load(open(S / "regresion_pc.json", encoding="utf-8"))
tc_us = {}
for u in d:
    for x in u["tcs"]:
        if x["k"] in E2E or x["k"] in IMP:
            tc_us.setdefault(x["k"], (u["key"], x["s"]))
tcs = sorted(tc_us)

existentes = {}
estado_rfa = {}  # TC -> (estado, assignee) actuales de su ejecución RFA
ultima = {}
for b in trozos(tcs):
    for e in buscar(f'parent in ({",".join(b)}) AND labels = "{LABEL}"', ["parent", "assignee", "status"]):
        existentes[e["fields"]["parent"]["key"]] = e["key"]
        estado_rfa[e["fields"]["parent"]["key"]] = (e["fields"]["status"]["name"], e["fields"].get("assignee"))
    for e in buscar(f'parent in ({",".join(b)}) AND labels = "{CAMP}"', ["parent", "updated", "assignee", "status"],
                    expand="changelog"):
        k = e["fields"]["parent"]["key"]
        if k not in ultima or ultima[k]["fields"]["updated"] < e["fields"]["updated"]:
            ultima[k] = e

qa = subtareas_qa(sorted({us for us, _ in tc_us.values()}))


def persona(p):
    return {"name": p["name"], "display": p["displayName"].title()} if p else None


res = {}
for tc in tcs:
    us, summ = tc_us[tc]
    e = ultima.get(tc)
    quien, origen = None, ""
    if e:
        for h in reversed(e.get("changelog", {}).get("histories", [])):
            if any(i["field"] == "status" and i["toString"] in ("Passed", "Failed", "Impeded") for i in h["items"]):
                quien, origen = persona(h["author"]), "ejecutó"
                break
        if not quien and e["fields"].get("assignee"):
            quien, origen = persona(e["fields"]["assignee"]), "assignee de la última ejecución"
    if not quien:
        s = (qa.get(us) or {}).get("eje") or []
        if s and s[0]["fields"].get("assignee"):
            quien, origen = persona(s[0]["fields"]["assignee"]), "QA de ejecución de la US"
    st, asig = estado_rfa.get(tc, (None, None))
    res[tc] = {"us": us, "previa": e["key"] if e else None, "previa_st": e["fields"]["status"]["name"] if e else None,
               "asignado": quien, "origen": origen, "rfa": existentes.get(tc),
               "rfa_st": st, "rfa_asignado": persona(asig)}


def crear_ejecucion(tc, summary, asignado, intentos=4):
    f = {"project": {"key": "MULTISTC"}, "issuetype": {"name": "Test Case Execution"}, "parent": {"key": tc},
         "summary": f"Execution of {summary}"[:255], "labels": [LABEL]}
    h = {**get_headers(), "Content-Type": "application/json"}
    for i in range(intentos):
        try:
            r = requests.post(f"{JIRA_BASE_URL}/rest/api/2/issue", headers=h, json={"fields": f}, verify=SSL_VERIFY, timeout=60)
            if r.status_code >= 300:
                raise SystemExit(f"ERROR {r.status_code} creando la ejecución de {tc}: {r.text[:400]}")
            key = r.json()["key"]
            break
        except requests.exceptions.ConnectionError:
            time.sleep(3 * (i + 1))
    else:
        raise SystemExit(f"ERROR de conexión persistente creando la ejecución de {tc}")
    if asignado:
        asignar(key, asignado)
    return key


def asignar(key, asignado, intentos=4):
    h = {**get_headers(), "Content-Type": "application/json"}
    for i in range(intentos):
        try:
            r = requests.put(f"{JIRA_BASE_URL}/rest/api/2/issue/{key}/assignee", headers=h,
                             json={"name": asignado["name"]}, verify=SSL_VERIFY, timeout=60)
            if r.status_code >= 300:
                raise SystemExit(f"ERROR {r.status_code} asignando {key} a {asignado['display']}: {r.text[:400]}")
            return
        except requests.exceptions.ConnectionError:
            time.sleep(3 * (i + 1))
    raise SystemExit(f"ERROR de conexión persistente asignando {key}")


from collections import Counter
print("TCs", len(tcs), "· ya con RFA", len(existentes))
print("Asignados:", Counter((r["asignado"] or {}).get("display", "SIN ASIGNAR") for r in res.values()).most_common())
print("Origen:", Counter(r["origen"] or "—" for r in res.values()))
print("Estado RFA:", Counter(r["rfa_st"] or "sin RFA" for r in res.values()).most_common())
for tc, r in res.items():
    if r["origen"] != "ejecutó":
        print("  ", tc, r["us"], r["previa"], r["previa_st"], r["origen"], (r["asignado"] or {}).get("display"))
if crear:
    for tc in tcs:
        r = res[tc]
        if not r["rfa"]:
            r["rfa"] = crear_ejecucion(tc, tc_us[tc][1], r["asignado"])
            r["rfa_st"], r["rfa_asignado"] = "Pending", r["asignado"]
            print("creada", r["rfa"], tc, (r["asignado"] or {}).get("display"))
            json.dump(res, open(S / "rfa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(S / "rfa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
