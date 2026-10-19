"""Ejecuciones RFA_26.10.100_Web de los TCs SMOKE (las que no son de la regresión de rfa.json).

Guarda por ejecución: TC, título, suite, componentes, labels, estado y assignee de la ejecución RFA,
y la última ejecución CC_26.10.100_Web del TC si la hay.

Uso: python datos_smoke.py smoke.json
"""
import json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]
S = Path(__file__).parent
sys.path.insert(0, str(R)); sys.path.insert(0, str(R / "scripts/informes_mcp"))
from refrescar_datos import trozos
from seguimiento_diario import buscar

LABEL, CAMP = "RFA_26.10.100_Web", "CC_26.10.100_Web"
regresion = {r["rfa"] for r in json.load(open(S / "rfa.json", encoding="utf-8")).values() if r.get("rfa")}
es = [e for e in buscar(f'labels = "{LABEL}"', ["parent", "assignee", "status", "updated"]) if e["key"] not in regresion]
tcs = sorted({e["fields"]["parent"]["key"] for e in es})
info, ult = {}, {}
for b in trozos(tcs):
    for t in buscar(f'key in ({",".join(b)})', ["summary", "status", "labels", "components"]):
        info[t["key"]] = t["fields"]
    for e in buscar(f'parent in ({",".join(b)}) AND labels = "{CAMP}"', ["parent", "status", "updated", "assignee"]):
        k = e["fields"]["parent"]["key"]
        if k not in ult or ult[k]["u"] < e["fields"]["updated"]:
            ult[k] = {"e": e["key"], "st": e["fields"]["status"]["name"], "u": e["fields"]["updated"],
                      "a": (e["fields"].get("assignee") or {}).get("displayName", "").title()}

out = []
for e in es:
    tc = e["fields"]["parent"]["key"]
    f = info[tc]
    m = re.match(r"\s*\[SMOKE\]\s*\[Suite\s*-\s*(\d+)\]\s*(.*)", f["summary"], re.I)
    out.append({"rfa": e["key"], "st": e["fields"]["status"]["name"],
                "asignado": (e["fields"].get("assignee") or {}).get("displayName", "").title(),
                "tc": tc, "s": m.group(2).strip() if m else f["summary"], "suite": int(m.group(1)) if m else None,
                "comps": [c["name"] for c in f["components"] if c["name"] != "Excel_Smoke"],
                "ia": "iA_smoke" in f["labels"], "previa": ult.get(tc)})
out.sort(key=lambda x: (x["suite"] or 999, x["tc"]))
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "ejecuciones smoke ·", len(tcs), "TCs ·", sum(1 for x in out if x["previa"]), "con ejecución CC previa")
