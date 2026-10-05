# Fluo

Resaltá, subrayá, tachá y dibujá sobre PDFs como si fueran un libro de papel.
Pensado para andar fluido en máquinas modestas (netbooks del gobierno de 2016,
Celeron, poca RAM, disco mecánico): render nativo con MuPDF y UI en Qt.

## Qué hace

- **Marcas sobre texto**: resaltar, subrayar y tachar arrastrando sobre las palabras.
- **Lápiz y marcador libre**: trazos a mano alzada; el marcador es translúcido y
  sirve en páginas escaneadas sin capa de texto.
- **Goma, deshacer y rehacer**, colores y grosor por herramienta.
- **Guardar como copia marcada** (el original queda intacto) o sobre el mismo archivo.
  Las marcas se guardan como anotaciones PDF estándar: las ve Acrobat, Chrome, el celu.
- **Volver a editar**: al abrir un PDF ya marcado, las marcas se cargan y se pueden
  seguir editando o borrando. Recuerda la última página de cada archivo.
- **Bibliotecas**: colecciones de accesos directos a PDFs, con miniaturas. Agregá
  archivos o carpetas enteras, arrastrá desde el Explorador, buscá, mové entre
  bibliotecas. Los PDFs nunca se mueven ni se copian.
- **Autoactualización** desde GitHub Releases (solo en la versión instalada).

## Instalar (Windows 10 o más, 64 bits)

Opción A, un clic: bajá [`Instalar.bat`](https://github.com/nicomine-dev/fluo/releases/latest/download/Instalar.bat) y hacé doble clic.

Opción B, PowerShell:

```powershell
irm https://raw.githubusercontent.com/nicomine-dev/fluo/main/scripts/install.ps1 | iex
```

Opción C, a mano: en [Releases](https://github.com/nicomine-dev/fluo/releases)
está `Fluo-Setup-x.y.z.exe` (instalador) y `Fluo-x.y.z-portable.zip`
(descomprimir y ejecutar, ideal para pendrive).

No pide administrador: instala en `%LOCALAPPDATA%\Programs\Fluo`.
La primera vez Windows SmartScreen avisa porque el ejecutable no está firmado:
«Más información» → «Ejecutar de todas formas».

## Desarrollo

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python run.py            # correr
.venv\Scripts\python -m pytest -q      # tests (usa Qt offscreen)
.venv\Scripts\pyinstaller fluo.spec --noconfirm   # build onedir en dist\Fluo
```

Estructura:

```
fluo/
  app.py             arranque, logging, excepthook
  main_window.py     alterna biblioteca <-> editor, actualizaciones
  updater.py         GitHub Releases: chequeo, descarga, instalador silencioso
  editor/
    model.py         TextMark / InkStroke (coordenadas de página sin rotar)
    document.py      PyMuPDF: texto, carga y escritura de anotaciones, guardado
    render.py        hilo de render (su propia copia del PDF)
    items.py         QGraphicsItems: página, capa rotada, marcas
    view.py          QGraphicsView: scroll continuo, zoom, herramientas, undo
    editor.py        toolbars, colores, guardar / guardar como
  library/
    store.py         bibliotecas y recientes en %LOCALAPPDATA%\Fluo\library.json
    thumbs.py        miniaturas en segundo plano con cache en disco
    view.py          pantalla de bibliotecas
installer/fluo.iss   Inno Setup (por usuario, silencioso para autoupdate)
scripts/install.ps1        instalador en un paso desde GitHub
.github/workflows/         tests en cada push; release al pushear un tag v*
```

## Publicar una versión

1. Subir `__version__` en `fluo/__init__.py`.
2. `git tag v0.2.0 && git push --tags`.
3. GitHub Actions compila, corre los tests, arma instalador y zip, y publica el Release.
   Las instalaciones existentes ofrecen actualizarse al abrir.

## Decisiones de diseño

- **Las marcas se renderizan en Qt, no en MuPDF**: la página se dibuja sin anotaciones
  y las marcas son items encima. Así se editan y borran sin re-renderizar.
- **Coordenadas**: el modelo usa el sistema de página *sin rotar* de PyMuPDF (el mismo
  de `get_text` y de las anotaciones). La capa de marcas aplica `page.rotation_matrix`.
- **Guardar**: las páginas tocadas se reescriben completas desde el modelo. Sobre el mismo
  archivo se guarda incremental (rápido en PDFs grandes); «Guardar como» crea un PDF nuevo
  y el editor pasa a trabajar sobre él.
- **Solo se muestran** anotaciones Highlight, Underline, StrikeOut e Ink. Otros tipos
  (notas, sellos) se conservan en el archivo pero no se dibujan, por ahora.
