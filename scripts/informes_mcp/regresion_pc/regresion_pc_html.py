"""Página de la regresión de PC: TCs elegidos (seleccion_regresion.py), último estado, ejecución RFA y bugs.

Uso: python regresion_pc_html.py regresion_pc.json <salida.html> historico_bugs.json rfa.json
"""
import json, sys, re, html
from collections import Counter
from datetime import date

d = json.load(open(sys.argv[1], encoding="utf-8"))
HIST = json.load(open(sys.argv[3], encoding="utf-8"))
RFA = json.load(open(sys.argv[4], encoding="utf-8")) if len(sys.argv) > 4 else {}
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from seleccion_regresion import E2E as SEL, IMP
J = "https://jira.tid.es/browse/"
E = html.escape
PRI = {"Blocker": "bad", "Critical": "bad", "Major": "imp"}


def limpia(s):
    return re.sub(r"^\s*(\[IMPEDED BY QA\]\s*)?(WEB|Web)\s*[.\-]*\s*", "", s.strip())


def badge(st):
    c = {"Passed": "ok", "Failed": "bad", "Impeded": "imp", "Pending": "pen"}.get(st, "na")
    return f'<span class="b {c}">{E(st)}</span>'


def usbadge(st):
    c = {"Closed": "ok", "Resolved": "res", "Impeded": "imp", "Reopened": "bad"}.get(st, "na")
    return f'<span class="b {c}">{E(st)}</span>'


def link(k):
    return f'<a href="{J}{k}" target="_blank" rel="noopener">{k}</a>'


def rfa_td(tc):
    r = RFA.get(tc)
    if not r or not r.get("rfa"):
        return '<td class="rfa"><span class="nob">—</span></td>'
    p = (r.get("rfa_asignado") or r.get("asignado") or {}).get("display") or "Sin asignar"
    nota = "" if r.get("origen") == "ejecutó" else f'<span class="why">{E(r.get("origen") or "")}</span>'
    return f'<td class="rfa"><span class="k">{link(r["rfa"])}</span> {badge(r.get("rfa_st") or "Pending")}<div class="who">{E(p)}</div>{nota}</td>'


bloques, sin, cnt = [], [], Counter()
for u in d:
    vivos = [x for x in u["tcs"] if x.get("st") != "Closed"]
    n_e2e = sum(1 for x in vivos if "End2End" in x.get("scope", []))
    cnt["E2E_total"] += n_e2e
    sel = [(x, x["k"] in SEL) for x in vivos if x["k"] in SEL or x["k"] in IMP]
    if not sel:
        sin.append((u, n_e2e))
        continue
    filas = []
    for x, e2e in sel:
        ej = x.get("eje") or {}
        st = ej.get("st", "Sin ejecución")
        cnt[st] += 1
        cnt["E2E" if e2e else "IMP"] += 1
        if e2e:
            mot = f'<span class="m e2e">End2End</span><span class="why">{E(SEL[x["k"]])}</span>'
        else:
            mot = f'<span class="m imp">Impedida importante</span><span class="why">{E(IMP[x["k"]])}</span>'
        hb = (HIST.get(x["k"]) or {}).get("bugs") or []
        bugs = "".join(
            f'<li><a href="{J}{b["k"]}" target="_blank" rel="noopener">{b["k"]}</a> '
            f'<span class="b {PRI.get(b.get("pri"), "pen")}">{E(b.get("pri") or "—")}</span> '
            f'<span class="bst">{E(b.get("st", ""))}</span> {E((b.get("s") or "")[:90])}</li>' for b in hb)
        u_ = ej.get("u", "")
        fecha = f"{u_[8:10]}/{u_[5:7]}" if u_ else ""
        filas.append(
            f'<tr data-st="{E(st)}" data-tipo="{"e2e" if e2e else "imp"}" data-bugs="{len(hb)}">'
            f'<td class="k">{link(x["k"])}</td><td class="t">{E(x.get("s", ""))}<div class="mot">{mot}</div></td>'
            f'<td>{badge(st)}<span class="f">{fecha}</span></td>'
            + rfa_td(x["k"]) +
            f'<td class="hb">{"<ul>" + bugs + "</ul>" if bugs else "<span class=nob>—</span>"}</td></tr>')
    no_ok = sum(1 for x, _ in sel if (x.get("eje") or {}).get("st") != "Passed")
    plural = "s" if len(sel) != 1 else ""
    extra = (f" · {n_e2e} E2E en la US" if n_e2e else "") + (f" · <b>{no_ok} sin Passed</b>" if no_ok else "")
    bloques.append(
        f'<section class="us"><header><span class="uk">{link(u["key"])}</span>{usbadge(u["st"])}'
        f'<h3>{E(limpia(u["s"]))}</h3><span class="cnt">{len(sel)} prueba{plural}{extra}</span></header>'
        '<div class="wrap"><table><thead><tr><th>Test Case</th><th>Título y por qué entra</th><th>Último estado (CC)</th><th>Ejecución RFA y asignada a</th><th>Bugs que ha detectado</th></tr></thead>'
        f'<tbody>{"".join(filas)}</tbody></table></div></section>')

total = sum(cnt[k] for k in ("Passed", "Failed", "Impeded", "Pending", "Sin ejecución"))
sinl = "".join(f'<li><span class="uk">{link(u["key"])}</span> {usbadge(u["st"])} {E(limpia(u["s"]))}'
               + (f' <span class="f">({n} E2E sin seleccionar)</span>' if n else "") + "</li>" for u, n in sin)


CSS = """
/* Layout: cabecera con cifras, prioridades y filtros; una sección por User Story con su tabla de TCs; al final las US sin pruebas */
:root{--bg:#f3f5f8;--card:#fff;--fg:#1a2130;--mut:#5d6778;--line:#dce1e8;--acc:#2a56c6;--accbg:#e7edfb;
--ok:#e1f3e6;--okf:#146c38;--bad:#fde5e2;--badf:#b0261a;--imp:#fff0d6;--impf:#8a5600;--pen:#eceff4;--penf:#4b5567;--res:#e2effc;--resf:#1d5a9e;
--sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#10141a;--card:#181d26;--fg:#e3e7ee;--mut:#97a0b0;--line:#29303c;--acc:#93b1ff;--accbg:#1c2743;
--ok:#12321e;--okf:#7fdb9b;--bad:#3a1816;--badf:#f39a93;--imp:#352810;--impf:#f1c46a;--pen:#242a34;--penf:#b3bbca;--res:#14283f;--resf:#8fc0f5;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#10141a;--card:#181d26;--fg:#e3e7ee;--mut:#97a0b0;--line:#29303c;--acc:#93b1ff;--accbg:#1c2743;
--ok:#12321e;--okf:#7fdb9b;--bad:#3a1816;--badf:#f39a93;--imp:#352810;--impf:#f1c46a;--pen:#242a34;--penf:#b3bbca;--res:#14283f;--resf:#8fc0f5;color-scheme:dark}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font:14px/1.45 var(--sans)}
main{max-width:1240px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:24px 48px;display:grid;gap:18px}
h1{font-size:24px;margin:0;text-wrap:balance}.sub{color:var(--mut);margin:4px 0 0;max-width:80ch}
.stats{display:flex;flex-wrap:wrap;gap:10px}.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 14px;display:grid;min-width:110px}
.stat b{font-size:22px;font-variant-numeric:tabular-nums}.stat span{font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.ctrl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg);padding-block:8px;z-index:2}
.ctrl button{font:inherit;font-weight:600;border:1px solid var(--line);background:var(--card);color:var(--mut);border-radius:999px;padding:5px 12px;cursor:pointer}
.ctrl button[aria-pressed="true"]{background:var(--accbg);color:var(--acc);border-color:var(--acc)}
.ctrl button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.ctrl input{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:5px 10px;min-width:0;flex:1 1 200px;max-width:320px}
#lista{display:grid;gap:22px}.us{display:grid;gap:8px;min-width:0}.us header{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.us h3{font-size:15px;margin:0;flex:1 1 300px;min-width:0}.uk{font-family:var(--mono);font-weight:600}.cnt{color:var(--mut);font-size:13px}.cnt b{color:var(--badf)}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
tbody tr:last-child td{border-bottom:0}th{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);white-space:nowrap}
td.k{font-family:var(--mono);font-size:12.5px;white-space:nowrap}td.t{min-width:300px}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.ok{background:var(--ok);color:var(--okf)}.bad{background:var(--bad);color:var(--badf)}.imp{background:var(--imp);color:var(--impf)}
.pen,.na{background:var(--pen);color:var(--penf)}.res{background:var(--res);color:var(--resf)}
.m{display:inline-block;font-size:11.5px;font-weight:600;border-radius:4px;padding:0 6px;margin:0 4px 2px 0;white-space:nowrap}
.m.e2e{background:var(--accbg);color:var(--acc)}.m.imp{background:var(--imp);color:var(--impf)}.why{display:block;font-size:12.5px;color:var(--mut)}
.f{font-size:12px;color:var(--mut);margin-left:6px;font-variant-numeric:tabular-nums}.bugs{font-size:12px;color:var(--mut);margin-top:3px}
.prio{background:var(--accbg);border-radius:10px;padding:12px 16px}.prio h2,.sin h2{font-size:15px;margin:0 0 6px}
.prio ul,.sin ul{margin:0;padding-left:18px;display:grid;gap:4px}
.sin{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}.sin .sub{margin:0 0 8px}
.vacio{color:var(--mut)}.stat small{font-size:13px;font-weight:500;color:var(--mut)}
.mot{margin-top:4px}td.hb{min-width:280px;font-size:12.5px}td.hb ul{margin:0;padding:0;list-style:none;display:grid;gap:3px}
.bst{color:var(--mut);font-size:12px}.nob{color:var(--mut)}
.tabs{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line)}
.tab{font:inherit;font-weight:600;border:0;background:none;color:var(--mut);padding:8px 14px;border-radius:8px 8px 0 0;cursor:pointer}
.tab:hover{color:var(--fg)}.tab[aria-selected="true"]{color:var(--acc);box-shadow:inset 0 -2px 0 var(--acc)}.tab:focus-visible{outline:2px solid var(--acc)}
.panel{display:grid;gap:18px}#lista-smoke{display:grid;gap:22px}
td.rfa{white-space:nowrap}td.rfa .k{font-family:var(--mono);font-size:12.5px}.who{font-weight:600;margin-top:3px}
.reparto{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}.reparto h2{font-size:15px;margin:0 0 8px}
.reparto ul{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:6px 18px}.reparto b{font-variant-numeric:tabular-nums}
"""

JS = """
const btns=[...document.querySelectorAll(".ctrl button")],q=document.getElementById("q");let f="todas";
function aplica(){const t=q.value.trim().toLowerCase();let vis=0;
document.querySelectorAll("#panel-reg .us").forEach(s=>{let n=0;const usTxt=s.querySelector("header").textContent.toLowerCase();
s.querySelectorAll("tbody tr").forEach(r=>{const st=r.dataset.st,ti=r.dataset.tipo;
let ok=f==="todas"||(f==="nopass"&&st!=="Passed")||(f==="bugs"&&r.dataset.bugs!=="0")||f===st||f===ti;
if(ok&&t)ok=r.textContent.toLowerCase().includes(t)||usTxt.includes(t);r.hidden=!ok;if(ok)n++;});
s.hidden=!n;vis+=n;});document.getElementById("vacio").hidden=!!vis;}
btns.forEach(b=>b.addEventListener("click",()=>{f=b.dataset.f;btns.forEach(x=>x.setAttribute("aria-pressed",String(x===b)));aplica();}));
q.addEventListener("input",aplica);
document.querySelectorAll("#panel-reg .us").forEach(s=>s.classList.add("reg"));
const tabs=[...document.querySelectorAll(".tab")];
function abre(p){tabs.forEach(t=>t.setAttribute("aria-selected",String(t.dataset.p===p)));
document.getElementById("panel-reg").hidden=p!=="reg";document.getElementById("panel-smoke").hidden=p!=="smoke";}
tabs.forEach(t=>t.addEventListener("click",()=>abre(t.dataset.p)));
if(location.hash==="#smoke")abre("smoke");
const qs=document.getElementById("qs");
qs.addEventListener("input",()=>{const t=qs.value.trim().toLowerCase();let vis=0;
document.querySelectorAll("#panel-smoke .suite").forEach(s=>{const h=s.querySelector("header").textContent.toLowerCase();let n=0;
s.querySelectorAll("tbody tr").forEach(r=>{const ok=!t||h.includes(t)||r.textContent.toLowerCase().includes(t);r.hidden=!ok;if(ok)n++;});
s.hidden=!n;vis+=n;});document.getElementById("vacio-smoke").hidden=!!vis;});
"""

stats = [(len(d), "US de PC"), (total, "Pruebas"), (f'{cnt["E2E"]}<small> de {cnt["E2E_total"]}</small>', "End2End elegidas"),
         (cnt["IMP"], "Impedidas importantes"),
         (cnt["Passed"], "En Passed"), (cnt["Impeded"], "En Impeded"), (cnt["Failed"], "En Failed"),
         (cnt["Pending"] + cnt["Sin ejecución"], "En Pending")]
con_rfa = [r for r in RFA.values() if r.get("rfa")]
quien_rfa = lambda r: (r.get("rfa_asignado") or r.get("asignado") or {}).get("display") or "Sin asignar"
rep = Counter(quien_rfa(r) for r in con_rfa)
hechas = Counter(quien_rfa(r) for r in con_rfa if (r.get("rfa_st") or "Pending") != "Pending")
st_rfa = Counter(r.get("rfa_st") or "Pending" for r in con_rfa)
resumen_rfa = ", ".join(f"{st_rfa[s]} {s}" for s in ("Passed", "Failed", "Impeded", "Pending") if st_rfa[s])
reparto = ("" if not rep else
           f'<section class="reparto"><h2>Ejecuciones RFA_26.10.100_Web por persona ({sum(rep.values())}: {resumen_rfa})</h2><ul>'
           + "".join(f"<li>{E(p)} <b>{hechas[p]}/{n}</b></li>" for p, n in rep.most_common())
           + '</ul><p class="sub" style="margin:8px 0 0">Ejecutadas / asignadas por persona. Cada ejecución va a quien ejecutó el TC por última vez en la campaña CC_26.10.100_Web.</p></section>')
stats_html = "".join(f'<div class="stat"><b>{n}</b><span>{t}</span></div>' for n, t in stats)

# Pestaña Smoke: ejecuciones RFA de los TCs SMOKE, agrupadas por suite
SMOKE = json.load(open(sys.argv[5], encoding="utf-8")) if len(sys.argv) > 5 else []
suites = {}
for x in SMOKE:
    suites.setdefault(x["suite"], []).append(x)
smoke_bloques = []
for n, xs in suites.items():
    # la 35 se usa dos veces (Player y Rows): se nombran las áreas con varias entradas
    areas = Counter(x["s"].split(" - ")[0].strip() for x in xs).most_common()
    area = " / ".join(a for a, c in areas if c >= 3 or a == areas[0][0])
    filas = "".join(
        f'<tr><td class="k">{link(x["rfa"])}</td><td class="k">{link(x["tc"])}</td>'
        f'<td class="t">{E(x["s"])}' + (' <span class="m e2e">iA_smoke</span>' if x["ia"] else "") + "</td>"
        f'<td>{E(", ".join(x["comps"]) or "—")}</td><td>{badge(x["st"])}</td>'
        f'<td>{E(x["asignado"]) if x["asignado"] else "<span class=nob>Sin asignar</span>"}</td></tr>' for x in xs)
    smoke_bloques.append(
        f'<section class="us suite"><header><h3>Suite {n if n is not None else "?"} · {E(area)}</h3>'
        f'<span class="cnt">{len(xs)} ejecuci{"ones" if len(xs) != 1 else "ón"}</span></header>'
        '<div class="wrap"><table><thead><tr><th>Ejecución RFA</th><th>Test Case</th><th>Título</th><th>Componente</th>'
        f'<th>Estado</th><th>Asignada a</th></tr></thead><tbody>{filas}</tbody></table></div></section>')
sm_st = Counter(x["st"] for x in SMOKE)
sm_asig = sum(1 for x in SMOKE if x["asignado"])
smoke_stats = "".join(f'<div class="stat"><b>{n}</b><span>{t}</span></div>' for n, t in [
    (len(SMOKE), "Ejecuciones smoke"), (len(suites), "Suites"), (sum(1 for x in SMOKE if x["ia"]), "iA_smoke"),
    (sm_st.get("Pending", 0), "En Pending"), (sm_st.get("Passed", 0), "En Passed"), (len(SMOKE) - sm_asig, "Sin asignar")])

page = f"""<title>Regresión PC 26.10.100</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;700&display=swap">
<style>{CSS}</style>
<main>
<header><h1>Regresión PC · 26.10.100</h1>
<p class="sub">Pruebas de la fase de regresión de PC Client con label RFA_26.10.100_Web: los End2End e impedidas elegidos por User Story y el smoke. Corte del {date.today():%d/%m/%Y}.</p></header>
<div class="tabs" role="tablist" aria-label="Bloque">
<button type="button" role="tab" class="tab" id="tab-reg" data-p="reg" aria-selected="true">Regresión por US · {total}</button>
<button type="button" role="tab" class="tab" id="tab-smoke" data-p="smoke" aria-selected="false">Smoke · {len(SMOKE)}</button>
</div>
<div class="panel" id="panel-reg" role="tabpanel" aria-labelledby="tab-reg">
<p class="sub">User Stories de PC Client (sin GoBFF) con una regresión reducida a la mitad. De cada US entran el camino principal y los End2End que en algún momento detectaron bugs Blocker, Critical o Major o no acabaron en Passed. A eso se suman las impedidas que afectan a reproducción, DRM, publicidad o a una US reabierta. El estado es la última ejecución con el label CC_26.10.100_Web; los bugs salen de todas las ejecuciones del TC.</p>
<div class="stats">{stats_html}</div>
<section class="prio"><h2>Por dónde empezar</h2><ul>
<li><b>Reproducción y DRM:</b> las cuatro de device binding de Nagra ({link("GO-36796")}) y las de cToken caducado ({link("MULTISTC-38383")}, {link("MULTISTC-67764")}). Playback Live ({link("GO-34943")}) no tiene ningún E2E.</li>
<li><b>Lo que no acabó en Passed:</b> compra y cancelación de suscripción ({link("MULTISTC-61019")}, {link("MULTISTC-61028")}, con sus bugs ya cerrados), Sports Details ({link("GO-35818")}) y las redirecciones ({link("GO-36164")} en Pending, {link("GO-36176")} reabierta).</li>
<li><b>Sesiones y perfiles:</b> liberación de sesión concurrente ({link("MULTISTC-64440")}), cambio entre perfil Kids y normal ({link("MULTISTC-64966")}) y suscripción pendiente de activación ({link("MULTISTC-54739")}).</li>
</ul></section>
{reparto}
<div class="ctrl" role="group" aria-label="Filtros">
<button type="button" id="f-todas" data-f="todas" aria-pressed="true">Todas</button>
<button type="button" id="f-nopass" data-f="nopass" aria-pressed="false">Sin Passed</button>
<button type="button" id="f-impeded" data-f="Impeded" aria-pressed="false">Impeded</button>
<button type="button" id="f-failed" data-f="Failed" aria-pressed="false">Failed</button>
<button type="button" id="f-bugs" data-f="bugs" aria-pressed="false">Con bugs</button>
<button type="button" id="f-e2e" data-f="e2e" aria-pressed="false">Solo End2End</button>
<button type="button" id="f-imp" data-f="imp" aria-pressed="false">Solo impedidas importantes</button>
<input type="search" id="q" placeholder="Buscar US, TC o texto" aria-label="Buscar">
</div>
<div id="lista">{"".join(bloques)}</div>
<p class="vacio" id="vacio" hidden>Ninguna prueba cumple el filtro.</p>
<section class="sin"><h2>US sin pruebas para regresión ({len(sin)})</h2>
<p class="sub">No tienen TCs End2End ni impedidas relevantes; en su mayoría son de BI, thumbnails o ajustes técnicos.</p><ul>{sinl}</ul></section>
</div>
<div class="panel" id="panel-smoke" role="tabpanel" aria-labelledby="tab-smoke" hidden>
<p class="sub">TCs SMOKE de PC (componente Excel_Smoke) con su ejecución RFA_26.10.100_Web, creadas el 15/10/2026. Ninguno tiene ejecución en la campaña CC_26.10.100_Web.</p>
<div class="stats">{smoke_stats}</div>
<div class="ctrl"><input type="search" id="qs" placeholder="Buscar suite, TC o texto" aria-label="Buscar en smoke"></div>
<div id="lista-smoke">{"".join(smoke_bloques)}</div>
<p class="vacio" id="vacio-smoke" hidden>Ningún smoke cumple la búsqueda.</p>
</div>
</main>
<script>{JS}</script>
"""
open(sys.argv[2], "w", encoding="utf-8").write(page)
print("OK", total, dict(cnt), len(bloques), len(sin))
