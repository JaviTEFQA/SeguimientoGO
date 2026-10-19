---
name: us-acceptance-tests
description: Estado de las User Stories de la 26.11.100 (o de otra versión) y de su subtarea [DEV] Acceptance tests. Úsalo cuando el usuario pida ver las US de una versión con sus acceptance tests de desarrollo, "el estado de los acceptance tests", "las [DEV] Acceptance tests" o qué US no tienen esa subtarea.
---

# US y [DEV] Acceptance tests

Saca, para cada User Story de la versión (GO + GOMOBILE, todas las plataformas), su estado y el estado y assignee de su subtarea `[DEV] Acceptance tests`.

## Cómo ejecutarlo

Desde la raíz del repo, con el venv:

```bash
.venv/Scripts/python.exe scripts/informes_mcp/us_acceptance_tests.py
```

- Por defecto usa la versión **26.11.100**. Si el usuario pide otra: `--version <versión>`.
- Sirve para cualquier subtarea de la US con `--subtarea "<summary>"`, p. ej. `--subtarea "[QA] US Test Design"` para el diseño QA. La página de diseño QA de la 27.02.100 está en https://claude.ai/artifact/6yAAqZ3HHP3qNhxqNggudc.
- Consulta Jira real con el token de `.env` y solo lee; no escribe ficheros ni toca Jira.
- Si falla con un error de handshake TLS o timeout contra jira.tid.es, reintenta tal cual: es un corte habitual de la red.
- En Windows, lanza con `PYTHONIOENCODING=utf-8` si la salida sale con caracteres rotos.

## Cómo presentarlo

El script imprime un resumen y la tabla en markdown, ordenada con lo que bloquea primero (subtarea Impeded, Open, In Progress…), después lo cerrado y al final las US sin subtarea.

1. Muestra el resumen (US totales, con y sin subtarea, reparto de estados) y la tabla completa, sin recortar filas.
2. Debajo, destaca en pocas viñetas:
   - Las subtareas en **Impeded** u **Open** cuya US ya está Resolved o Closed: el desarrollo está entregado y faltan sus acceptance tests.
   - Las US **sin la subtarea** agrupadas por plataforma. No todas las US la llevan (ahora mismo solo unas 47 de 87), así que preséntalo como dato, no como error.
   - Las subtareas sin asignar.
3. Si el usuario pide filtrar (solo una plataforma, solo las que no están cerradas…), filtra la tabla al presentarla; no hace falta tocar el script.

## Página en claude.ai

Si el usuario pide verlo en Claude o en el navegador, genera la página con `--html <ruta en el scratchpad>.html` y publícala con la herramienta Artifact. La página ya está publicada en https://claude.ai/artifact/EMeppsPUYkH8aGW9jvJ7Us: para actualizarla, regenera el HTML y publícalo pasando esa URL como `url` (léela antes con `action: "read"`), así se conserva el enlace y quien lo tenga compartido ve la versión nueva.

Responde en español, como el resto del repo.
