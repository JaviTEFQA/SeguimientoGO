"""Histórico de cada TC: nº de ejecuciones, Failed/Impeded y bugs detectados (enlace "detects") en todas sus ejecuciones.

Uso: python historico_bugs.py regresion_pc.json historico_bugs.json
"""
import sys, json
from collections import defaultdict
from pathlib import Path
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R)); sys.path.insert(0, str(R / "scripts/informes_mcp"))
from refrescar_datos import trozos
from seguimiento_diario import buscar

d = json.load(open(sys.argv[1], encoding="utf-8"))
tcs = sorted({x["k"] for u in d for x in u["tcs"] if x.get("st") != "Closed"})
hist = defaultdict(lambda: {"ejes": 0, "fails": 0, "bugs": {}})
for b in trozos(tcs):
    for e in buscar(f'parent in ({",".join(b)})', ["status", "parent", "labels", "issuelinks"]):
        h = hist[e["fields"]["parent"]["key"]]
        h["ejes"] += 1
        if e["fields"]["status"]["name"] in ("Failed", "Impeded"):
            h["fails"] += 1
        for l in e["fields"].get("issuelinks") or []:
            o = l.get("outwardIssue")
            if o and l["type"]["outward"] == "detects":
                h["bugs"][o["key"]] = None
bugkeys = sorted({k for h in hist.values() for k in h["bugs"]})
info = {}
for b in trozos(bugkeys):
    for x in buscar(f'key in ({",".join(b)})', ["summary", "status", "priority", "issuetype"]):
        f = x["fields"]
        info[x["key"]] = {"s": f["summary"], "st": f["status"]["name"], "pri": (f.get("priority") or {}).get("name"),
                          "t": f["issuetype"]["name"]}
out = {k: {"ejes": h["ejes"], "fails": h["fails"], "bugs": [dict(k=b, **info.get(b, {})) for b in h["bugs"]]}
       for k, h in hist.items()}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(tcs), "TCs", len(out), "con ejecuciones", len(bugkeys), "bugs")
