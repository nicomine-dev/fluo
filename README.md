# Fluo

Resaltá, subrayá, tachá y dibujá sobre PDFs como si fueran un libro de papel.
Pensado para andar fluido en máquinas modestas (netbooks del gobierno, Celeron,
poca RAM, disco mecánico): render nativo con MuPDF y UI en Qt. Corre en
**Windows 7 SP1, 8, 8.1, 10 y 11**, de 32 o 64 bits, con un solo instalador.

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
- **Un solo instalador** para Windows 7 SP1, 8, 8.1, 10 y 11, de 32 o 64 bits.

## Instalar (Windows 7 SP1 en adelante, 32 o 64 bits)

Página de descarga para compartir: **https://fluo-pdf.vercel.app** (botón de descarga,
paso a paso y notas para Windows 7). Los links `/descargar`, `/portable` e `/instalar`
redirigen siempre a la última versión.

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

**En Windows 7** usá la opción C: el PowerShell que trae Windows 7 es viejo y no sabe
bajar de GitHub. Hace falta Windows 7 **SP1 con las actualizaciones de Windows Update**
(en particular KB2533623 y KB2999226, que son de 2011 y 2015).

## Desarrollo

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python run.py            # correr
.venv\Scripts\python -m pytest -q      # tests (usa Qt offscreen)
.venv\Scripts\python -m PyInstaller fluo.spec --noconfirm   # build onedir en dist\Fluo (PySide6)
.py38	ools\python -m PyInstaller fluo.spec --noconfirm       # build legacy 32 bits (PySide2), ver abajo
```

Para el build legacy hace falta un Python 3.8 de 32 bits. Sin instalar nada en el
sistema: bajá el paquete NuGet `pythonx86` 3.8.10, descomprimilo en `.py38/` y
corré `.py38	ools\python -m pip install -r requirements.txt -r requirements-dev.txt`.

Estructura:

```
fluo/
  qt.py              capa de compatibilidad PySide6 / PySide2
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

## Sitio de descarga (Vercel)

La carpeta `site/` es la página https://fluo-pdf.vercel.app: HTML estático más una función
(`site/api/go.js`) que redirige `/descargar` y `/portable` al archivo del último release.
Se despliega a mano desde esa carpeta, con el CLI logueado en la cuenta personal:

```powershell
cd site
vercel --prod
```

Si algún día querés que se despliegue solo al pushear, conectá el repo desde el panel de
Vercel (proyecto `fluo`, Settings, Git) y poné `site` como Root Directory.

## Publicar una versión

1. Subir `__version__` en `fluo/__init__.py`.
2. `git tag v0.2.0 && git push --tags`.
3. GitHub Actions compila, corre los tests, arma instalador y zip, y publica el Release.
   Las instalaciones existentes ofrecen actualizarse al abrir.

## Compatibilidad: dos Qt, un código

Todo el código importa Qt desde `fluo/qt.py`, que elige el binding disponible:

| | Desarrollo | Build publicado |
|---|---|---|
| Python | 3.9 o más (acá 3.13) | 3.8 de 32 bits |
| Qt | PySide6 (Qt 6) | PySide2 5.15 (Qt 5) |
| Windows | 10 u 11, 64 bits | 7 SP1, 8, 8.1, 10, 11; 32 y 64 bits |

Qt 6 y Python 3.9+ no corren en Windows 7 ni 8, por eso el instalador se compila con
Python 3.8 + Qt 5 en 32 bits: un solo paquete que anda en todas las máquinas. Los
tests corren en los dos entornos (`tests.yml`). PyInstaller documenta soporte oficial
desde Windows 8; en Windows 7 funciona con Python 3.8 si el sistema está actualizado,
pero no tenemos una máquina con Windows 7 para probarlo de punta a punta.

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
