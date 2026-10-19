# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Idioma

El código, los comentarios, la salida por consola y la documentación están en español. Mantén ese idioma al añadir código o documentación.

## Qué hay

El repo solo contiene lo que usan las tres skills de `.claude/skills/` (limpieza del 19/10/2026; lo retirado está en `C:\Users\JMARTIN\Documents\SeguimientoGO_retirado_20261019` y en `SeguimientoGO_backup_20261019.zip`):

- `seguimiento-2611` → `scripts/informes_mcp/crear_ejecuciones_faltantes.py`, `seguimiento_versiones.py`, `seguimiento_diario.py`, `seguimiento_versiones_html.py`.
- `us-acceptance-tests` → `scripts/informes_mcp/us_acceptance_tests.py`.
- `regresion-2610` → `scripts/informes_mcp/regresion_pc/` (se lanza desde esa carpeta).

Cada `SKILL.md` describe los pasos; síguelos en vez de improvisar.

## Comandos

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Lanza los scripts desde la raíz con `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe ...` (la consola de Windows es cp1252 y la salida lleva caracteres que no caben).

No hay tests ni linter. Los scripts consultan Jira real (y algunos escriben: `crear_ejecuciones_faltantes.py --crear`, `regresion_pc/crear_rfa.py --crear`); para validar un cambio usa `python -m py_compile <ficheros>` en vez de lanzarlos. Si falla por handshake TLS o timeout contra jira.tid.es, es un corte habitual: reintenta.

## Credenciales

`JIRA_TOKEN` se lee de `.env` (gitignored) con un parser inline al principio de `jira_tc_report.py`. Las variables de entorno ya definidas tienen prioridad. Nunca escribas tokens en el código.

## Arquitectura

- `jira_tc_report.py` es a la vez un informe suelto (TCs por US, `--reports`/`--version`) y el módulo de conexión que importan todos los scripts: `jira_search`, `JIRA_BASE_URL`, `SSL_VERIFY`, `get_headers`. No lo borres.
- `scripts/informes_mcp/refrescar_datos.py` tiene los helpers comunes: `test_cases` (enlace Tests en los dos sentidos), `subtareas_qa`, `trozos`, `nombre`.
- `scripts/informes_mcp/seguimiento_diario.py` aporta `buscar` (búsqueda paginada con reintentos), `tabla`, `corto` y `TIPOS_BUG`.
- Los scripts añaden la raíz y su carpeta a `sys.path` para importarse entre sí.

### Versiones y labels

`jira_tc_labels_by_version.json` guarda `{versión: {android|ios|tvos|pc|gobff: label}}`, con la convención `CC_<versión>_<Android|iOS|tvOS|Web|BFF>` (`pc` → `Web`, `gobff` → `BFF`). Para un ciclo nuevo, añade su clave.

### Ejecuciones automatizadas

`crear_ejecuciones_faltantes.py` no crea ejecución de Android/iOS/tvOS a los TCs automatizados en esa plataforma (label `AUTO_ACCEPTANCE_<plataforma>` o la plataforma en AutoUSTest Done) salvo que sean End2End.

## Campos personalizados de Jira (instancia `jira.tid.es`)

| Campo | Id | Uso |
|---|---|---|
| Sprint | `customfield_11000` | String legado; se parsea con regex `name=...` |
| Epic Link | `customfield_11600` | Agrupar por épica |
| Test Scope | `customfield_10163` | Multi-select (System, End2End…) |
| AutoUSTest Done | `customfield_33700` | Multicheckbox: CORE, Mobile Android, Mobile iOS, PC Client, tvOS |
| Automation Done | `customfield_30800` | Multicheckbox (Mobile_Android, Mobile_iOS, PC Client…) |
