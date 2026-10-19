---
name: regresion-2610
description: Regresión de PC Client de la 26.10.100 publicada en claude.ai. Son las US de PC (sin GoBFF) con los TCs End2End más importantes por US y por histórico de bugs, más las impedidas críticas, cada uno con su última ejecución CC_26.10.100_Web, su ejecución RFA_26.10.100_Web y la persona asignada. Úsalo cuando el usuario pida "la regresión de la 26.10.100", "regresión de PC", "actualiza la regresión", "crea las ejecuciones RFA" o quiera añadir o quitar TCs de la regresión.
---

# Regresión 26.10.100 · PC

Página publicada: https://claude.ai/artifact/WKGmbV5AfWC4ZJLfCZE9Hq. Cada ejecución del skill la actualiza en el mismo enlace.

Todo vive en `scripts/informes_mcp/regresion_pc/`. Lanza los comandos desde esa carpeta con el venv del repo (`../../../.venv/Scripts/python.exe`) y `PYTHONIOENCODING=utf-8`.

## Criterio de selección (16/10/2026)

- Solo US de la 26.10.100 con componente **PC Client**.
- De los TCs End2End de cada US entran el camino principal (play, compra, grabar…) y los que **detectaron bugs Blocker, Critical o Major** en cualquier ejecución o **no acabaron en Passed**. Fuera quedan las variantes repetidas de layout, iconos, metadata o widgets.
- Además entran las impedidas que afectan a reproducción y DRM (cToken caducado, device binding de Nagra), a publicidad (VMAP) o a una US reabierta.
- Los TCs cerrados no entran.
- Objetivo: la mitad de lo que daría "todos los E2E + impedidas". Con el corte del 16/10 son 99 (89 E2E de 185 y 10 impedidas).

La selección está escrita a mano en `seleccion_regresion.py` (`E2E` y `IMP`, TC → motivo que sale en la página). Para añadir o quitar TCs se edita ahí.

## Pasos

1. **Datos** (solo leen de Jira):
   ```bash
   python datos_regresion.py regresion_pc.json
   python historico_bugs.py regresion_pc.json historico_bugs.json
   ```
   Si al regenerarlos aparecen TCs E2E nuevos con bugs Blocker/Critical/Major o Failed/Impeded, propón al usuario añadirlos a `seleccion_regresion.py` antes de seguir.

2. **Ejecuciones RFA** (escribe en Jira): crea una Test Case Execution con label `RFA_26.10.100_Web` por cada TC elegido que aún no la tenga, en Pending, y la asigna a quien ejecutó el TC por última vez en `CC_26.10.100_Web`. Quién la ejecutó se saca del autor del último cambio de estado a Passed/Failed/Impeded de esa ejecución. Si no hay, se usa el assignee de la ejecución y, si tampoco, el QA de la subtarea `[QA] US Test Execution` de la US.
   ```bash
   python crear_rfa.py            # simula: TCs, reparto por persona y quién sale por qué vía
   python crear_rfa.py --crear    # crea y asigna; guarda rfa.json
   ```
   - Simula siempre antes y enseña al usuario el reparto. Crea solo si el usuario lo ha pedido en esta conversación.
   - Jira no deja poner el assignee al crear, así que el script crea y luego asigna con `PUT /issue/{key}/assignee`.
   - No duplica: salta los TCs que ya tienen ejecución con ese label.
   - Ya existían 261 ejecuciones `RFA_26.10.100_Web` creadas el 15/10 sobre otros TCs. Al contar por label salen 360, pero las de la regresión son las de `rfa.json` (MULTISTC-72140 … 72238 en el primer lote).
   - Si sale un error de Jira distinto de un corte de conexión, para y avisa.

3. **Smoke** (solo lee de Jira): el resto de ejecuciones `RFA_26.10.100_Web` (las que no están en `rfa.json`) son de TCs SMOKE de PC (`[SMOKE][Suite - N]`, componente `Excel_Smoke`). El 15/10/2026 había 261, todas en Pending y sin asignar. Salen en la pestaña Smoke, agrupadas por suite.
   ```bash
   python datos_smoke.py smoke.json
   ```

4. **Página.**
   ```bash
   python regresion_pc_html.py regresion_pc.json <scratch>/regresion_pc_26.10.100.html historico_bugs.json rfa.json smoke.json
   ```
   Tiene dos pestañas: «Regresión por US» (la primera) y «Smoke» (también se abre con `#smoke`).
   Si cambian las prioridades, edita a mano la sección "Por dónde empezar" en `regresion_pc_html.py`.

5. **Publicar.** Con la herramienta Artifact, lee primero la página (`action: "read"` con la URL de arriba) y publica el HTML pasando esa URL como `url`. No pases `icon`.

6. **Respuesta.** Da el enlace y resume cuántas pruebas hay, cuántas ejecuciones RFA se han creado, el reparto por persona y cómo va el smoke (Passed, Pending, sin asignar). Si cambió la selección, di qué TCs entran o salen y por qué.

Responde en español, como el resto del repo.
