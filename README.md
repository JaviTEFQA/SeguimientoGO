# SeguimientoGO

## Descripción

Conjunto de scripts Python para generar informes HTML de seguimiento QA a partir de Jira.
Las credenciales se leen exclusivamente del fichero `.env` (nunca hardcodeadas en el código).

Hay dos scripts independientes:

| Script | Qué genera | Sube a Confluence |
|---|---|---|
| `seguimiento_go.py` | Estado de subtareas QA (Test Design / Test Execution) por US | ✅ Sí |
| `jira_tc_report.py` | Test Cases vinculados a cada US con estado de última ejecución | ❌ No |

---

## Configuración

Crea un fichero `.env` en la raíz del proyecto:

```env
JIRA_TOKEN=tu_token_personal_de_jira
CONFLUENCE_TOKEN=tu_token_personal_de_confluence  # solo necesario para seguimiento_go.py
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

---

## seguimiento_go.py — Reporte QA de subtareas

Genera un HTML por plataforma con el estado de las subtareas **Test Design** y **Test Execution**
de cada User Story, y lo sube automáticamente a la página de Confluence correspondiente.

```bash
# Todos los reportes
python seguimiento_go.py

# Solo un subconjunto
python seguimiento_go.py --reports android ios
```

**Reportes disponibles:** `android`, `ios`, `tvos`, `pc`, `gobff`

**Salida:** `jira_report_android.html`, `jira_report_ios.html`, etc.

---

## jira_tc_report.py — Reporte de Test Cases por US

Genera un HTML por plataforma mostrando todos los **Test Cases** vinculados a cada User Story
(link "is tested by"), con su **Test Scope** y el **estado de la última ejecución** de la
campaña de ciclo correspondiente.

- Las US sin ningún TC con scope **End2End** se marcan con un aviso ⚠ Sin E2E.
- Al final de cada reporte se incluye un **cuadro resumen** con totales y porcentajes
  (Passed / Failed / Impeded / Pending) y una barra de distribución.
- **No sube nada a Confluence.**

```bash
# Todos los reportes (usa la versión por defecto: 26.06.100)
python jira_tc_report.py

# Todos los reportes para una versión concreta
python jira_tc_report.py --version 26.06.100

# Solo un subconjunto
python jira_tc_report.py --reports android ios

# Subconjunto + versión
python jira_tc_report.py --reports android ios --version 26.06.100
```

**Reportes disponibles:** `android`, `ios`, `tvos`, `pc`, `gobff`

**Salida:** `jira_tc_report_android_26.06.100.html`, `jira_tc_report_ios_26.06.100.html`, etc.

### Labels de ejecución por plataforma

Las labels se resuelven por versión desde el fichero `jira_tc_labels_by_version.json`.
Para lanzar el reporte con otra campaña, usa el parámetro `--version`.

| Plataforma | Label de campaña |
|---|---|
| Android | `CC_26.06.100_Android` |
| iOS | `CC_26.06.100_iOS` |
| tvOS | `CC_26.06.100_tvOS` |
| PC Client | `CC_26.06.100_Web` |
| GoBFF | `CC_26.06.100_BFF` |

Para añadir una nueva versión, agrega una nueva clave de versión en
`jira_tc_labels_by_version.json` con las labels por plataforma.

---

## Compilar a ejecutable

```bash
pip install pyinstaller
pyinstaller SeguimientoGO.spec          # carpeta
pyinstaller SeguimientoGO_OneFile.spec  # .exe único
```

## Crear instalador Windows

Requiere [Inno Setup](https://jrsoftware.org/isinfo.php).

```powershell
.\installer\build_installer.ps1
```

---

## Estructura

```
SeguimientoGO/
├── seguimiento_go.py           # Reporte QA subtareas → Confluence
├── jira_report.py              # Lógica principal de seguimiento_go.py
├── jira_tc_report.py           # Reporte Test Cases por US (sin Confluence)
├── .env                        # Credenciales (NO subir a git)
├── requirements.txt
├── SeguimientoGO.spec
├── SeguimientoGO_OneFile.spec
├── installer/
│   ├── SeguimientoGO.iss
│   └── build_installer.ps1
└── installer_output/
```
