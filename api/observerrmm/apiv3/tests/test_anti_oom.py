"""F009 (GAP-030 / RN-02 / RN-030): `get_agent_config()` y el anti-OOM real.

⚠️ **Este módulo se reescribió el 2026-08-03 porque su premisa era falsa.** La
versión anterior exigía un "piso de producción" por cada `CHECKIN_*`, y esos
números no salían de `settings.py`: eran los **fallbacks** del `getattr` de
`apiv3/utils.py`, o sea los valores **inflados** que GAP-052 corrigió a propósito
el 2026-06-27 porque dejaban a un agente recién enrolado sin inventario por horas
o días (disks ~2.8 días, wmi hasta 70 h). El test exigía volver justamente a eso,
así que llevaba rojo desde la recalibración — invisible porque el CI que lo
corría no se ejecutaba.

Lo que `settings.py` declara textual sobre el bloque `CHECKIN_*` es el invariante
que sí hay que proteger:

    El ÚNICO con riesgo real de OOM en MeshCentral es CHECKIN_SYNCMESH
    → se mantiene >= 3600 (lección MINSAL).

Así que acá se verifican cosas que sí son verdad: el piso de `syncmesh` desde
settings y desde el fallback, que ningún intervalo sea absurdo, y que perder una
línea de `settings.py` deje el intervalo más conservador y **nunca más
frecuente** — que es la protección que el test viejo quería dar y expresaba con
números equivocados.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings as django_settings
from django.test import SimpleTestCase

from apiv3 import utils as apiv3_utils

# El piso anti-OOM real, y el único: MeshCentral es lo que se cae.
SYNCMESH_FLOOR = 3600

# Los ocho intervalos que el endpoint /config entrega al agente.
CHECKIN_FIELDS = (
    "checkin_hello",
    "checkin_agentinfo",
    "checkin_winsvc",
    "checkin_pubip",
    "checkin_disks",
    "checkin_sw",
    "checkin_wmi",
    "checkin_syncmesh",
)


class TestAgentConfigAntiOOM(SimpleTestCase):
    def test_syncmesh_respects_the_only_real_floor(self):
        cfg = apiv3_utils.get_agent_config()
        self.assertGreaterEqual(
            cfg.checkin_syncmesh,
            SYNCMESH_FLOOR,
            msg="CHECKIN_SYNCMESH bajo el piso anti-OOM de MeshCentral",
        )

    def test_syncmesh_floor_holds_when_settings_missing(self):
        # Si desaparece la línea `CHECKIN_SYNCMESH` de settings, el fallback del
        # `getattr` tiene que seguir respetando el piso: es el que evita el OOM.
        empty = SimpleNamespace()
        with patch.object(apiv3_utils, "settings", empty):
            cfg = apiv3_utils.get_agent_config()
        self.assertGreaterEqual(
            cfg.checkin_syncmesh,
            SYNCMESH_FLOOR,
            msg="el fallback de CHECKIN_SYNCMESH baja del piso anti-OOM",
        )

    def test_every_interval_is_positive(self):
        cfg = apiv3_utils.get_agent_config()
        for field in CHECKIN_FIELDS:
            with self.subTest(field=field):
                self.assertGreater(getattr(cfg, field), 0, msg=f"{field} <= 0")

    def test_fallbacks_mirror_the_configured_range(self):
        # Endurecido el 2026-08-15 (feature 037). Antes esto sólo exigía que el
        # fallback no fuera MÁS agresivo que settings, y esa asimetría dejó pasar
        # el drift real: GAP-052 recalibró `settings.py` y los fallbacks quedaron
        # décadas más lentos (disks 69 h contra 33 min) sin que nada se pusiera
        # rojo. El invariante correcto es de IGUALDAD: perder una línea de
        # `settings.py` tiene que dejar el mismo intervalo que se despacha.
        #
        # Como el valor sale de un `random.randint`, se comprueba por contención
        # sobre muchos sorteos: cada uno tiene que caer dentro del rango
        # configurado, en los dos sentidos.
        empty = SimpleNamespace()
        with patch.object(apiv3_utils, "settings", empty):
            draws = [apiv3_utils.get_agent_config() for _ in range(200)]

        for field in CHECKIN_FIELDS:
            setting_name = field.replace("checkin_", "CHECKIN_").upper()
            configured = getattr(django_settings, setting_name, None)
            if configured is None:
                continue  # sin línea en settings no hay nada que comparar
            observed = [getattr(cfg, field) for cfg in draws]
            with self.subTest(field=field):
                self.assertGreaterEqual(
                    min(observed),
                    min(configured),
                    msg=(
                        f"el fallback de {setting_name} es MÁS agresivo que el "
                        f"valor configurado {configured}"
                    ),
                )
                self.assertLessEqual(
                    max(observed),
                    max(configured),
                    msg=(
                        f"el fallback de {setting_name} es MÁS LENTO que el valor "
                        f"configurado {configured}: quedó rezagado como en GAP-052"
                    ),
                )
