"""US de PC Client de la 26.10.100 con sus TCs (scope, estado) y la última ejecución CC_26.10.100_Web.

Uso: python datos_regresion.py regresion_pc.json
"""
import sys, json
from pathlib import Path
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R)); sys.path.insert(0, str(R / "scripts/informes_mcp"))
from refrescar_datos import test_cases, trozos
from seguimiento_diario import buscar
us = buscar('(project = "GO" OR project = "GOMOBILE") AND issuetype = "User Story" AND fixVersion = "26.10.100" AND component = "PC Client" ORDER BY key',
            ["summary", "status", "components", "issuelinks"])
tcs = {u["key"]: test_cases(u["fields"]) for u in us}
todos = sorted({t for v in tcs.values() for t in v})
info = {}
for b in trozos(todos):
    for t in buscar(f'key in ({",".join(b)})', ["summary", "status", "priority", "customfield_10163"]):
        f = t["fields"]
        info[t["key"]] = {"s": f["summary"], "st": f["status"]["name"], "pri": (f.get("priority") or {}).get("name"),
                          "scope": [o["value"] for o in (f.get("customfield_10163") or [])]}
ult = {}
for b in trozos(todos):
    for e in buscar(f'parent in ({",".join(b)}) AND labels = "CC_26.10.100_Web"', ["status", "parent", "updated", "issuelinks"]):
        k = e["fields"]["parent"]["key"]
        if k not in ult or ult[k]["u"] < e["fields"]["updated"]:
            bugs = [l["outwardIssue"]["key"] + " (" + l["outwardIssue"]["fields"]["status"]["name"] + ")"
                    for l in e["fields"].get("issuelinks") or [] if "outwardIssue" in l and l["type"]["outward"] == "detects"]
            ult[k] = {"e": e["key"], "st": e["fields"]["status"]["name"], "u": e["fields"]["updated"], "bugs": bugs}
out = [{"key": u["key"], "st": u["fields"]["status"]["name"], "comps": [c["name"] for c in u["fields"]["components"]],
        "s": u["fields"]["summary"], "tcs": [dict(k=t, **info.get(t, {}), eje=ult.get(t)) for t in tcs[u["key"]]]} for u in us]
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(us), "US", len(todos), "TCs", Counter(s for i in info.values() for s in i["scope"]), Counter(v["st"] for v in ult.values()))
