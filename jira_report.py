#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jira_report.py
Genera informes HTML enriquecidos con User Stories de Jira
y el estado de sus subtareas QA (Test Design / Test Execution).

Uso:
    python jira_report.py
    python jira_report.py --reports android ios

Credenciales: se leen del fichero .env (en la misma carpeta que este script).
Nunca incluyas tokens en el código fuente ni los compartas.
"""

import argparse
import os
import sys
import requests
import urllib3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ── Carga de .env ────────────────────────────────────────────────────────────
o_env = Path(__file__).parent / ".env"
if o_env.exists():
    for _line in o_env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _key = _k.strip()
            if not os.environ.get(_key):
                os.environ[_key] = _v.strip()

#  CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────

JIRA_BASE_URL = "https://jira.tid.es"

# Tokens: se leen exclusivamente de variables de entorno (cargadas desde .env).
# Nunca escribas un token directamente en este fichero.
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")

# ── Confluence ────────────────────────────────────────────────────────────────
CONFLUENCE_BASE_URL = "https://confluence.tid.es"
CONFLUENCE_TOKEN    = os.environ.get("CONFLUENCE_TOKEN", "")

# Si el entorno corporativo usa certificados internos y hay errores SSL,
# cambia SSL_VERIFY a False (reduce la seguridad, solo en redes de confianza).
SSL_VERIFY = True

MAX_RESULTS = 500   # máximo de User Stories a recuperar por query

# Subcadenas del summary para identificar las subtareas QA
QA_TEST_DESIGN    = "[QA] US Test Design"
QA_TEST_EXECUTION = "[QA] US Test Execution"

# ── Queries – cada entrada genera su propio fichero HTML ────────────────────
REPORTS = [
    {
        "key":                "android",
        "kind":               "device",
        "title":              "Android – Mobile Android · Fix Version 26.06.100",
        "output_file":        "jira_report_android.html",
        "confluence_page_id": "747276234",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "Mobile Android"'
        ),
    },
    {
        "key":                "ios",
        "kind":               "device",
        "title":              "iOS – Mobile iOS · Fix Version 26.06.100",
        "output_file":        "jira_report_ios.html",
        "confluence_page_id": "747276241",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "Mobile iOS"'
        ),
    },
    {
        "key":                "tvos",
        "kind":               "device",
        "title":              "tvOS · Fix Version 26.06.100",
        "output_file":        "jira_report_tvos.html",
        "confluence_page_id": "747276477",
        "jql": (
            'project = "24030" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = tvOS'
        ),
    },
    {
        "key":                "pc",
        "kind":               "device",
        "title":              "PC Client · Fix Version 26.06.100",
        "output_file":        "jira_report_pc.html",
        "confluence_page_id": "747276472",
        "jql": (
            'project = "22830" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = "PC Client"'
        ),
    },
    {
        "key":                "gobff",
        "kind":               "service",
        "title":              "GoBFF · Fix Version 26.06.100",
        "output_file":        "jira_report_gobff.html",
        "confluence_page_id": "747276475",
        "jql": (
            'project = "22830" AND issuetype = "User Story"'
            ' AND fixVersion = 26.06.100 AND component = GoBFF'
        ),
    },
]

REPORT_KEYS = tuple(report["key"] for report in REPORTS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera reportes QA de Jira para plataformas y dispositivos."
    )
    parser.add_argument(
        "--reports",
        nargs="+",
        choices=REPORT_KEYS,
        metavar="REPORT",
        help=(
            "Lista explícita de reportes a generar. "
            f"Opciones: {', '.join(REPORT_KEYS)}."
        ),
    )
    return parser.parse_args(argv)


def get_selected_reports(args: argparse.Namespace) -> list[dict]:
    if args.reports:
        selected_keys = set(args.reports)
        return [report for report in REPORTS if report["key"] in selected_keys]

    return list(REPORTS)

# ──────────────────────────────────────────────────────────────────────────────
#  ORDEN Y COLORES DE ESTADOS
# ──────────────────────────────────────────────────────────────────────────────

# Cuanto menor el número, más arriba aparece el grupo en la tabla
STATUS_ORDER = {
    "done":        0,
    "closed":      1,
    "resolved":    2,
    "in progress": 3,
    "in review":   4,
    "testing":     5,
    "reopened":    6,
    "to do":       7,
    "open":        8,
    "backlog":     9,
    "impeded":     10,
    "blocked":     11,
}

STATUS_BADGE = {
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
}


def status_sort_key(status_name: str) -> int:
    return STATUS_ORDER.get(status_name.lower(), 50)


# Colores de estado para el macro nativo de Confluence
CONFLUENCE_STATUS_COLOR = {
    "done":        ("Green",  "Done"),
    "closed":      ("Green",  "Closed"),
    "resolved":    ("Green",  "Resolved"),
    "in progress": ("Yellow", "In Progress"),
    "in review":   ("Yellow", "In Review"),
    "testing":     ("Blue",   "Testing"),
    "reopened":    ("Yellow", "Reopened"),
    "to do":       ("Grey",   "To Do"),
    "open":        ("Grey",   "Open"),
    "backlog":     ("Grey",   "Backlog"),
    "impeded":     ("Red",    "Impeded"),
    "blocked":     ("Red",    "Blocked"),
}


# ──────────────────────────────────────────────────────────────────────────────
#  CLIENTE JIRA
# ──────────────────────────────────────────────────────────────────────────────

def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {JIRA_TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def jira_search(jql: str, fields: list, max_results: int = MAX_RESULTS) -> list:
    """Ejecuta una búsqueda JQL paginada y devuelve todos los issues."""
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


# Campo sprint en esta instancia de Jira (detectado: customfield_11000, formato string legado)
SPRINT_FIELD = "customfield_11000"

# Campo Epic Link (customfield_11600 en esta instancia de Jira)
EPIC_LINK_FIELD = "customfield_11600"

import re as _re

def extract_sprint_name(fields: dict) -> str:
    """Extrae el nombre del sprint del campo customfield_11000 (formato string legado Jira)."""
    value = fields.get(SPRINT_FIELD)
    if not value:
        return "—"
    # Es una lista de strings con formato:
    # "com.atlassian.greenhopper...Sprint@xxx[...name=GO 26.06.100 SP2,...]"
    if isinstance(value, list) and value:
        # Tomar el último elemento (sprint más reciente)
        raw = str(value[-1])
        m = _re.search(r"name=([^,\]]+)", raw)
        return m.group(1).strip() if m else raw[:60]
    if isinstance(value, dict):
        return value.get("name", "—")
    # String directo
    m = _re.search(r"name=([^,\]]+)", str(value))
    return m.group(1).strip() if m else str(value)[:60]


def fetch_user_stories(jql: str) -> list:
    return jira_search(
        jql,
        fields=["summary", "status", "assignee", "subtasks", "labels", SPRINT_FIELD, EPIC_LINK_FIELD],
    )


def fetch_qa_subtasks(parent_keys: list) -> dict:
    """
    Busca en Jira todas las subtareas QA de los parents dados.
    Devuelve:
        { parent_key: { "design": {"status":…, "assignee":…},
                        "execution": {"status":…, "assignee":…} } }
    """
    if not parent_keys:
        return {}

    result = defaultdict(lambda: {"design": None, "execution": None})

    # Jira limita la cláusula IN; trabajamos en lotes de 200
    batch_size = 200
    for i in range(0, len(parent_keys), batch_size):
        batch    = parent_keys[i : i + batch_size]
        keys_str = ", ".join(batch)
        jql = (
            f'parent in ({keys_str})'
            f' AND (summary ~ "US Test Design" OR summary ~ "US Test Execution")'
        )
        subtasks = jira_search(
            jql,
            fields=["summary", "status", "assignee", "parent"],
            max_results=5000,
        )

        for st in subtasks:
            f            = st["fields"]
            summary      = f.get("summary", "")
            status_name  = f.get("status", {}).get("name", "—")
            assignee_obj = f.get("assignee") or {}
            assignee     = assignee_obj.get("displayName", "—")
            parent_key   = f.get("parent", {}).get("key", "")

            if not parent_key:
                continue

            entry = {"status": status_name, "assignee": assignee}

            if QA_TEST_DESIGN.lower() in summary.lower():
                result[parent_key]["design"] = entry
            elif QA_TEST_EXECUTION.lower() in summary.lower():
                result[parent_key]["execution"] = entry

    return result


def fetch_epic_info(epic_keys: list) -> dict:
    """
    Devuelve {epic_key: {"summary": str}} para las epics dadas.
    """
    if not epic_keys:
        return {}
    result = {}
    batch_size = 100
    for i in range(0, len(epic_keys), batch_size):
        batch    = epic_keys[i : i + batch_size]
        keys_str = ", ".join(batch)
        issues   = jira_search(
            f"issuekey in ({keys_str})",
            fields=["summary"],
            max_results=len(batch),
        )
        for issue in issues:
            result[issue["key"]] = issue["fields"].get("summary", issue["key"])
    return result


# ──────────────────────────────────────────────────────────────────────────────
#  PALETA DE COLORES POR ÉPICA
# ──────────────────────────────────────────────────────────────────────────────

# Pares (background, color-texto) para HTML
EPIC_PALETTE_HTML = [
    ("#ede9fe", "#5b21b6"),  # violeta
    ("#fef3c7", "#92400e"),  # ámbar
    ("#dbeafe", "#1e40af"),  # azul
    ("#d1fae5", "#065f46"),  # esmeralda
    ("#ffedd5", "#9a3412"),  # naranja
    ("#fce7f3", "#9d174d"),  # rosa
    ("#ecfccb", "#3f6212"),  # lima
    ("#e0f2fe", "#075985"),  # celeste
    ("#fef9c3", "#713f12"),  # amarillo
    ("#f3e8ff", "#6b21a8"),  # lila
]

# Pares (background, color-texto) para Confluence storage (inline style)
EPIC_PALETTE_CONF = [
    ("#ede9fe", "#5b21b6"),
    ("#fef3c7", "#92400e"),
    ("#dbeafe", "#1e40af"),
    ("#d1fae5", "#065f46"),
    ("#ffedd5", "#9a3412"),
    ("#fce7f3", "#9d174d"),
    ("#ecfccb", "#3f6212"),
    ("#e0f2fe", "#075985"),
    ("#fef9c3", "#713f12"),
    ("#f3e8ff", "#6b21a8"),
]


def _epic_color_index(epic_key: str, ordered_keys: list) -> int:
    """Devuelve el índice de color (cíclico) para una clave de épica."""
    try:
        return ordered_keys.index(epic_key) % len(EPIC_PALETTE_HTML)
    except ValueError:
        return 0


# ──────────────────────────────────────────────────────────────────────────────
#  CONFLUENCE – CLIENTE Y RENDERIZADOR NATIVO
# ──────────────────────────────────────────────────────────────────────────────

def get_confluence_headers() -> dict:
    return {
        "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _xesc(text: str) -> str:
    """Escapa los caracteres especiales XML en un texto plano."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# Estilos inline por color para el formato storage de Confluence
_CONFL_STYLE = {
    "Green":  "background:#e3fcef;color:#006644;",
    "Yellow": "background:#fff7c0;color:#7a5800;",
    "Blue":   "background:#deebff;color:#0052cc;",
    "Red":    "background:#ffebe6;color:#bf2600;",
    "Grey":   "background:#f4f5f7;color:#5e6c84;border:1px solid #dfe1e6;",
}


def confluence_status_macro(status_name: str) -> str:
    """Devuelve un span con estilo inline para mostrar un estado coloreado en Confluence."""
    if not status_name or status_name == "\u2014":
        return "\u2014"
    colour, label = CONFLUENCE_STATUS_COLOR.get(status_name.lower(), ("Blue", status_name))
    style = _CONFL_STYLE.get(colour, _CONFL_STYLE["Blue"])
    return (
        f'<strong style="{style}padding:2px 6px;border-radius:3px;'
        f'font-size:11px;font-family:sans-serif;white-space:nowrap;">{label}</strong>'
    )


def render_confluence_storage(title: str, issues: list, subtasks_map: dict, timestamp: str, epics_map: dict | None = None) -> str:
    """Genera el cuerpo de la página en formato Confluence Storage (XHTML nativo)."""
    if not issues:
        return f"<p>No se encontraron User Stories. ({timestamp})</p>"

    if epics_map is None:
        epics_map = {}
    ordered_epic_keys = sorted(epics_map.keys())

    issues_sorted = sorted(
        issues,
        key=lambda i: status_sort_key(i["fields"]["status"]["name"])
    )

    rows = []
    current_group = None

    for issue in issues_sorted:
        f          = issue["fields"]
        key        = issue["key"]
        status     = f["status"]["name"]
        title_text = _xesc(f.get("summary", "—"))
        issue_url  = f"{JIRA_BASE_URL}/browse/{key}"
        sprint     = _xesc(extract_sprint_name(f))
        labels_raw = f.get("labels") or []
        labels_txt = _xesc(", ".join(labels_raw)) if labels_raw else "—"

        qa        = subtasks_map.get(key, {})
        design    = qa.get("design")    or {}
        execution = qa.get("execution") or {}

        d_status   = design.get("status",   "—")
        d_assignee = _xesc(design.get("assignee", "—"))
        e_status   = execution.get("status",   "—")
        e_assignee = _xesc(execution.get("assignee", "—"))

        epic_key   = f.get(EPIC_LINK_FIELD) or ""
        epic_title = _xesc(epics_map.get(epic_key, epic_key)) if epic_key else ""
        if epic_key:
            idx        = _epic_color_index(epic_key, ordered_epic_keys)
            ebg, efg   = EPIC_PALETTE_CONF[idx]
            epic_style = f"background:{ebg};color:{efg};padding:2px 8px;border-radius:3px;font-size:11px;font-family:sans-serif;white-space:nowrap;"
            epic_url   = f"{JIRA_BASE_URL}/browse/{_xesc(epic_key)}"
            epic_cell  = f'<a href="{epic_url}" style="{epic_style}font-weight:600;text-decoration:none;">{epic_title}</a>'
        else:
            epic_cell = "—"

        if status != current_group:
            current_group = status
            _, label = CONFLUENCE_STATUS_COLOR.get(status.lower(), ("Blue", status))
            rows.append(
                f'<tr><td colspan="10" style="background-color:#eef2ff;">'
                f'<strong>{label}</strong></td></tr>'
            )

        rows.append(
            f"<tr>"
            f'<td><a href="{issue_url}">{key}</a></td>'
            f"<td>{title_text}</td>"
            f"<td>{sprint}</td>"
            f"<td>{confluence_status_macro(status)}</td>"
            f"<td>{confluence_status_macro(d_status)}</td>"
            f"<td>{d_assignee}</td>"
            f"<td>{confluence_status_macro(e_status)}</td>"
            f"<td>{e_assignee}</td>"
            f"<td>{labels_txt}</td>"
            f"<td>{epic_cell}</td>"
            f"</tr>"
        )

    rows_html = "\n".join(rows)
    count = len(issues)

    return (
        "<p><em>Actualizado autom&aacute;ticamente por SeguimientoGO"
        f" &middot; {timestamp} &middot; {count} User Stories</em></p>"
        "<table><tbody>"
        "<tr>"
        "<th>ID Jira</th>"
        "<th>T&iacute;tulo</th>"
        "<th>Sprint</th>"
        "<th>Estado US</th>"
        "<th>Test Design &ndash; Estado</th>"
        "<th>Test Design &ndash; Assignee</th>"
        "<th>Test Execution &ndash; Estado</th>"
        "<th>Test Execution &ndash; Assignee</th>"
        "<th>Labels</th>"
        "<th>Epic Link</th>"
        "</tr>"
        + rows_html
        + "</tbody></table>"
    )


def update_confluence_page(page_id: str, storage_content: str) -> tuple:
    """Actualiza una página de Confluence con contenido en formato storage nativo."""
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}"

    # Obtener versión actual y título
    resp = requests.get(
        url, headers=get_confluence_headers(),
        verify=SSL_VERIFY, timeout=30
    )
    resp.raise_for_status()
    data            = resp.json()
    current_version = data["version"]["number"]
    title           = data["title"]

    payload = {
        "version": {"number": current_version + 1},
        "title":   title,
        "type":    "page",
        "body": {
            "storage": {
                "value":          storage_content,
                "representation": "storage",
            }
        },
    }
    resp = requests.put(
        url, headers=get_confluence_headers(),
        json=payload, verify=SSL_VERIFY, timeout=30
    )
    resp.raise_for_status()
    return title, current_version + 1


# ──────────────────────────────────────────────────────────────────────────────
#  GENERACIÓN HTML
# ──────────────────────────────────────────────────────────────────────────────

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
header h1::before {
    content: "📋";
    font-size: 1.2rem;
}
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
thead th:first-child { border-radius: 0; }

tbody tr {
    border-bottom: 1px solid var(--border);
    transition: background .12s;
}
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: #f0f4ff; }

td { padding: 10px 14px; vertical-align: middle; }

/* ── Columna ID ── */
td.id-col { white-space: nowrap; }
td.id-col a {
    color: var(--primary);
    text-decoration: none;
    font-weight: 700;
    font-size: .84rem;
}
td.id-col a:hover { text-decoration: underline; color: var(--primary-dark); }

/* ── Columna Título ── */
td.title-col { max-width: 280px; }
td.title-col span {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.45;
}

/* ── Columna Sprint ── */
td.sprint-col {
    white-space: nowrap;
    color: var(--text-light);
    font-size: .80rem;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
}
td.sprint-col.empty { color: #b3bac5; font-style: italic; }

/* ── Columna Labels ── */
td.labels-col {
    font-size: .78rem;
    color: var(--text-light);
    max-width: 220px;
}
td.labels-col.empty { color: #b3bac5; font-style: italic; }

/* ── Columna Assignee ── */
td.assignee-col {
    white-space: nowrap;
    color: var(--text-light);
    font-size: .80rem;
}
td.assignee-col.empty { color: #b3bac5; font-style: italic; }

/* ── Badges de estado ── */
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
.badge-empty  {
    color: #b3bac5;
    font-style: italic;
    font-size: .75rem;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
}

/* ── Fila separadora de grupo de estados ── */
.group-row td {
    background: #eef2ff;
    font-weight: 700;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: var(--primary-dark);
    padding: 7px 14px;
    border-top: 2px solid #c5d4f0;
    border-bottom: 1px solid #c5d4f0;
}

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


def badge_html(status_name: str) -> str:
    if not status_name or status_name in ("—", ""):
        return '<span class="badge-empty">—</span>'
    key = status_name.lower()
    css_class, label = STATUS_BADGE.get(key, ("badge-blue", status_name))
    return f'<span class="badge {css_class}">{label}</span>'


def assignee_html(name: str) -> str:
    if not name or name == "—":
        return '<td class="assignee-col empty">Sin asignar</td>'
    return f'<td class="assignee-col">{name}</td>'


def render_section(title: str, issues: list, subtasks_map: dict, epics_map: dict | None = None) -> str:
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

    # Ordenar por estado
    issues_sorted = sorted(
        issues,
        key=lambda i: status_sort_key(i["fields"]["status"]["name"])
    )

    rows_html     = []
    current_group = None

    for issue in issues_sorted:
        f          = issue["fields"]
        key        = issue["key"]
        status     = f["status"]["name"]
        title_text = f.get("summary", "—").replace("<", "&lt;").replace(">", "&gt;")
        issue_url  = f"{JIRA_BASE_URL}/browse/{key}"
        sprint     = extract_sprint_name(f)
        labels_raw = f.get("labels") or []
        labels_txt = ", ".join(labels_raw) if labels_raw else "—"

        qa        = subtasks_map.get(key, {})
        design    = qa.get("design")    or {}
        execution = qa.get("execution") or {}

        d_status   = design.get("status",   "—")
        d_assignee = design.get("assignee", "—")
        e_status   = execution.get("status",   "—")
        e_assignee = execution.get("assignee", "—")

        epic_key   = f.get(EPIC_LINK_FIELD) or ""
        epic_title = epics_map.get(epic_key, epic_key) if epic_key else ""
        if epic_key:
            idx       = _epic_color_index(epic_key, ordered_epic_keys)
            ebg, efg  = EPIC_PALETTE_HTML[idx]
            epic_html = (
                f'<td style="white-space:nowrap;">'
                f'<a href="{JIRA_BASE_URL}/browse/{epic_key}" target="_blank" '
                f'style="background:{ebg};color:{efg};padding:3px 9px;border-radius:12px;'
                f'font-size:.70rem;font-weight:700;text-decoration:none;white-space:nowrap;">'
                f'{epic_title}</a></td>'
            )
        else:
            epic_html = '<td class="labels-col empty">—</td>'

        sprint_html = (
            f'<td class="sprint-col">{sprint}</td>'
            if sprint and sprint != "—"
            else '<td class="sprint-col empty">—</td>'
        )
        labels_html = (
            f'<td class="labels-col">{labels_txt}</td>'
            if labels_raw
            else '<td class="labels-col empty">—</td>'
        )

        # Fila de separación de grupo
        if status != current_group:
            current_group = status
            rows_html.append(
                f'<tr class="group-row"><td colspan="10">{status}</td></tr>'
            )

        rows_html.append(f"""          <tr>
            <td class="id-col"><a href="{issue_url}" target="_blank">{key}</a></td>
            <td class="title-col"><span title="{title_text}">{title_text}</span></td>
            {sprint_html}
            <td>{badge_html(status)}</td>
            <td>{badge_html(d_status)}</td>
            {assignee_html(d_assignee)}
            <td>{badge_html(e_status)}</td>
            {assignee_html(e_assignee)}
            {labels_html}
            {epic_html}
          </tr>""")

    count      = len(issues)
    table_body = "\n".join(rows_html)

    return f"""
    <div class="section">
      <div class="section-header">
        <h2>{title}</h2>
        <span class="count">{count} User {'Story' if count == 1 else 'Stories'}</span>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>ID Jira</th>
              <th>Título</th>
              <th>Sprint</th>
              <th>Estado US</th>
              <th>Test Design – Estado</th>
              <th>Test Design – Assignee</th>
              <th>Test Execution – Estado</th>
              <th>Test Execution – Assignee</th>
              <th>Labels</th>
              <th>Epic Link</th>
            </tr>
          </thead>
          <tbody>
{table_body}
          </tbody>
        </table>
      </div>
    </div>"""


def generate_html(section_html: str, title: str, timestamp: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} – QA Report</title>
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

  <footer>Generado automáticamente por <strong>SeguimientoGO</strong> · {timestamp}</footer>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None):
    args = parse_args(argv)
    selected_reports = get_selected_reports(args)

    if not JIRA_TOKEN:
        print("[ERROR] Token de Jira no configurado.")
        print("        Define la variable de entorno JIRA_TOKEN o edita JIRA_TOKEN en este script.")
        sys.exit(1)

    # Si SSL_VERIFY es False en entorno corporativo, suprimir advertencias
    if not SSL_VERIFY:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    generated = []

    print(f"[i] Reportes seleccionados: {', '.join(report['key'] for report in selected_reports)}")

    for q in selected_reports:
        out_file = q["output_file"]
        print(f"\n[→] {q['title']}  →  {out_file}")
        print(f"    JQL: {q['jql']}")

        try:
            issues = fetch_user_stories(q["jql"])
        except requests.HTTPError as exc:
            code = exc.response.status_code
            body = exc.response.text[:300]
            print(f"    [ERROR HTTP {code}] {body}")
            section = render_section(q["title"], [], {})
            issues  = []
        except requests.ConnectionError:
            print(f"    [ERROR] No se puede conectar a {JIRA_BASE_URL}. Verifica la red o SSL_VERIFY.")
            section = render_section(q["title"], [], {})
            issues  = []
        except Exception as exc:
            print(f"    [ERROR] {exc}")
            section = render_section(q["title"], [], {})
            issues  = []
        else:
            print(f"    {len(issues)} User Stories encontradas.")
            parent_keys = [i["key"] for i in issues]
            print("    Cargando subtareas QA …")
            try:
                subtasks_map = fetch_qa_subtasks(parent_keys)
                total_with_design    = sum(1 for v in subtasks_map.values() if v.get("design"))
                total_with_execution = sum(1 for v in subtasks_map.values() if v.get("execution"))
                print(f"    Test Design encontrados:    {total_with_design}")
                print(f"    Test Execution encontrados: {total_with_execution}")
            except Exception as exc:
                print(f"    [WARN] No se pudieron cargar subtareas: {exc}")
                subtasks_map = {}

            epic_keys = sorted({
                i["fields"].get(EPIC_LINK_FIELD) or ""
                for i in issues
            } - {""})
            print(f"    Cargando títulos de epics ({len(epic_keys)}) …")
            try:
                epics_map = fetch_epic_info(epic_keys)
            except Exception as exc:
                print(f"    [WARN] No se pudieron cargar épicas: {exc}")
                epics_map = {}

            section = render_section(q["title"], issues, subtasks_map, epics_map)

            # ── Subir a Confluence si la query tiene página configurada ──
            if q.get("confluence_page_id"):
                print(f"    Subiendo a Confluence (página {q['confluence_page_id']}) …")
                try:
                    confl_content = render_confluence_storage(
                        q["title"], issues, subtasks_map, timestamp, epics_map
                    )
                    page_title, new_ver = update_confluence_page(
                        q["confluence_page_id"], confl_content
                    )
                    print(f"    [✓] Confluence: '{page_title}' → v{new_ver}")
                except requests.HTTPError as exc:
                    print(f"    [WARN] Confluence HTTP {exc.response.status_code}: {exc.response.text[:200]}")
                except Exception as exc:
                    print(f"    [WARN] No se pudo actualizar Confluence: {exc}")

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
