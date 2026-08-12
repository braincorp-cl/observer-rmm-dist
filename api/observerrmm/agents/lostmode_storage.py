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

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class LostModeEvidenceStorage(FileSystemStorage):
    """Mantiene las operaciones de archivo confinadas a LOST_MODE_EVIDENCE_BASE_PATH.

    A diferencia de `ReportAssetStorage` no expone helpers de navegación
    (`isdir`, `rename`, `move`, ...): la evidencia no se explora ni se reorganiza
    desde la consola, sólo se escribe una vez y se lee por su fila.
    """


def get_lost_mode_evidence_fs() -> LostModeEvidenceStorage:
    return LostModeEvidenceStorage(
        location=settings.LOST_MODE_EVIDENCE_BASE_PATH,
    )
