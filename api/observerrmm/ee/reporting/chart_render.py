"""Renderizado de gráficos Kaleido/chromium AISLADO en un subproceso Python limpio.

Kaleido 1.x renderiza a imagen (SVG/PNG) lanzando un chromium como subproceso y
hablándole por asyncio (choreographer). Cuando eso corre **dentro de un worker
uWSGI** (`app.ini`: `master=true` + `enable-threads=true`), la gestión de señales
del worker (SIGCHLD) interfiere con el watcher de subprocesos de asyncio y el
chromium "se cierra apenas arranca" (`"The browser seemed to close immediately
after starting"`) → el render falla (400/500 en Preview/GenerateReport de la UI).
Standalone (`manage.py shell`) y bajo Celery —procesos sin ese contexto— funciona;
**solo rompe en la request servida por uWSGI**.

Fix: ejecutar `fig.to_image` en un **subproceso Python del venv** (intérprete
limpio, señales por defecto). Se le pasa la figura por stdin (JSON) y devuelve el
SVG por stdout. El chromium queda como NIETO del worker uWSGI (hijo del subproceso
limpio, que lo reapea bien); uWSGI nunca es su padre. El stdout se lee por completo
antes de esperar al proceso, así que el resultado se obtiene aunque el worker
reapee el subproceso.

Se usa subprocess directo (no multiprocessing): bajo uWSGI `sys.executable` es el
binario `uwsgi` y `multiprocessing` (spawn) además re-importa `__main__` (la app
uWSGI), dos formas de romper el hijo. Acá el ejecutable es explícito.
"""

import os
import subprocess
import sys

# Script del subproceso: lee la figura (JSON) de stdin y escribe el SVG en stdout.
_CHILD = (
    "import sys;"
    "import plotly.io as pio;"
    "fig=pio.from_json(sys.stdin.buffer.read().decode('utf-8'));"
    "sys.stdout.buffer.write(fig.to_image(format='svg'));"
    "sys.stdout.buffer.flush()"
)


def _venv_python() -> str:
    """Ruta al intérprete Python del venv (NO `sys.executable`, que bajo uWSGI
    es el binario `uwsgi`)."""
    for name in ("python", "python3"):
        cand = os.path.join(sys.prefix, "bin", name)
        if os.path.exists(cand):
            return cand
    base = getattr(sys, "_base_executable", "") or sys.executable
    return base if os.path.basename(base).startswith("python") else "python3"


def render_svg(fig, *, timeout: int = 180) -> str:
    """Convierte una figura plotly a SVG en un subproceso Python aislado.

    Levanta RuntimeError con el detalle si el subproceso falla o excede `timeout`.
    """
    import plotly.io as pio

    fig_json = pio.to_json(fig)
    try:
        proc = subprocess.run(
            [_venv_python(), "-c", _CHILD],
            input=fig_json.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=dict(
                os.environ
            ),  # HOME heredado → chromium autodescubierto por Kaleido
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"timeout ({timeout}s) renderizando el gráfico (Kaleido/chromium)"
        )

    if proc.returncode != 0 or not proc.stdout:
        detail = (
            proc.stderr.decode("utf-8", "replace").strip()[-500:] if proc.stderr else ""
        )
        raise RuntimeError(
            f"fallo al renderizar el gráfico (Kaleido/chromium): {detail}"
        )
    return proc.stdout.decode("utf-8")
