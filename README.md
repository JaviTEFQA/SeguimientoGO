# SeguimientoGO

## Descripción

(Pendiente de definir)

## Uso

```bash
pip install -r requirements.txt
python seguimiento_go.py
```

Por defecto se generan siempre los 5 reportes definidos:

```bash
python seguimiento_go.py
```

Para generar solo un subconjunto concreto:

```bash
python seguimiento_go.py --reports android ios
```

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

## Estructura

```
SeguimientoGO/
├── seguimiento_go.py
├── requirements.txt
├── SeguimientoGO.spec
├── SeguimientoGO_OneFile.spec
├── installer/
│   ├── SeguimientoGO.iss
│   └── build_installer.ps1
└── installer_output/
```
