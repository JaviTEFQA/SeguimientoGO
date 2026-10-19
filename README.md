# SeguimientoGO

Informes de seguimiento QA a partir de Jira (`jira.tid.es`), pensados para lanzarse como skills de Claude Code.
Las credenciales se leen de `.env` (nunca del código).

## Skills

| Skill | Qué hace | Scripts |
|---|---|---|
| `seguimiento-2611` | Seguimiento de la 26.11.100 por plataforma y ejecuciones diarias, publicado en claude.ai. Antes crea las ejecuciones que faltan. | `scripts/informes_mcp/crear_ejecuciones_faltantes.py`, `seguimiento_versiones.py`, `seguimiento_diario.py`, `seguimiento_versiones_html.py` |
| `us-acceptance-tests` | Estado de las US de una versión y de su subtarea `[DEV] Acceptance tests` (u otra con `--subtarea`). | `scripts/informes_mcp/us_acceptance_tests.py` |
| `regresion-2610` | Regresión de PC Client de la 26.10.100 y sus ejecuciones RFA. | `scripts/informes_mcp/regresion_pc/` |

Las instrucciones de cada una están en `.claude/skills/<skill>/SKILL.md`.

## Configuración

`.env` en la raíz:

```env
JIRA_TOKEN=tu_token_personal_de_jira
```

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Estructura

```
SeguimientoGO/
├── .claude/skills/                  # Las tres skills
├── jira_tc_report.py                # Conexión a Jira (token, jira_search, cabeceras); también genera el informe de TCs por US
├── jira_tc_labels_by_version.json   # Labels de campaña por versión y plataforma
├── requirements.txt
└── scripts/informes_mcp/
    ├── refrescar_datos.py           # Helpers comunes (TCs de una US, subtareas QA, troceo de claves)
    ├── seguimiento_diario.py        # Ejecuciones diarias por persona y plataforma
    ├── seguimiento_versiones.py     # US abiertas, bugs en Resolved y diseño pendiente por plataforma
    ├── seguimiento_versiones_html.py
    ├── crear_ejecuciones_faltantes.py
    ├── us_acceptance_tests.py
    ├── datos/titulares_26.11.100_ejemplo.json
    └── regresion_pc/
```

## Informe de Test Cases por US

`jira_tc_report.py` también se puede lanzar suelto: genera un HTML por plataforma con los TCs de cada US y su última ejecución.

```bash
python jira_tc_report.py --reports pc --version 26.11.100
```

Reportes: `android`, `ios`, `tvos`, `pc`, `gobff`. Las labels salen de `jira_tc_labels_by_version.json`.
