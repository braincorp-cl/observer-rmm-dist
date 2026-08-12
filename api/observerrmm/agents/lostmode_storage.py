"""Almacenamiento de la evidencia del modo perdido/robado (feature 030, ADR-025).

Storage propio, deliberadamente separado de `ee.reporting`:

1. `ee.reporting` **no se instala** cuando `DEMO=True`, así que colgarse de
   `get_report_assets_fs` dejaría la feature rota en ese modo.
2. La evidencia forense de ADR-025 tiene su propio régimen de retención y de
   acceso (permiso dedicado para verla, borrado a plazo). Mezclarla con los
   assets de reportes, que son material de plantilla y se sirven por URL
   pública, sería incorrecto aunque funcionara.

Mismo patrón que `ee/reporting/storage.py`: una subclase de `FileSystemStorage`
anclada a una ruta base propia, y una factory que las migraciones y los
`FileField` pueden referenciar por nombre (una instancia embebida en una
migración quedaría congelada con la ruta que tenía el día que se escribió).
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class LostModeEvidenceStorage(FileSystemStorage):
    """Mantiene las operaciones de archivo confinadas a LOST_MODE_EVIDENCE_BASE_PATH.

    A diferencia de `ReportAssetStorage` no expone helpers de navegación
    (`isdir`, `rename`, `move`, ...): la evidencia no se explora ni se reorganiza
    desde la consola, sólo se escribe una vez y se lee por su fila.

    LA RUTA SE LEE EN CADA USO, no se congela en el constructor. En
    `FileSystemStorage`, `location` y `base_location` son `cached_property`: el
    valor queda fijado la primera vez y para cambiarlo hay que vaciar el
    `__dict__` del objeto a mano — que es exactamente lo que tuvo que hacer el
    `conftest.py` de reporting, y por una razón cara: sus tests escribían de
    verdad en `/opt/observer/reporting/assets`, pasaban por accidente en el
    runner de la CI (donde `/opt` es escribible) y fallaban en cualquier equipo
    de desarrollo con un error que no menciona ni permisos ni rutas.

    Con estas dos propiedades, `override_settings(LOST_MODE_EVIDENCE_BASE_PATH=…)`
    basta para aislar la evidencia en un temporal, y montar la evidencia en otro
    volumen desde `local_settings.py` sigue funcionando igual.
    """

    @property
    def base_location(self) -> str:
        return self._value_or_setting(
            self._location, settings.LOST_MODE_EVIDENCE_BASE_PATH
        )

    @property
    def location(self) -> str:
        return os.path.abspath(self.base_location)


def get_lost_mode_evidence_fs() -> LostModeEvidenceStorage:
    """Factory que referencian el `FileField` y las migraciones.

    No recibe la ruta: la resuelve el storage en cada uso (ver arriba). Una
    instancia embebida en una migración quedaría congelada con la ruta que tenía
    el día que se escribió, y por eso lo que se referencia es esta función.
    """
    return LostModeEvidenceStorage()
