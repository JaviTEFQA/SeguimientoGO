---
name: seguimiento-2611
description: Seguimiento de la 26.11.100 publicado en la página de claude.ai. Antes crea las ejecuciones que falten a los TCs de las US con el diseño en Resolved o Closed. La página tiene una pestaña de ejecuciones diarias (hoy por persona frente a ayer a la misma hora, totales de campaña y desglose por plataforma) y otra por plataforma (Android, iOS, PC + BFF, tvOS y Chromecast) con US abiertas, ejecuciones, bugs en Resolved, diseño pendiente y titulares. Úsalo cuando el usuario pida "actualiza datos de la 26.11", "el seguimiento de la 26.11 por plataforma", "súbelo a la nube" o "actualiza la página de la 26.11".
---

# Seguimiento 26.11.100 por plataforma

Página publicada: https://claude.ai/artifact/DiQW4i2ppQ8uWXEJADPLRG. Cada ejecución del skill la actualiza en el mismo enlace.

## Pasos

Trabaja en el scratchpad de la sesión para los ficheros intermedios (`<scratch>` abajo). Desde la raíz del repo, con el venv:

0. **Ejecuciones que faltan.** Antes de sacar los datos, crea las ejecuciones de los TCs de las US cuyo diseño ya está en Resolved o Closed (pedido del usuario el 15/10/2026: «siempre que pasen una tarea de diseño a resolved o closed, si no tienen ejecuciones los TCs, créalas»):
   ```bash
   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/informes_mcp/crear_ejecuciones_faltantes.py --version 26.11.100 --crear
   ```
   - Solo mira US no cerradas con la subtarea `[QA] US Test Design` en Resolved o Closed. Cada TC (enlace Tests en los dos sentidos) necesita una ejecución con el label de la plataforma de la US (`CC_26.11.100_Android`, `_iOS`, `_tvOS`, `_Web`, `_BFF`, desde `jira_tc_labels_by_version.json`); un TC de varias plataformas lleva una por plataforma. Salta los TCs cerrados.
   - No crea la ejecución de Android, iOS o tvOS a los TCs automatizados en esa plataforma (pedido del usuario el 19/10/2026): label `AUTO_ACCEPTANCE_Android` / `_iOS` / `_tvOS` o la plataforma marcada en AutoUSTest Done (`customfield_33700`: «Mobile Android», «Mobile iOS», «tvOS»), salvo que el Test Scope sea End2End. Salen en la línea «Se saltan por TC automatizado».
   - Crea en Pending y sin asignar; Jira no deja poner el componente por la API.
   - Si crea alguna, dilo en la respuesta (cuántas, por label y de qué US) y menciónalo en los titulares de `diario`. Si no hay ninguna, no hace falta decir nada.
   - Si sale un error de Jira distinto de un corte de conexión, para y avisa al usuario en vez de seguir.

1. **Datos.** Saca el corte en markdown:
   ```bash
   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/informes_mcp/seguimiento_versiones.py android ios pcbff11 tvos chromecast > <scratch>/corte_2611.md
   ```
   Y las ejecuciones diarias (lo mismo que «actualiza datos»: hoy por persona frente al día laborable anterior a la misma hora, totales de campaña por persona con su delta y desglose por label):
   ```bash
   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/informes_mcp/seguimiento_diario.py --version 26.11.100 --labels CC_26.11.100_Android CC_26.11.100_iOS CC_26.11.100_tvOS CC_26.11.100_Web CC_26.11.100_BFF --solo-ejecuciones > <scratch>/diario_2611.md
   ```
   Los dos consultan Jira real con el token de `.env` y solo leen. Si falla por handshake TLS o timeout contra jira.tid.es, reintenta tal cual. El dueño de una ejecución sin assignee se hereda de la subtarea `[QA] US Test Execution` de su US.

2. **Titulares.** Lee los dos cortes (sobre todo el bloque «D. Cifras» de cada plataforma y las tablas 1, 2 y 2b del diario) y escribe `<scratch>/titulares_2611.json` con este formato (ejemplo real en `scripts/informes_mcp/datos/titulares_26.11.100_ejemplo.json`):
   ```json
   {"global": ["..."], "plataformas": {"diario": ["..."], "android": ["..."], "ios": [], "pc": [], "tvos": [], "chromecast": []}, "notas": {"pc": "..."}}
   ```
   - Las claves son `diario` (pestaña de ejecuciones diarias), `android`, `ios`, `pc`, `tvos` y `chromecast`. `notas` va debajo de la tabla de bugs de esa plataforma y es opcional.
   - En `diario`: el pulso de hoy frente a ayer a la misma hora, quién ha ejecutado y quién no (con su última ejecución), los Failed/Impeded del día agrupados si caen en el mismo bloque, la cola sin asignar y algún logro real con nombre. Mismo tono que el cuadro de «actualiza datos».
   - Formato «registro A»: cada titular empieza con dos cifras reales que se contradicen, en `<b>…</b>`, seguidas de una frase corta. El remate apunta al sistema o a la cola, nunca a una persona.
   - `global` recoge lo que afecta a varias plataformas (ejecuciones o US a nombre de gente que ya no está, el mismo diseño pendiente en las tres móviles…).
   - Usa solo cifras del corte; no inventes ni arrastres las del ejemplo.

3. **Página.**
   ```bash
   python scripts/informes_mcp/seguimiento_versiones_html.py <scratch>/corte_2611.md <scratch>/seguimiento_26.11.100.html <scratch>/titulares_2611.json --diario <scratch>/diario_2611.md
   ```
   La pestaña «Ejecuciones diarias» sale la primera y abierta por defecto.
   En la tabla «User Stories no cerradas» de cada plataforma las cifras son clicables (pedido del usuario el 19/10/2026): TCs abre los TCs de la US en Jira; P, F, I y Pe abren la última ejecución de cada TC en ese estado; Sin eje. abre los TCs sin ejecución. `seguimiento_versiones.py` las escribe como `[n](búsqueda de Jira)` y el HTML las convierte en enlaces; si muestras las tablas en el chat, quita los enlaces y deja solo la cifra.

4. **Publicar.** Con la herramienta Artifact, lee primero la página (`action: "read"` con la URL de arriba) y publica `<scratch>/seguimiento_26.11.100.html` pasando esa URL como `url`, para conservar el enlace. No pases `icon`.

5. **Respuesta.** Da el enlace y, en pocas líneas, qué ha cambiado desde el corte anterior si lo hubo en la sesión (ejecuciones en Passed, US cerradas, bugs nuevos en Resolved, diseño). Si el usuario pide las tablas en el chat, muéstralas completas por plataforma.

## Notas

- «PC» es PC Client + GoBFF (ámbito `pcbff11`).
- Chromecast no tiene label de campaña (`CC_26.11.100_Chromecast` sin ejecuciones a 15/10/2026): sale con US, bugs y diseño, sin ejecuciones.
- El diseño pendiente no cuenta las subtareas `[QA] US Test Design` en Resolved.
- La tabla de diseño pendiente lleva el GOSPECS del que cuelga la US (enlace Depends) y el estado de su subtarea `[TPM] US Specification` (pedido del usuario el 20/10/2026; si hay copias «CLONE - …» manda la original). Especificación Closed con diseño QA parado es lo que hay que señalar; especificación Impeded explica el diseño Impeded.
- La página es privada salvo que el usuario la comparta desde su menú Share; Claude no puede cambiar eso.

Responde en español, como el resto del repo.
