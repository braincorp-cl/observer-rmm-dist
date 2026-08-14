"""Feature 030 · Fase 3 · T022 · exportación del caso a PDF.

Un PDF se genera una vez y después circula solo, fuera del alcance de la
consola y de sus permisos. Eso convierte tres cosas en errores caros, y son las
que se prueban acá:

- que exportar **sin** `can_view_lost_evidence` NO meta las imágenes, y que el
  documento lo diga. Un informe que omite en silencio es peor que uno que no se
  pudo generar: quien lo recibe lo cita como completo;
- que los **dos relojes** —el del equipo y el del servidor— salgan siempre. Es
  el dato que alguien va a discutir si el documento llega a un tribunal;
- que la exportación quede **auditada**, y auditada aunque el render falle.

El contexto se prueba aparte del PDF a propósito. Parsear un PDF para ver si
dice lo que tiene que decir es frágil y lento; lo que importa está en
`armar_contexto`, y del `generate_pdf` sólo hace falta saber que produce un PDF
de verdad — eso se comprueba una vez, por los primeros bytes.
"""

import tempfile

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone as djangotime
from model_bakery import baker

from agents.lostmode_export import (
    MAX_IMAGENES_EMBEBIDAS,
    armar_contexto,
    armar_html,
    nombre_archivo,
)
from agents.models import LostModeEvidence, LostModeState
from logs.models import AuditLog
from observerrmm.constants import AuditActionType, LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

base_url = "/agents"

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestExportacionDelCaso(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()

        self.agent = baker.make_recipe("agents.agent")
        self.estado = LostModeState.objects.create(
            agent=self.agent,
            active=True,
            reason="robo en la vía pública, ticket #4821",
            marked_at=djangotime.now(),
        )
        self.tmp = tempfile.mkdtemp(prefix="lostmode-export-")
        self.url = f"{base_url}/{self.agent.agent_id}/lostmode/export/"

    def crear_piezas(self):
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            geo = LostModeEvidence.objects.create(
                agent=self.agent,
                cycle=1,
                kind=LostModeEvidenceKind.GEO,
                lat=-33.4489,
                lng=-70.6693,
                accuracy_m=35,
                source="wifi",
                captured_at=djangotime.now(),
            )
            pantalla = LostModeEvidence(
                agent=self.agent,
                cycle=1,
                kind=LostModeEvidenceKind.SCREEN,
                session_user="ana",
                captured_at=djangotime.now(),
            )
            pantalla.asset.save("pantalla-000001.png", ContentFile(PNG_1x1), save=False)
            pantalla.save()

            sin_captura = LostModeEvidence.objects.create(
                agent=self.agent,
                cycle=2,
                kind=LostModeEvidenceKind.SCREEN,
                note="wayland_sin_autorizacion",
                captured_at=djangotime.now(),
            )
        return geo, pantalla, sin_captura

    def _contexto(self, *, con_imagenes):
        piezas = list(
            LostModeEvidence.objects.filter(agent=self.agent).order_by("-cycle", "kind")
        )
        return armar_contexto(
            agent=self.agent,
            state=self.estado,
            piezas=piezas,
            retencion={"prune_days": 90, "closed_case_days": 30},
            cifrado=True,
            exportado_por="ana",
            con_imagenes=con_imagenes,
        )

    # ------------------------------------------------------------- contexto

    def test_el_contexto_trae_el_caso_completo(self):
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=True)

        self.assertEqual(ctx["hostname"], self.agent.hostname)
        self.assertEqual(ctx["estado_caso"], "ABIERTO")
        self.assertIn("ticket #4821", ctx["motivo"])
        self.assertEqual(ctx["total_piezas"], 3)
        self.assertEqual(ctx["retencion_dias"], 90)

        # Orden: lo último que se supo del equipo, primero. El PDF y la pantalla
        # tienen que leerse igual.
        self.assertEqual(ctx["piezas"][0]["ciclo"], 2)

        # El tipo sale en el idioma del documento, no con la etiqueta en inglés
        # de la API: esto lo lee una persona en un mostrador, no un cliente HTTP.
        self.assertEqual(ctx["piezas"][0]["tipo"], "Captura de pantalla")
        self.assertEqual(
            [p["tipo"] for p in ctx["piezas"] if p["es_geo"]], ["Posición del equipo"]
        )

    def test_los_dos_relojes_salen_siempre(self):
        """El del equipo y el del servidor. Entre los dos puede haber horas."""
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=True)

        for pieza in ctx["piezas"]:
            self.assertNotEqual(pieza["capturado_equipo"], "—")
            self.assertNotEqual(pieza["recibido_servidor"], "—")

    def test_la_imagen_se_embebe_como_data_uri(self):
        """Enlazarla sería mandarle a quien recibe el PDF una página de login."""
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=True)

        con_imagen = [p for p in ctx["piezas"] if p["imagen"]]
        self.assertEqual(len(con_imagen), 1)
        self.assertTrue(con_imagen[0]["imagen"].startswith("data:image/png;base64,"))
        self.assertEqual(ctx["imagenes_embebidas"], 1)

    def test_sin_permiso_de_ver_evidencia_no_hay_imagenes_y_se_declara(self):
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=False)

        self.assertEqual(ctx["imagenes_embebidas"], 0)
        self.assertFalse(any(p["imagen"] for p in ctx["piezas"]))

        # Y el documento tiene que DECIRLO, no callarlo.
        omitidas = [
            p for p in ctx["piezas"] if "no tiene permiso" in p["imagen_ausente"]
        ]
        self.assertEqual(
            len(omitidas), 2, "las dos piezas de pantalla deben declararlo"
        )

        html = armar_html(ctx)
        self.assertIn("Documento sin imágenes", html)

    def test_la_pieza_sin_archivo_dice_por_que(self):
        """La que sólo trae el motivo del agente: no es una imagen rota."""
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=True)

        ciclo2 = [p for p in ctx["piezas"] if p["ciclo"] == 2][0]
        self.assertEqual(ciclo2["nota"], "wayland_sin_autorizacion")
        self.assertEqual(
            ciclo2["imagen_ausente"], "el equipo no la pudo tomar en este ciclo"
        )

    def test_la_geo_no_se_reporta_como_imagen_faltante(self):
        """Una posición no tiene imagen por definición: no hay nada que explicar."""
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            ctx = self._contexto(con_imagenes=False)

        geo = [p for p in ctx["piezas"] if p["es_geo"]][0]
        self.assertEqual(geo["imagen_ausente"], "")
        self.assertIn("-33.448900", geo["coordenadas"])
        self.assertIn("±35 m", geo["coordenadas"])
        self.assertIn("wifi", geo["coordenadas"])

    def test_el_recorte_por_tamano_se_declara(self):
        """Un recorte silencioso convertiría 'esto es todo' en una mentira."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            for i in range(MAX_IMAGENES_EMBEBIDAS + 3):
                pieza = LostModeEvidence(
                    agent=self.agent,
                    cycle=i + 1,
                    kind=LostModeEvidenceKind.SCREEN,
                    captured_at=djangotime.now(),
                )
                pieza.asset.save(
                    f"pantalla-{i:06d}.png", ContentFile(PNG_1x1), save=False
                )
                pieza.save()

            ctx = self._contexto(con_imagenes=True)

        self.assertEqual(ctx["imagenes_embebidas"], MAX_IMAGENES_EMBEBIDAS)
        self.assertEqual(ctx["imagenes_recortadas"], 3)
        self.assertIn("Documento recortado", armar_html(ctx))

    def test_el_cifrado_indeterminado_no_se_lee_como_cifrado(self):
        """`None` es un tercer valor: el servidor no lo pudo decir."""
        ctx = armar_contexto(
            agent=self.agent,
            state=self.estado,
            piezas=[],
            retencion={"prune_days": 90, "closed_case_days": 30},
            cifrado=None,
            exportado_por="ana",
            con_imagenes=True,
        )
        html = armar_html(ctx)
        self.assertIn("no se pudo determinar", html)

        html_sin_cifrar = armar_html({**ctx, "cifrado": False})
        self.assertIn("sin cifrar", html_sin_cifrar)

    def test_el_nombre_del_archivo_es_ascii_y_sin_espacios(self):
        """Viaja por correo y termina en rutas de Windows."""
        self.agent.hostname = "NOTEBOOK Ñuñoa: dirección"
        nombre = nombre_archivo(self.agent)

        self.assertTrue(nombre.endswith(".pdf"))
        self.assertTrue(nombre.isascii(), nombre)
        self.assertNotIn(" ", nombre)
        self.assertNotIn(":", nombre)

    def test_un_equipo_sin_caso_igual_exporta(self):
        """Sin `state` el documento sale, y dice que no hay caso registrado."""
        ctx = armar_contexto(
            agent=self.agent,
            state=None,
            piezas=[],
            retencion={"prune_days": 90, "closed_case_days": 30},
            cifrado=True,
            exportado_por="ana",
            con_imagenes=True,
        )
        self.assertEqual(ctx["estado_caso"], "sin caso registrado")
        self.assertIn("No hay evidencia registrada", armar_html(ctx))

    # ----------------------------------------------------------- la vista

    def test_la_exportacion_devuelve_un_pdf_de_verdad(self):
        self.authenticate()
        self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("attachment;", r["Content-Disposition"])
        # El `exit 0` no prueba el efecto: lo que prueba que es un PDF es la
        # firma del formato, no que la vista haya devuelto 200.
        self.assertTrue(r.content.startswith(b"%PDF-"))
        self.assertGreater(len(r.content), 1000)

        self.check_not_authenticated("get", self.url)

    def test_exportar_exige_operar_el_caso_pero_no_ver_rostros(self):
        """Un solo permiso en la puerta; el segundo decide si van las imágenes."""
        self.crear_piezas()

        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)
        self.check_not_authorized("get", self.url)

        user.role.can_manage_lost_mode = True
        user.role.save()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF-"))

    def test_exportar_queda_auditado_con_si_llevo_imagenes(self):
        """Es la acción que saca la evidencia del control de la consola."""
        self.crear_piezas()

        user = self.create_user_with_roles([])
        user.role.can_manage_lost_mode = True
        user.role.save()
        self.client.force_authenticate(user=user)

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            self.client.get(self.url)

        fila = AuditLog.objects.filter(
            action=AuditActionType.LOST_MODE, agent_id=self.agent.agent_id
        ).last()
        self.assertIsNotNone(fila)
        self.assertIn("exported the lost device case", fila.message)
        self.assertIn("images=no", fila.after_value)

        # Y con el permiso, la fila tiene que decir lo contrario.
        user.role.can_view_lost_evidence = True
        user.role.save()
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            self.client.get(self.url)

        fila = AuditLog.objects.filter(
            action=AuditActionType.LOST_MODE, agent_id=self.agent.agent_id
        ).last()
        self.assertIn("images=yes", fila.after_value)

    def test_el_alcance_por_rol_recorta_la_exportacion(self):
        ajeno = baker.make_recipe("agents.agent")

        user = self.create_user_with_roles([])
        user.role.can_manage_lost_mode = True
        user.role.save()
        user.role.can_view_clients.set([self.agent.client])
        self.client.force_authenticate(user=user)

        self.check_not_authorized(
            "get", f"{base_url}/{ajeno.agent_id}/lostmode/export/"
        )
