"""Feature 030 · Fase 3 · T019 — retención de la evidencia (ADR-025 punto 4).

La deuda que cierra este test es concreta: en el terreno del 2026-08-12 hubo que
borrar 108 filas de evidencia A MANO al terminar la prueba, porque el borrado a
plazo no existía. En un caso real de cliente no hay quien lo haga.

Cada caso mira **el disco**, no la fila. Borrar la fila y dejar el PNG en
`/opt/observer/lostmode/evidence` da una consola que declara la retención
cumplida y un servidor que la incumple — la forma que tomaría acá el "ok falso",
y la única que nadie notaría hasta una auditoría.
"""

import datetime as dt
import os
import tempfile
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone as djangotime
from model_bakery import baker

from agents.models import LostModeEvidence, LostModeState
from agents.tasks import prune_lost_mode_evidence
from core.tasks import core_maintenance_tasks
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestRetencionEvidencia(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.agent")
        self.tmp = tempfile.mkdtemp(prefix="lostmode-retencion-")

    # --------------------------------------------------------- utilidades

    def captura(self, cycle=1, dias_atras=0, agent=None):
        """Una pieza con archivo, envejecida `dias_atras` días."""
        pieza = LostModeEvidence(
            agent=agent or self.agent, cycle=cycle, kind=LostModeEvidenceKind.SCREEN
        )
        pieza.asset.save(f"pantalla-{cycle:06d}.png", ContentFile(PNG_1x1), save=False)
        pieza.save()
        if dias_atras:
            self.envejecer(pieza, dias_atras)
        return pieza

    def envejecer(self, pieza, dias):
        """`created` es auto_now_add: sólo se puede mover con un UPDATE."""
        cuando = djangotime.now() - dt.timedelta(days=dias)
        LostModeEvidence.objects.filter(pk=pieza.pk).update(created=cuando)
        if not pieza.asset:
            return
        ruta = self.ruta(pieza)
        if os.path.exists(ruta):
            marca = cuando.timestamp()
            os.utime(ruta, (marca, marca))

    def ruta(self, pieza):
        return os.path.join(self.tmp, pieza.asset.name)

    def podar(self, dias=90, gracia=7):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            return prune_lost_mode_evidence(dias, gracia)

    # ------------------------------------------------------- plazo de 90 d

    def test_la_pieza_vencida_se_va_del_disco_y_de_la_tabla(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            vieja = self.captura(cycle=1, dias_atras=91)
        ruta = self.ruta(vieja)
        self.assertTrue(os.path.exists(ruta), "control: el archivo tiene que existir")

        self.podar()

        self.assertFalse(LostModeEvidence.objects.filter(pk=vieja.pk).exists())
        self.assertFalse(os.path.exists(ruta), "el PNG siguió en el disco")

    def test_la_pieza_dentro_del_plazo_no_se_toca(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            reciente = self.captura(cycle=1, dias_atras=89)

        self.podar()

        self.assertTrue(LostModeEvidence.objects.filter(pk=reciente.pk).exists())
        self.assertTrue(os.path.exists(self.ruta(reciente)))

    def test_la_pieza_sin_archivo_tambien_vence(self):
        """La fila que sólo trae el motivo (`wayland_no_soportado`) es evidencia."""
        motivo = LostModeEvidence.objects.create(
            agent=self.agent,
            cycle=1,
            kind=LostModeEvidenceKind.SCREEN,
            note="wayland_no_soportado",
        )
        self.envejecer(motivo, 91)

        self.podar()

        self.assertFalse(LostModeEvidence.objects.filter(pk=motivo.pk).exists())

    def test_el_punto_de_geo_vence_igual_que_la_imagen(self):
        geo = LostModeEvidence.objects.create(
            agent=self.agent,
            cycle=1,
            kind=LostModeEvidenceKind.GEO,
            lat=-33.4489,
            lng=-70.6693,
        )
        self.envejecer(geo, 91)

        self.podar()

        self.assertFalse(LostModeEvidence.objects.filter(pk=geo.pk).exists())

    # -------------------------------------------------------- caso cerrado

    def test_caso_cerrado_hace_mas_de_la_gracia_borra_todo_el_caso(self):
        LostModeState.objects.create(
            agent=self.agent,
            active=False,
            reason="robo, ticket #4821",
            recovered_at=djangotime.now() - dt.timedelta(days=8),
        )
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            # Recién capturada: por antigüedad NO vencería. La borra el cierre.
            pieza = self.captura(cycle=1)
        ruta = self.ruta(pieza)

        self.podar(dias=90, gracia=7)

        self.assertFalse(LostModeEvidence.objects.filter(pk=pieza.pk).exists())
        self.assertFalse(os.path.exists(ruta))

    def test_dentro_de_la_gracia_la_evidencia_sigue_disponible(self):
        """Los días que existen para la denuncia que se presenta después."""
        LostModeState.objects.create(
            agent=self.agent,
            active=False,
            reason="robo, ticket #4821",
            recovered_at=djangotime.now() - dt.timedelta(days=6),
        )
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1)

        self.podar(dias=90, gracia=7)

        self.assertTrue(LostModeEvidence.objects.filter(pk=pieza.pk).exists())
        self.assertTrue(os.path.exists(self.ruta(pieza)))

    def test_gracia_cero_es_la_lectura_literal_del_adr(self):
        LostModeState.objects.create(
            agent=self.agent,
            active=False,
            reason="robo",
            recovered_at=djangotime.now() - dt.timedelta(minutes=5),
        )
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1)

        self.podar(dias=90, gracia=0)

        self.assertFalse(LostModeEvidence.objects.filter(pk=pieza.pk).exists())

    def test_caso_abierto_no_se_toca_nunca(self):
        LostModeState.objects.create(
            agent=self.agent, active=True, reason="robo, ticket #4821"
        )
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1)

        self.podar(dias=90, gracia=0)

        self.assertTrue(LostModeEvidence.objects.filter(pk=pieza.pk).exists())

    def test_equipo_re_marcado_conserva_la_evidencia_del_caso_anterior(self):
        """Re-marcar limpia `recovered_at`: el equipo volvió a estar perdido."""
        LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="se perdió de nuevo",
            recovered_at=None,
        )
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            anterior = self.captura(cycle=1, dias_atras=30)

        self.podar(dias=90, gracia=0)

        self.assertTrue(LostModeEvidence.objects.filter(pk=anterior.pk).exists())

    def test_el_caso_de_otro_equipo_no_se_arrastra(self):
        otro = baker.make_recipe("agents.agent")
        LostModeState.objects.create(
            agent=self.agent,
            active=False,
            reason="robo",
            recovered_at=djangotime.now() - dt.timedelta(days=30),
        )
        LostModeState.objects.create(agent=otro, active=True, reason="robo")
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            cerrado = self.captura(cycle=1)
            abierto = self.captura(cycle=2, agent=otro)

        self.podar()

        self.assertFalse(LostModeEvidence.objects.filter(pk=cerrado.pk).exists())
        self.assertTrue(LostModeEvidence.objects.filter(pk=abierto.pk).exists())
        self.assertTrue(os.path.exists(self.ruta(abierto)))

    # ----------------------------------------------------------- huérfanos

    def test_el_archivo_sin_fila_se_barre_al_cumplir_el_plazo(self):
        """Borrar un AGENTE hace cascada sobre las filas y deja los archivos.

        Sin este barrido, la evidencia de un equipo dado de baja se quedaría en
        el disco para siempre: nadie la lista, nadie la cuenta, nadie la borra.
        """
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1)
        ruta = self.ruta(pieza)
        LostModeEvidence.objects.filter(pk=pieza.pk).delete()  # cascada, sin archivo
        viejo = (djangotime.now() - dt.timedelta(days=91)).timestamp()
        os.utime(ruta, (viejo, viejo))

        self.podar()

        self.assertFalse(os.path.exists(ruta))

    def test_el_huerfano_reciente_no_se_barre(self):
        """El margen que protege al archivo recién escrito por la ingesta.

        Entre `asset.save(...)` y el `save()` de la fila hay una ventana en la
        que el archivo existe y la fila todavía no: barrerlo ahí sería perder
        una captura en un caso abierto.
        """
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1)
        ruta = self.ruta(pieza)
        LostModeEvidence.objects.filter(pk=pieza.pk).delete()

        self.podar()

        self.assertTrue(os.path.exists(ruta))

    def test_las_carpetas_vacias_no_quedan_dando_vueltas(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            pieza = self.captura(cycle=1, dias_atras=91)
        carpeta = os.path.dirname(self.ruta(pieza))

        self.podar()

        self.assertFalse(os.path.exists(carpeta))
        self.assertTrue(os.path.isdir(self.tmp), "la base no se borra")

    def test_una_base_inexistente_no_revienta_la_poda(self):
        """El ambiente que nunca recibió evidencia todavía no tiene el árbol."""
        with override_settings(
            LOST_MODE_EVIDENCE_BASE_PATH=os.path.join(self.tmp, "no-existe")
        ):
            self.assertIn("0 filas", prune_lost_mode_evidence(90, 7))

    # ------------------------------------------------------ el enganche

    def test_el_mantenimiento_la_encola_siempre(self):
        """SIN guard `> 0`: acá el 0 no existe como "apagado" (ADR-025)."""
        with patch("core.tasks.prune_lost_mode_evidence") as tarea:
            core_maintenance_tasks()

        tarea.delay.assert_called_once_with(90, 7)
