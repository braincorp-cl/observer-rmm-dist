"""Aislamiento del almacenamiento de assets para los tests de reporting.

`report_assets_fs` es un singleton de módulo construido en el import con
`location=settings.REPORTING_ASSETS_BASE_PATH`, cuyo default es
**`/opt/observer/reporting/assets`** — una ruta de servidor. Varios tests
escriben ahí **de verdad**: `baker.make("reporting.ReportAsset",
_create_files=True)` crea el archivo, y `UploadAssets` hace `asset.save()`.

Eso hacía que 8 tests dependieran del entorno en vez del código:

- en el runner de GitHub `/opt` es escribible, así que **pasaban por accidente**
  y dejaban basura fuera del sandbox de pytest;
- en una máquina de desarrollo normal `/opt` no lo es, así que fallaban con
  `PermissionError` desde `os.makedirs`, o con un `TypeError` río abajo cuando la
  vista devolvía `notify_error(...)` —un string— y el test lo indexaba como dict.

Ese segundo síntoma es el peor: el mensaje no menciona permisos ni rutas en
ninguna parte, así que la causa queda a tres saltos de distancia del error.

El fixture apunta el singleton a un `tmp_path` por test —aislado y descartable—
y restaura el estado original al terminar. `location` y `base_location` son
`cached_property` de `FileSystemStorage`, así que hay que vaciarlas del `__dict__`
para que se recalculen; con sólo cambiar `_location` no pasaría nada.

No afecta a los tests que parchean el storage completo
(`@patch("ee.reporting.views.report_assets_fs")`) ni a los que pasan rutas
literales sin tocar el disco: ahí el objeto real ni se usa.
"""

import pytest

from ee.reporting.storage import report_assets_fs

# Las `cached_property` de FileSystemStorage que derivan de `_location`.
_CACHED = ("base_location", "location")


@pytest.fixture(autouse=True)
def report_assets_in_tmp(tmp_path):
    """Redirige `report_assets_fs` a un directorio temporal por test."""
    original_location = report_assets_fs._location
    original_cached = {
        key: report_assets_fs.__dict__[key]
        for key in _CACHED
        if key in report_assets_fs.__dict__
    }

    assets_dir = tmp_path / "reporting-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    report_assets_fs._location = str(assets_dir)
    for key in _CACHED:
        report_assets_fs.__dict__.pop(key, None)

    try:
        yield assets_dir
    finally:
        report_assets_fs._location = original_location
        for key in _CACHED:
            report_assets_fs.__dict__.pop(key, None)
        report_assets_fs.__dict__.update(original_cached)
