"""Almacenamiento de las capturas del monitoreo de actividad (feature 049-C).

Mismo storage que la evidencia del modo perdido (cifra al escribir y descifra al
leer con la llave del ambiente), anclado a su propia ruta: las capturas tienen
otra finalidad y otro plazo (`activity_prune_days`), y mezclarlas con la
evidencia de un caso de robo confundiría las dos retenciones.
"""

from django.conf import settings

from agents.lostmode_storage import LostModeEvidenceStorage


class ActivityScreenshotStorage(LostModeEvidenceStorage):
    @property
    def base_location(self) -> str:
        return self._value_or_setting(
            self._location, settings.ACTIVITY_SCREENSHOTS_BASE_PATH
        )


def get_activity_screenshots_fs():
    return ActivityScreenshotStorage()
