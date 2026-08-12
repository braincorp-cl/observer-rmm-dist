"""Feature 030 · Fase 1 · lectura de la línea de tiempo del caso (T010 + T012).

La consola lee dos cosas: el listado de piezas del caso y el archivo de cada
pieza. Lo que se prueba acá es la parte que, si se equivoca, no se nota mirando
la pantalla:

- que la evidencia NO se sirva por una URL del almacenamiento sino por una vista
  con permiso. La diferencia se ve el día en que alguien pega el enlace en un
  chat: una URL estática funciona para cualquiera que la tenga;
- que `can_view_lost_evidence` sea realmente un segundo permiso y no un adorno.
  ADR-025 separa a propósito operar el caso de MIRAR lo que la pantalla mostraba,
  porque la persona que tiene el equipo puede ser su propio dueño;
- que el alcance por rol recorte también acá — el listado de un equipo ajeno no
  se puede leer aunque se tengan los dos permisos;
- que una pieza sin archivo (la que sólo trae el motivo) no reviente la descarga.
"""

import tempfile

from django.test import override_settings
from model_bakery import baker

from agents.models import LostModeEvidence, LostModeState
from observerrmm.constants import LostModeEvidenceKind
from observerrmm.test import ObserverTestCase

base_url = "/agents"

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestLineaDeTiempo(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.setup_client()

        self.agent = baker.make_recipe("agents.agent")
        self.estado = LostModeState.objects.create(
            agent=self.agent, active=True, reason="robo, ticket #4821"
        )
        self.tmp = tempfile.mkdtemp(prefix="lostmode-evidence-")
        self.url = f"{base_url}/{self.agent.agent_id}/lostmode/evidence/"

    def crear_piezas(self):
        """Dos ciclos: uno con captura, otro que sólo pudo decir por qué no."""
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            geo = LostModeEvidence.objects.create(
                agent=self.agent,
                cycle=1,
                kind=LostModeEvidenceKind.GEO,
                lat=-33.4489,
                lng=-70.6693,
                accuracy_m=35,
                source="wifi",
            )
            pantalla = LostModeEvidence(
                agent=self.agent,
                cycle=1,
                kind=LostModeEvidenceKind.SCREEN,
                session_user="ana",
            )
            from django.core.files.base import ContentFile

            pantalla.asset.save("pantalla-000001.png", ContentFile(PNG_1x1), save=False)
            pantalla.save()

            sin_captura = LostModeEvidence.objects.create(
                agent=self.agent,
                cycle=2,
                kind=LostModeEvidenceKind.SCREEN,
                note="wayland_no_soportado",
            )
        return geo, pantalla, sin_captura

    # ------------------------------------------------------------- listado

    def test_listado_trae_el_caso_y_sus_piezas(self):
        self.authenticate()
        self.crear_piezas()

        r = self.client.get(self.url, format="json")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["state"]["reason"], "robo, ticket #4821")
        self.assertEqual(len(r.data["evidence"]), 3)

        # Orden: lo último que se supo del equipo va primero.
        self.assertEqual(r.data["evidence"][0]["cycle"], 2)

        # La ruta del archivo NO viaja: la consola arma la URL de descarga con el
        # id, y esa descarga pasa por la vista con permiso.
        for pieza in r.data["evidence"]:
            self.assertNotIn("asset", pieza)
        self.assertTrue(
            any(p["has_asset"] for p in r.data["evidence"]),
            "la pieza con captura tiene que declarar que trae archivo",
        )

        self.check_not_authenticated("get", self.url)

    def test_listado_de_equipo_sin_caso_no_revienta(self):
        """Un equipo que nunca se marcó: `state` en null y la lista vacía."""
        self.authenticate()
        otro = baker.make_recipe("agents.agent")

        r = self.client.get(
            f"{base_url}/{otro.agent_id}/lostmode/evidence/", format="json"
        )

        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["state"])
        self.assertEqual(r.data["evidence"], [])

    # ------------------------------------------------------------ descarga

    def test_descarga_de_la_captura(self):
        self.authenticate()
        _, pantalla, _ = self.crear_piezas()

        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self.client.get(f"{self.url}{pantalla.pk}/file/")

            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), PNG_1x1)

    def test_pieza_sin_archivo_no_revienta_la_descarga(self):
        self.authenticate()
        _, _, sin_captura = self.crear_piezas()

        r = self.client.get(f"{self.url}{sin_captura.pk}/file/")

        # 400 con mensaje, no un 500 ni un archivo vacío: el motivo ya viajó en
        # el listado y la consola no debería haber pedido este archivo.
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_pedir_la_evidencia_de_otro_equipo_por_su_id(self):
        """El id es global; el filtro por agente es lo que impide el cruce."""
        self.authenticate()
        _, pantalla, _ = self.crear_piezas()
        otro = baker.make_recipe("agents.agent")

        r = self.client.get(
            f"{base_url}/{otro.agent_id}/lostmode/evidence/{pantalla.pk}/file/"
        )

        self.assertEqual(r.status_code, 404)

    # --------------------------------------------------------- autorización

    def test_ver_la_pantalla_exige_su_propio_permiso(self):
        _, pantalla, _ = self.crear_piezas()
        archivo_url = f"{self.url}{pantalla.pk}/file/"

        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)

        self.check_not_authorized("get", self.url)
        self.check_not_authorized("get", archivo_url)

        # Operar el caso alcanza para seguir el recorrido...
        user.role.can_manage_lost_mode = True
        user.role.save()
        self.check_authorized("get", self.url)
        # ...pero NO para mirar lo que la pantalla estaba mostrando.
        self.check_not_authorized("get", archivo_url)

        user.role.can_view_lost_evidence = True
        user.role.save()
        with override_settings(LOST_MODE_EVIDENCE_BASE_PATH=self.tmp):
            r = self.client.get(archivo_url)
            self.assertEqual(r.status_code, 200)

    def test_ver_evidencia_sin_operar_el_caso_no_alcanza(self):
        """Los dos permisos son necesarios, no alternativos."""
        _, pantalla, _ = self.crear_piezas()

        user = self.create_user_with_roles([])
        user.role.can_view_lost_evidence = True
        user.role.save()
        self.client.force_authenticate(user=user)

        self.check_not_authorized("get", f"{self.url}{pantalla.pk}/file/")

    def test_el_alcance_por_rol_recorta_la_linea_de_tiempo(self):
        ajeno = baker.make_recipe("agents.agent")

        user = self.create_user_with_roles([])
        user.role.can_manage_lost_mode = True
        user.role.can_view_lost_evidence = True
        user.role.save()
        user.role.can_view_clients.set([self.agent.client])
        self.client.force_authenticate(user=user)

        self.check_authorized("get", self.url)
        self.check_not_authorized(
            "get", f"{base_url}/{ajeno.agent_id}/lostmode/evidence/"
        )
