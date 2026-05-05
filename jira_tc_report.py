#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jira_tc_report.py
Genera informes HTML de Test Cases (scope End2End) asociados a cada User Story,
mostrando el estado de la última ejecución por plataforma.

NO sube resultados a Confluence.

Uso:
    python jira_tc_report.py
    python jira_tc_report.py --reports android
    python jira_tc_report.py --reports android ios

Credenciales: se leen del fichero .env (en la misma carpeta que este script).
"""

import argparse
import os
import sys
import re as _re
import requests
import urllib3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ── Carga de .env ─────────────────────────────────────────────────────────────
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if not os.environ.get(_k.strip()):
                os.environ[_k.strip()] = _v.strip()

# ── Configuración ──────────────────────────────────────────────────────────────
JIRA_BASE_URL = "https://jira.tid.es"
JIRA_TOKEN    = os.environ.get("JIRA_TOKEN", "")
SSL_VERIFY    = True
MAX_RESULTS   = 500

# IDs de campos custom detectados en esta instancia Jira
SPRINT_FIELD     = "customfield_11000"   # Sprint (formato string legado)
EPIC_LINK_FIELD  = "customfield_11600"   # Epic Link
TEST_SCOPE_FIELD = "customfield_10163"   # Test Scope (multi-select)

# Filtros para Test Cases
TC_LINK_OUTWARD = "is tested by"  # etiqueta outward del tipo de link "Tests"
TC_SCOPE_FILTER = None             # None = mostrar todos los scopes; "End2End" para filtrar

# ── Reportes ───────────────────────────────────────────────────────────────────
# execution_label: label que identifica la ejecución de cada plataforma/versión
# en los Test Case Execution (subtareas del TC en proyecto MULTISTC).
# Patrón: CC_{fixVersion}_{Platform}
# Ajusta si los labels de tu instancia difieren.
REPORTS = [
    {
        "key":             "android",
        "title":           "Android – Mobile Android · Fix Version 26.06.100",
        "output_file":     "jira_tc_report_android.html",
        "execution_label": "CC_26.06.100_Android",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "Mobile Android"'
        ),
    },
    {
        "key":             "ios",
        "title":           "iOS – Mobile iOS · Fix Version 26.06.100",
        "output_file":     "jira_tc_report_ios.html",
        "execution_label": "CC_26.06.100_iOS",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "Mobile iOS"'
        ),
    },
    {
        "key":             "tvos",
        "title":           "tvOS · Fix Version 26.06.100",
        "output_file":     "jira_tc_report_tvos.html",
        "execution_label": "CC_26.06.100_tvOS",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = tvOS'
        ),
    },
    {
        "key":             "pc",
        "title":           "PC Client · Fix Version 26.06.100",
        "output_file":     "jira_tc_report_pc.html",
        "execution_label": "CC_26.06.100_Web",
        "jql": (
            'project = "22830" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "PC Client"'
        ),
    },
    {
        "key":             "gobff",
        "title":           "GoBFF · Fix Version 26.06.100",
        "output_file":     "jira_tc_report_gobff.html",
        "execution_label": "CC_26.06.100_BFF",
        "jql": (
            'project = "22830" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = GoBFF'
        ),
    },
]

REPORT_KEYS = tuple(r["key"] for r in REPORTS)


# ── Argumentos CLI ─────────────────────────────────────────────────────────────
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera reportes HTML de Test Cases (End2End) por User Story."
    )
    parser.add_argument(
        "--reports",
        nargs="+",
        choices=REPORT_KEYS,
        metavar="REPORT",
        help=f"Reportes a generar. Opciones: {', '.join(REPORT_KEYS)}.",
    )
    return parser.parse_args(argv)


def get_selected_reports(args: argparse.Namespace) -> list[dict]:
    if args.reports:
        selected = set(args.reports)
        return [r for r in REPORTS if r["key"] in selected]
    return list(REPORTS)


# ── Badges de estado ───────────────────────────────────────────────────────────
STATUS_BADGE: dict[str, tuple[str, str]] = {
    # Estados de User Story
    "done":        ("badge-green",  "Done"),
    "closed":      ("badge-green",  "Closed"),
    "resolved":    ("badge-green",  "Resolved"),
    "in progress": ("badge-yellow", "In Progress"),
    "in review":   ("badge-yellow", "In Review"),
    "testing":     ("badge-blue",   "Testing"),
    "reopened":    ("badge-yellow", "Reopened"),
    "to do":       ("badge-gray",   "To Do"),
    "open":        ("badge-gray",   "Open"),
    "backlog":     ("badge-gray",   "Backlog"),
    "impeded":     ("badge-red",    "Impeded"),
    "blocked":     ("badge-red",    "Blocked"),
    # Estados de Test Case Execution
    "passed":      ("badge-green",  "Passed"),
    "failed":      ("badge-red",    "Failed"),
    "not run":     ("badge-gray",   "Not Run"),
    "wip":         ("badge-yellow", "WIP"),
    "aborted":     ("badge-red",    "Aborted"),
}

SCOPE_BADGE: dict[str, tuple[str, str]] = {
    "end2end":     ("badge-e2e",    "End2End"),
    "smoke":       ("badge-blue",   "Smoke"),
    "sanity":      ("badge-yellow", "Sanity"),
    "acceptance":  ("badge-green",  "Acceptance"),
    "system":      ("badge-gray",   "System"),
    "integration": ("badge-gray",   "Integration"),
    "component":   ("badge-gray",   "Component"),
}


def badge_html(status_name: str) -> str:
    if not status_name or status_name == "—":
        return '<span class="badge-empty">—</span>'
    key = status_name.lower()
    css_class, label = STATUS_BADGE.get(key, ("badge-blue", status_name))
    return f'<span class="badge {css_class}">{label}</span>'


def scope_badges_html(scope_values: list[str]) -> str:
    if not scope_values:
        return '<span class="badge-empty">—</span>'
    parts = []
    for sv in scope_values:
        # Normalizar para buscar en el mapa (quitar guiones/espacios)
        key = sv.lower().replace("-", "").replace(" ", "").replace("_", "").replace("2", "2")
        # Mapeo específico para variantes de End2End
        if "end2end" in key or "end-to-end" in sv.lower() or "e2e" in key:
            key = "end2end"
        css_class, label = SCOPE_BADGE.get(key, ("badge-gray", sv))
        parts.append(f'<span class="badge {css_class}">{label}</span>')
    return " ".join(parts)


def _esc(text: str) -> str:
    """Escapa entidades HTML básicas."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Cliente Jira ───────────────────────────────────────────────────────────────
def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {JIRA_TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def jira_search(jql: str, fields: list, max_results: int = MAX_RESULTS) -> list:
    """Búsqueda JQL paginada; devuelve todos los issues."""
    url      = f"{JIRA_BASE_URL}/rest/api/2/search"
    issues   = []
    start_at = 0
    page_size = 100

    while True:
        params = {
            "jql":        jql,
            "fields":     ",".join(fields),
            "maxResults": min(page_size, max_results - len(issues)),
            "startAt":    start_at,
        }
        resp = requests.get(
            url, headers=get_headers(), params=params,
            verify=SSL_VERIFY, timeout=30
        )
        resp.raise_for_status()
        data  = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)
        start_at += len(batch)
        if start_at >= data.get("total", 0) or not batch or len(issues) >= max_results:
            break

    return issues


def extract_sprint_name(fields: dict) -> str:
    """Extrae el nombre del sprint del campo legacy customfield_11000."""
    value = fields.get(SPRINT_FIELD)
    if not value:
        return "—"
    if isinstance(value, list) and value:
        raw = str(value[-1])
        m = _re.search(r"name=([^,\]]+)", raw)
        return m.group(1).strip() if m else raw[:60]
    if isinstance(value, dict):
        return value.get("name", "—")
    m = _re.search(r"name=([^,\]]+)", str(value))
    return m.group(1).strip() if m else str(value)[:60]


def fetch_user_stories(jql: str) -> list:
    """Recupera User Stories incluyendo issuelinks (necesarios para extraer TCs)."""
    return jira_search(
        jql,
        fields=["summary", "status", "labels", "issuelinks", SPRINT_FIELD, EPIC_LINK_FIELD],
    )


def extract_tc_keys(us_list: list) -> dict[str, list[str]]:
    """
    Extrae {us_key: [tc_key, ...]} a partir de los issuelinks de cada US.
    Solo incluye links outward cuyo label es 'is tested by' (tipo "Tests").
    """
    result: dict[str, list[str]] = {}
    for us in us_list:
        tc_keys = [
            link["outwardIssue"]["key"]
            for link in us["fields"].get("issuelinks", [])
            if link.get("type", {}).get("outward") == TC_LINK_OUTWARD
            and link.get("outwardIssue")
        ]
        result[us["key"]] = tc_keys
    return result


def fetch_test_cases(tc_keys: list[str]) -> dict[str, dict]:
    """
    Recupera en batch los detalles de los Test Cases.
    Devuelve {tc_key: {"summary": str, "scope": [str], "status": str,
                       "bugs": [{"key": str, "summary": str}]}}.
    Incluye los bugs detectados via issuelink outward "detects".
    """
    if not tc_keys:
        return {}

    result: dict[str, dict] = {}
    batch_size = 100

    for i in range(0, len(tc_keys), batch_size):
        batch   = tc_keys[i : i + batch_size]
        issues  = jira_search(
            f'issuekey in ({", ".join(batch)})',
            fields=["summary", "status", TEST_SCOPE_FIELD, "issuelinks"],
            max_results=len(batch),
        )
        for issue in issues:
            f         = issue["fields"]
            scope_raw = f.get(TEST_SCOPE_FIELD) or []
            if isinstance(scope_raw, list):
                scope_values = [s.get("value", "") for s in scope_raw if isinstance(s, dict)]
            elif isinstance(scope_raw, dict):
                scope_values = [scope_raw.get("value", "")]
            else:
                scope_values = []

            # Bugs: links outward cuyo tipo outward es "detects"
            bugs = [
                {
                    "key":     link["outwardIssue"]["key"],
                    "summary": link["outwardIssue"].get("fields", {}).get("summary", ""),
                    "status":  link["outwardIssue"].get("fields", {}).get("status", {}).get("name", ""),
                }
                for link in f.get("issuelinks", [])
                if link.get("type", {}).get("outward", "").lower() == "detects"
                and link.get("outwardIssue")
            ]

            result[issue["key"]] = {
                "summary": f.get("summary", "—"),
                "scope":   scope_values,
                "status":  f.get("status", {}).get("name", "—"),
                "bugs":    bugs,
            }

    return result


def fetch_tc_executions(tc_keys: list[str], execution_label: str) -> dict[str, dict]:
    """
    Recupera las Test Case Executions (subtareas) de los TCs dados que tengan
    el label de plataforma/versión indicado.
    Devuelve {tc_key: {"key": str, "status": str, "updated": str}}
    con la ejecución MÁS RECIENTE por TC (ordenada por 'updated' desc).
    """
    if not tc_keys:
        return {}

    result: dict[str, dict] = {}
    batch_size = 200

    for i in range(0, len(tc_keys), batch_size):
        batch      = tc_keys[i : i + batch_size]
        jql        = f'parent in ({", ".join(batch)}) AND labels = "{execution_label}"'
        executions = jira_search(
            jql,
            fields=["summary", "status", "parent", "updated"],
            max_results=5000,
        )

        by_parent: dict[str, list] = defaultdict(list)
        for ex in executions:
            parent_key = (ex["fields"].get("parent") or {}).get("key", "")
            if parent_key:
                by_parent[parent_key].append(ex)

        for parent_key, exs in by_parent.items():
            # Tomar la más reciente por fecha de actualización
            latest = max(exs, key=lambda x: x["fields"].get("updated", ""))
            lf     = latest["fields"]
            result[parent_key] = {
                "key":     latest["key"],
                "status":  lf["status"]["name"],
                "updated": (lf.get("updated") or "")[:10],
            }

    return result


def fetch_epic_info(epic_keys: list[str]) -> dict[str, str]:
    """Devuelve {epic_key: summary_str}."""
    if not epic_keys:
        return {}
    result: dict[str, str] = {}
    for i in range(0, len(epic_keys), 100):
        batch  = epic_keys[i : i + 100]
        issues = jira_search(
            f'issuekey in ({", ".join(batch)})',
            fields=["summary"],
            max_results=len(batch),
        )
        for issue in issues:
            result[issue["key"]] = issue["fields"].get("summary", issue["key"])
    return result


# ── Paleta épicas ──────────────────────────────────────────────────────────────
EPIC_PALETTE = [
    ("#ede9fe", "#5b21b6"), ("#fef3c7", "#92400e"), ("#dbeafe", "#1e40af"),
    ("#d1fae5", "#065f46"), ("#ffedd5", "#9a3412"), ("#fce7f3", "#9d174d"),
    ("#ecfccb", "#3f6212"), ("#e0f2fe", "#075985"), ("#fef9c3", "#713f12"),
    ("#f3e8ff", "#6b21a8"),
]


def _epic_color(epic_key: str, ordered_keys: list) -> tuple[str, str]:
    try:
        idx = ordered_keys.index(epic_key) % len(EPIC_PALETTE)
    except ValueError:
        idx = 0
    return EPIC_PALETTE[idx]


# ── CSS ────────────────────────────────────────────────────────────────────────
HTML_CSS = """
:root {
    --bg:           #f0f2f5;
    --surface:      #ffffff;
    --primary:      #0052cc;
    --primary-dark: #0747a6;
    --text:         #172b4d;
    --text-light:   #5e6c84;
    --border:       #dfe1e6;
    --radius:       8px;
    --shadow:       0 2px 8px rgba(0,0,0,.10);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 28px 24px 48px;
    min-height: 100vh;
}

/* ── Header ── */
header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    color: #fff;
    padding: 22px 28px;
    border-radius: var(--radius);
    margin-bottom: 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--shadow);
}
header h1 {
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: .3px;
    display: flex;
    align-items: center;
    gap: 10px;
}
header h1::before { content: "🧪"; font-size: 1.2rem; }
header .meta {
    font-size: .8rem;
    opacity: .88;
    text-align: right;
    line-height: 1.8;
}

/* ── Section card ── */
.section {
    background: var(--surface);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    margin-bottom: 36px;
    overflow: hidden;
    border: 1px solid var(--border);
}
.section-header {
    background: var(--primary-dark);
    color: #fff;
    padding: 14px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}
.section-header h2 { font-size: .95rem; font-weight: 700; }
.section-header .count {
    background: rgba(255,255,255,.20);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: .75rem;
    white-space: nowrap;
}

/* ── Table ── */
.table-wrapper { overflow-x: auto; }

table {
    width: 100%;
    border-collapse: collapse;
    font-size: .865rem;
}
thead th {
    background: #f7f8fa;
    color: var(--text-light);
    font-size: .72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .7px;
    padding: 10px 14px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 1;
}

tbody tr { border-bottom: 1px solid var(--border); }
tbody tr:last-child { border-bottom: none; }

/* ── Fila de US (cabecera de grupo) ── */
tr.us-row td {
    background: #eef2ff;
    border-top: 2px solid #c5d4f0;
    border-bottom: 1px solid #c5d4f0;
    padding: 9px 14px;
    vertical-align: middle;
}
tr.us-row .us-key-link {
    color: var(--primary-dark);
    text-decoration: none;
    font-weight: 700;
    font-size: .88rem;
    margin-right: 4px;
}
tr.us-row .us-key-link:hover { text-decoration: underline; }
tr.us-row .us-title {
    color: var(--text);
    font-size: .85rem;
    font-weight: 600;
    padding: 0 10px;
}
tr.us-row .us-badge { margin: 0 6px; }
tr.us-row .us-meta {
    font-size: .78rem;
    color: var(--text-light);
    white-space: nowrap;
    padding: 0 6px;
}

/* ── Fila de TC ── */
tr.tc-row { transition: background .12s; }
tr.tc-row:hover { filter: brightness(.96); }
tr.tc-row td { padding: 9px 14px; vertical-align: middle; }

/* Colores de fila por resultado de ejecución (línea completa) */
tr.tc-passed,
tr.tc-passed td  { background: #c9ecd6; }
tr.tc-failed,
tr.tc-failed td  { background: #f7cfcf; }
tr.tc-impeded,
tr.tc-impeded td { background: #f3e7b3; }

tr.tc-passed td:first-child  { border-left: 4px solid #36b37e; padding-left: 18px; }
tr.tc-failed td:first-child  { border-left: 4px solid #ff5630; padding-left: 18px; }
tr.tc-impeded td:first-child { border-left: 4px solid #ffab00; padding-left: 18px; }
tr.tc-row td:first-child     { border-left: 4px solid #c7d2fe; padding-left: 18px; }

/* ── Columna Bugs ── */
td.bugs-col { font-size: .78rem; white-space: nowrap; }
td.bugs-col a {
    display: inline-block;
    background: #ffebe6;
    color: #bf2600;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: .70rem;
    font-weight: 700;
    text-decoration: none;
    margin: 1px 2px;
    white-space: nowrap;
}
td.bugs-col a:hover { background: #ff5630; color: #fff; }

/* ── Sin TCs ── */
tr.no-tc-row td {
    background: #fafafa;
    color: #b3bac5;
    font-style: italic;
    font-size: .82rem;
    padding: 8px 14px 8px 22px;
    border-left: 4px solid #e5e7eb;
}

/* ── Columnas ── */
td.id-col { white-space: nowrap; }
td.id-col a {
    color: var(--primary);
    text-decoration: none;
    font-weight: 700;
    font-size: .84rem;
}
td.id-col a:hover { text-decoration: underline; color: var(--primary-dark); }

td.title-col { max-width: 300px; }
td.title-col span {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.45;
}

td.exec-id-col { white-space: nowrap; }
td.exec-id-col a {
    color: var(--text-light);
    text-decoration: none;
    font-size: .78rem;
}
td.exec-id-col a:hover { text-decoration: underline; color: var(--primary); }

td.date-col {
    white-space: nowrap;
    color: var(--text-light);
    font-size: .78rem;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 12px;
    font-size: .70rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .5px;
    white-space: nowrap;
}
.badge-green  { background: #e3fcef; color: #006644; }
.badge-yellow { background: #fff7c0; color: #7a5800; }
.badge-blue   { background: #deebff; color: #0052cc; }
.badge-red    { background: #ffebe6; color: #bf2600; }
.badge-gray   { background: #f4f5f7; color: #5e6c84; border: 1px solid #dfe1e6; }
.badge-e2e    { background: #ede9fe; color: #5b21b6; }
.badge-empty  {
    color: #b3bac5;
    font-style: italic;
    font-size: .75rem;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
}

/* ── Warning sin E2E ── */
.warn-e2e {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: #fff8e1;
    color: #b45309;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: .68rem;
    font-weight: 700;
    white-space: nowrap;
    margin-left: 8px;
}

/* ── Summary box ── */
.summary-wrap {
    background: var(--surface);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    margin-top: 8px;
    margin-bottom: 36px;
    padding: 24px 28px;
}
.summary-wrap h3 {
    font-size: .95rem;
    font-weight: 700;
    color: var(--primary-dark);
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.summary-cards {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.stat-card {
    flex: 1;
    min-width: 120px;
    border-radius: 8px;
    padding: 14px 18px;
    text-align: center;
}
.stat-card .val {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.1;
    display: block;
}
.stat-card .lbl {
    font-size: .72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .6px;
    margin-top: 4px;
    display: block;
}
.stat-card .pct {
    font-size: .80rem;
    font-weight: 600;
    margin-top: 2px;
    display: block;
    opacity: .80;
}
.stat-card.s-total   { background: #eef2ff; color: #1e3a8a; }
.stat-card.s-passed  { background: #e3fcef; color: #006644; }
.stat-card.s-failed  { background: #ffebe6; color: #bf2600; }
.stat-card.s-impeded { background: #fff7c0; color: #7a5800; }
.stat-card.s-pending { background: #f4f5f7; color: #5e6c84; border: 1px solid #dfe1e6; }

/* ── Progress bar ── */
.progress-bar-wrap { margin-top: 4px; }
.progress-bar-wrap .pb-label {
    font-size: .72rem;
    color: var(--text-light);
    margin-bottom: 6px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .5px;
}
.progress-bar {
    height: 16px;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    background: #f4f5f7;
}
.pb-passed  { background: #36b37e; transition: width .3s; }
.pb-failed  { background: #ff5630; transition: width .3s; }
.pb-impeded { background: #ffab00; transition: width .3s; }
.pb-pending { background: #dfe1e6; transition: width .3s; }

/* ── Mensaje sin resultados ── */
.empty-msg {
    padding: 28px;
    text-align: center;
    color: var(--text-light);
    font-size: .875rem;
}

/* ── Footer ── */
footer {
    text-align: center;
    color: var(--text-light);
    font-size: .75rem;
    margin-top: 8px;
}
"""


# ── Renderizado de sección HTML ────────────────────────────────────────────────
def render_section(
    title:         str,
    issues:        list,
    us_tc_map:     dict[str, list[str]],   # us_key -> [tc_key] (ya filtrado a End2End)
    tc_details:    dict[str, dict],        # tc_key -> {summary, scope, status}
    execution_map: dict[str, dict],        # tc_key -> {key, status, updated}
    epics_map:     dict[str, str] | None = None,
) -> str:
    if not issues:
        return f"""
    <div class="section">
      <div class="section-header">
        <h2>{title}</h2><span class="count">0 USs</span>
      </div>
      <div class="empty-msg">No se encontraron User Stories para esta query.</div>
    </div>"""

    if epics_map is None:
        epics_map = {}
    ordered_epic_keys = sorted(epics_map.keys())

    rows_html: list[str] = []
    total_tcs = 0
    stats: dict[str, int] = {"passed": 0, "failed": 0, "impeded": 0, "pending": 0}

    for issue in issues:
        f       = issue["fields"]
        us_key  = issue["key"]
        us_url  = f"{JIRA_BASE_URL}/browse/{us_key}"
        summary = _esc(f.get("summary", "—"))
        status  = f["status"]["name"]
        sprint  = extract_sprint_name(f)

        # Epic badge
        epic_key   = f.get(EPIC_LINK_FIELD) or ""
        epic_title = _esc(epics_map.get(epic_key, epic_key)) if epic_key else ""
        if epic_key:
            ebg, efg  = _epic_color(epic_key, ordered_epic_keys)
            epic_html = (
                f'<a href="{JIRA_BASE_URL}/browse/{_esc(epic_key)}" target="_blank" '
                f'style="background:{ebg};color:{efg};padding:2px 8px;border-radius:10px;'
                f'font-size:.70rem;font-weight:700;text-decoration:none;white-space:nowrap;'
                f'margin-left:6px;">{epic_title}</a>'
            )
        else:
            epic_html = ""

        sprint_html = (
            f'<span class="us-meta">· {_esc(sprint)}</span>'
            if sprint and sprint != "—" else ""
        )

        # ── Warning E2E ──────────────────────────────────────────────────────
        has_e2e = any(
            "end2end" in s.lower()
            for k in us_tc_map.get(us_key, [])
            for s in (tc_details.get(k) or {}).get("scope", [])
        )
        warn_html = (
            ''
            if has_e2e
            else '<span class="warn-e2e">&#x26A0; Sin E2E</span>'
        )

        # ── Fila cabecera de US ──────────────────────────────────────────────
        rows_html.append(
            f'<tr class="us-row">'
            f'<td colspan="7">'
            f'<a class="us-key-link" href="{us_url}" target="_blank">{us_key}</a>'
            f'<span class="us-title" title="{summary}">{summary}</span>'
            f'<span class="us-badge">{badge_html(status)}</span>'
            f'{sprint_html}'
            f'{epic_html}'
            f'{warn_html}'
            f'</td>'
            f'</tr>'
        )

        # ── Filas de Test Cases ──────────────────────────────────────────────
        tc_keys = us_tc_map.get(us_key, [])

        if not tc_keys:
            rows_html.append(
                '<tr class="no-tc-row"><td colspan="7">'
                'Sin test cases vinculados'
                '</td></tr>'
            )
            continue

        for tc_key in tc_keys:
            tc = tc_details.get(tc_key)
            if not tc:
                continue

            tc_summary = _esc(tc.get("summary", "—"))
            tc_url     = f"{JIRA_BASE_URL}/browse/{tc_key}"
            scope_html = scope_badges_html(tc.get("scope", []))

            # Bugs detectados (issuelink outward "detects")
            bugs = [b for b in tc.get("bugs", []) if b.get("status", "").lower() != "closed"]
            if bugs:
                bug_parts = []
                for b in bugs:
                    bug_parts.append(
                        f'<a href="{JIRA_BASE_URL}/browse/{b["key"]}" target="_blank" '
                        f'title="{_esc(b["summary"])}">{b["key"]}</a>'
                    )
                bugs_html = "<td class='bugs-col'>" + "".join(bug_parts) + "</td>"
            else:
                bugs_html = '<td class="bugs-col" style="color:#b3bac5;">—</td>'

            exec_info  = execution_map.get(tc_key)
            if exec_info:
                exec_url        = f"{JIRA_BASE_URL}/browse/{exec_info['key']}"
                exec_status_html = (
                    f'<a href="{exec_url}" target="_blank" style="text-decoration:none;">'
                    f'{badge_html(exec_info["status"])}</a>'
                )
                exec_key_html   = f'<a href="{exec_url}" target="_blank">{exec_info["key"]}</a>'
                exec_date       = exec_info["updated"]
                stat_key = exec_info["status"].lower()
                if stat_key == "passed":
                    stats["passed"] += 1
                    row_class = "tc-row tc-passed"
                elif stat_key == "failed":
                    stats["failed"] += 1
                    row_class = "tc-row tc-failed"
                elif stat_key == "impeded":
                    stats["impeded"] += 1
                    row_class = "tc-row tc-impeded"
                else:
                    stats["pending"] += 1
                    row_class = "tc-row"
            else:
                exec_status_html = '<span class="badge badge-gray">Sin ejecución</span>'
                exec_key_html   = "—"
                exec_date       = "—"
                stats["pending"] += 1
                row_class = "tc-row"

            rows_html.append(
                f'<tr class="{row_class}">'
                f'<td class="id-col"><a href="{tc_url}" target="_blank">{tc_key}</a></td>'
                f'<td class="title-col"><span title="{tc_summary}">{tc_summary}</span></td>'
                f'<td>{scope_html}</td>'
                f'<td>{exec_status_html}</td>'
                f'<td class="exec-id-col">{exec_key_html}</td>'
                f'<td class="date-col">{exec_date}</td>'
                f'{bugs_html}'
                f'</tr>'
            )
            total_tcs += 1

    count_us   = len(issues)
    table_body = "\n".join(rows_html)

    # ── Porcentajes para el resumen ────────────────────────────────────────
    tfc         = total_tcs or 1
    n_passed    = stats["passed"]
    n_failed    = stats["failed"]
    n_impeded   = stats["impeded"]
    n_pending   = stats["pending"]
    pct_passed  = n_passed  / tfc * 100
    pct_failed  = n_failed  / tfc * 100
    pct_impeded = n_impeded / tfc * 100
    pct_pending = n_pending / tfc * 100
    summary_box = (
        f'<div class="summary-wrap">'
        f'<h3>&#x1F4CA; Resumen de ejecuci&oacute;n &nbsp;&middot;&nbsp; {total_tcs} Test Cases</h3>'
        f'<div class="summary-cards">'
        f'<div class="stat-card s-total"><span class="val">{total_tcs}</span><span class="lbl">Total TCs</span></div>'
        f'<div class="stat-card s-passed"><span class="val">{n_passed}</span><span class="lbl">Passed</span><span class="pct">{pct_passed:.0f}%</span></div>'
        f'<div class="stat-card s-failed"><span class="val">{n_failed}</span><span class="lbl">Failed</span><span class="pct">{pct_failed:.0f}%</span></div>'
        f'<div class="stat-card s-impeded"><span class="val">{n_impeded}</span><span class="lbl">Impeded</span><span class="pct">{pct_impeded:.0f}%</span></div>'
        f'<div class="stat-card s-pending"><span class="val">{n_pending}</span><span class="lbl">Pending</span><span class="pct">{pct_pending:.0f}%</span></div>'
        f'</div>'
        f'<div class="progress-bar-wrap">'
        f'<div class="pb-label">Distribuci&oacute;n</div>'
        f'<div class="progress-bar">'
        f'<div class="pb-passed"  style="width:{pct_passed:.1f}%"  title="Passed &middot; {pct_passed:.0f}%"></div>'
        f'<div class="pb-failed"  style="width:{pct_failed:.1f}%"  title="Failed &middot; {pct_failed:.0f}%"></div>'
        f'<div class="pb-impeded" style="width:{pct_impeded:.1f}%" title="Impeded &middot; {pct_impeded:.0f}%"></div>'
        f'<div class="pb-pending" style="width:{pct_pending:.1f}%" title="Pending &middot; {pct_pending:.0f}%"></div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    return f"""
    <div class="section">
      <div class="section-header">
        <h2>{title}</h2>
        <span class="count">
          {count_us} User {'Story' if count_us == 1 else 'Stories'}
          &nbsp;·&nbsp; {total_tcs} Test Cases
        </span>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>TC ID</th>
              <th>Título del Test Case</th>
              <th>Test Scope</th>
              <th>Última Ejecución</th>
              <th>Ejecución ID</th>
              <th>Fecha</th>
              <th>Bugs</th>
            </tr>
          </thead>
          <tbody>
{table_body}
          </tbody>
        </table>
      </div>
    </div>
{summary_box}"""


def generate_html(section_html: str, title: str, timestamp: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} – TC Report</title>
  <style>
{HTML_CSS}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class="meta">
      <div>Generado el {timestamp}</div>
      <div>{JIRA_BASE_URL}</div>
    </div>
  </header>

  {section_html}

  <footer>
    Generado automáticamente por <strong>jira_tc_report</strong> · {timestamp}
    · Todos los Test Cases
  </footer>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> None:
    args             = parse_args(argv)
    selected_reports = get_selected_reports(args)

    if not JIRA_TOKEN:
        print("[ERROR] Token de Jira no configurado.")
        print("        Define JIRA_TOKEN en el fichero .env o como variable de entorno.")
        sys.exit(1)

    if not SSL_VERIFY:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    generated: list[str] = []

    print(f"[i] Reportes seleccionados: {', '.join(r['key'] for r in selected_reports)}")
    scope_label = TC_SCOPE_FILTER if TC_SCOPE_FILTER else "Todos"
    print(f"[i] Filtro scope: {scope_label}")

    for q in selected_reports:
        out_file    = q["output_file"]
        exec_label  = q["execution_label"]
        print(f"\n[→] {q['title']}")
        print(f"    Salida:      {out_file}")
        print(f"    Exec label:  {exec_label}")
        print(f"    JQL:         {q['jql']}")

        try:
            # 1. Recuperar User Stories (con issuelinks)
            issues = fetch_user_stories(q["jql"])
            print(f"    {len(issues)} User Stories encontradas.")

            # 2. Extraer TC keys de los issuelinks de las US
            us_tc_map_all = extract_tc_keys(issues)
            all_tc_keys   = list({k for keys in us_tc_map_all.values() for k in keys})
            print(f"    {len(all_tc_keys)} Test Cases vinculados (todos los scopes).")

            # 3. Recuperar detalles de TCs (summary, scope, status)
            tc_details: dict[str, dict] = {}
            if all_tc_keys:
                print("    Cargando detalles de Test Cases …")
                tc_details = fetch_test_cases(all_tc_keys)

            # 4. Filtrar por scope (si TC_SCOPE_FILTER es None, se incluyen todos)
            if TC_SCOPE_FILTER:
                e2e_keys = {
                    k for k, v in tc_details.items()
                    if any(TC_SCOPE_FILTER.lower() in s.lower() for s in v.get("scope", []))
                }
                print(f"    {len(e2e_keys)} Test Cases con scope {TC_SCOPE_FILTER}.")
                us_tc_map_e2e = {
                    us_key: [k for k in keys if k in e2e_keys]
                    for us_key, keys in us_tc_map_all.items()
                }
            else:
                e2e_keys = set(tc_details.keys())
                us_tc_map_e2e = us_tc_map_all
                print(f"    {len(e2e_keys)} Test Cases (sin filtro de scope).")

            # 5. Recuperar ejecuciones por plataforma (solo para TCs End2End)
            execution_map: dict[str, dict] = {}
            if e2e_keys:
                print(f"    Cargando Test Case Executions (label: {exec_label}) …")
                execution_map = fetch_tc_executions(list(e2e_keys), exec_label)
                covered = sum(1 for k in e2e_keys if k in execution_map)
                print(f"    Cobertura: {covered}/{len(e2e_keys)} TCs con ejecución registrada.")
            else:
                execution_map = {}

            # 6. Recuperar títulos de épicas
            epic_keys = sorted({
                i["fields"].get(EPIC_LINK_FIELD) or ""
                for i in issues
            } - {""})
            epics_map: dict[str, str] = {}
            if epic_keys:
                print(f"    Cargando títulos de épicas ({len(epic_keys)}) …")
                try:
                    epics_map = fetch_epic_info(epic_keys)
                except Exception as exc:
                    print(f"    [WARN] No se pudieron cargar épicas: {exc}")

            section = render_section(
                q["title"], issues, us_tc_map_e2e, tc_details, execution_map, epics_map
            )

        except requests.HTTPError as exc:
            code = exc.response.status_code
            body = exc.response.text[:300]
            print(f"    [ERROR HTTP {code}] {body}")
            section = render_section(q["title"], [], {}, {}, {})

        except requests.ConnectionError:
            print(f"    [ERROR] No se puede conectar a {JIRA_BASE_URL}.")
            section = render_section(q["title"], [], {}, {}, {})

        except Exception as exc:
            print(f"    [ERROR] {exc}")
            section = render_section(q["title"], [], {}, {}, {})

        html = generate_html(section, q["title"], timestamp)
        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"    [✓] Generado: {out_file}")
        generated.append(out_file)

    print(f"\n[✓] {len(generated)} informe(s) generados:")
    for f in generated:
        print(f"    {f}")


if __name__ == "__main__":
    main()
