"""Tests de la geocerca por sitio (feature 026).

Cubren las tres decisiones de diseño que no son obvias leyendo el código y que, si
se rompen, lo hacen en silencio: (1) que sólo se evalúen orígenes MEDIDOS —
evaluar "ip" fue el bug que originó la feature—, (2) que la precisión del fix se
descuente del margen, y (3) que una alerta abierta NO se cierre por falta de datos
frescos.
"""

from unittest.mock import patch

from model_bakery import baker

from agents.tasks import geofence_check_task
from core.geo import haversine_m
from observerrmm.constants import GEO_CHECK_HISTORY_ID, AlertType
from observerrmm.test import ObserverTestCase

# Datacenter de Oriencoop, Talca — el caso real que originó la feature.
TALCA = (-35.4281789, -71.6598373)
# Lo que devolvían TODOS los locators por IP para ese bloque de Entel: Santiago.
SANTIAGO = (-33.4568700, -70.6482900)


class TestHaversine(ObserverTestCase):
    def test_mismo_punto_es_cero(self):
        # min(1.0, ...) protege el asin del redondeo con puntos idénticos.
        self.assertEqual(haversine_m(*TALCA, *TALCA), 0.0)

    def test_distancia_talca_santiago(self):
        # ~238 km es el error que medimos contra los proveedores de IP.
        km = haversine_m(*TALCA, *SANTIAGO) / 1000
        self.assertAlmostEqual(km, 238.0, delta=2.0)

    def test_es_simetrica(self):
        self.assertAlmostEqual(
            haversine_m(*TALCA, *SANTIAGO), haversine_m(*SANTIAGO, *TALCA), places=6
        )

    def test_un_grado_de_latitud(self):
        # Un grado de latitud son ~111,2 km en cualquier meridiano.
        self.assertAlmostEqual(haversine_m(0, 0, 1, 0) / 1000, 111.2, delta=0.3)


class TestGeofenceTask(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.core = self.coresettings
        self.core.geo_tracking_enabled = True
        self.core.geo_geofence_enabled = True
        self.core.geo_geofence_radius_m = 1000
        # save() invalida CORESETTINGS_CACHE_KEY, así que la tarea lee esto y no
        # una copia cacheada de otro test.
        self.core.save()

        self.site = baker.make("clients.Site", latitude=TALCA[0], longitude=TALCA[1])
        self.agent = baker.make_recipe("agents.online_agent", site=self.site)

    def _geo_point(self, lat, long, source, accuracy=20):
        return baker.make(
            "checks.CheckHistory",
            check_id=GEO_CHECK_HISTORY_ID,
            agent_id=self.agent.agent_id,
            y=accuracy,
            results={"lat": lat, "long": long, "source": source},
        )

    def _open_alerts(self):
        from alerts.models import Alert

        return Alert.objects.filter(alert_type=AlertType.GEOFENCE, resolved=False)

    # --- lo que NO debe alertar -------------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_origen_ip_no_se_evalua(self, _mail):
        """El motivo de existir de la feature: un fix por IP a 238 km NO es
        evidencia de que el equipo se movió, es el error del proveedor."""
        self._geo_point(*SANTIAGO, "ip")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_origen_site_no_se_evalua(self, _mail):
        # Sería tautológico: esas coordenadas SON las del sitio.
        self._geo_point(*SANTIAGO, "site")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_dentro_del_radio_no_alerta(self, _mail):
        self._geo_point(TALCA[0] + 0.001, TALCA[1], "wifi")  # ~111 m
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_precision_del_fix_se_descuenta(self, _mail):
        """A 1.010 m con un fix de ±20 m el equipo puede estar dentro: no se
        alerta con un dato que no permite afirmarlo."""
        self._geo_point(TALCA[0] + 0.00908, TALCA[1], "wifi", accuracy=20)
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_equipo_autorizado_a_salir_no_alerta(self, _mail):
        self.agent.geo_offsite_allowed = True
        self.agent.save(update_fields=["geo_offsite_allowed"])
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_sitio_sin_coordenadas_no_alerta(self, _mail):
        self.site.latitude = None
        self.site.longitude = None
        self.site.save(update_fields=["latitude", "longitude"])
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_interruptor_apagado_no_alerta(self, _mail):
        self.core.geo_geofence_enabled = False
        self.core.save(update_fields=["geo_geofence_enabled"])
        self._geo_point(*SANTIAGO, "wifi")
        self.assertEqual(geofence_check_task(), "geofence disabled")
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_mantencion_no_alerta(self, _mail):
        self.agent.maintenance_mode = True
        self.agent.save(update_fields=["maintenance_mode"])
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    # --- lo que SÍ debe alertar ------------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_fuera_del_radio_alerta_y_manda_correo(self, mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()

        alert = self._open_alerts().get()
        self.assertEqual(alert.agent, self.agent)
        self.assertIn("238.0 km", alert.message)
        # hidden=False o no aparece en el widget de la consola.
        self.assertFalse(alert.hidden)
        mail.assert_called_once()

    @patch("agents.tasks._send_geofence_email")
    def test_origen_native_tambien_se_evalua(self, _mail):
        self._geo_point(*SANTIAGO, "native")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 1)

    @patch("agents.tasks._send_geofence_email")
    def test_no_duplica_ni_re_notifica(self, mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        geofence_check_task()

        self.assertEqual(self._open_alerts().count(), 1)
        mail.assert_called_once()

    # --- resolución -------------------------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_volver_al_sitio_resuelve(self, _mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 1)

        self._geo_point(*TALCA, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_autorizarlo_despues_resuelve(self, _mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()

        self.agent.geo_offsite_allowed = True
        self.agent.save(update_fields=["geo_offsite_allowed"])
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 0)

    @patch("agents.tasks._send_geofence_email")
    def test_sin_datos_frescos_NO_resuelve(self, _mail):
        """El caso del notebook robado: se fue del sitio y dejó de reportar.
        Cerrar la alerta por falta de datos sería lo contrario de lo que el
        operador necesita ver."""
        import datetime as dt

        from django.utils import timezone as djangotime

        from agents.tasks import GEOFENCE_MAX_FIX_AGE
        from checks.models import CheckHistory

        point = self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 1)

        # El punto envejece más allá de la ventana de evaluación.
        CheckHistory.objects.filter(pk=point.pk).update(
            x=djangotime.now() - GEOFENCE_MAX_FIX_AGE - dt.timedelta(hours=1)
        )
        geofence_check_task()
        self.assertEqual(self._open_alerts().count(), 1)


class TestGeofenceOutsideFlag(ObserverTestCase):
    """Feature 041 · geofence_check_task espeja el estado dentro/fuera en el campo
    `Agent.outside_geofence`, la fuente reactiva que lee el config del agente.

    Lo que se congela acá: se prende al abrir la alerta, se apaga al resolver (por
    volver al sitio o por dejar de ser evaluable), y NO se prende para equipos
    eximidos —autorizado a salir / mantención—, que son justamente los que no
    deben gatillar contramedidas.
    """

    def setUp(self):
        self.setup_coresettings()
        self.core = self.coresettings
        self.core.geo_tracking_enabled = True
        self.core.geo_geofence_enabled = True
        self.core.geo_geofence_radius_m = 1000
        self.core.save()

        self.site = baker.make("clients.Site", latitude=TALCA[0], longitude=TALCA[1])
        self.agent = baker.make_recipe("agents.online_agent", site=self.site)

    def _geo_point(self, lat, long, source, accuracy=20):
        return baker.make(
            "checks.CheckHistory",
            check_id=GEO_CHECK_HISTORY_ID,
            agent_id=self.agent.agent_id,
            y=accuracy,
            results={"lat": lat, "long": long, "source": source},
        )

    def _flag(self):
        self.agent.refresh_from_db(fields=["outside_geofence"])
        return self.agent.outside_geofence

    # --- se prende al abrir ----------------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_fuera_prende_el_flag(self, _mail):
        self.assertFalse(self._flag())
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertTrue(self._flag())

    @patch("agents.tasks._send_geofence_email")
    def test_dentro_no_prende_el_flag(self, _mail):
        self._geo_point(TALCA[0] + 0.001, TALCA[1], "wifi")  # ~111 m, dentro
        geofence_check_task()
        self.assertFalse(self._flag())

    # --- se apaga al resolver --------------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_volver_al_sitio_apaga_el_flag(self, _mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertTrue(self._flag())

        self._geo_point(*TALCA, "wifi")
        geofence_check_task()
        self.assertFalse(self._flag())

    @patch("agents.tasks._send_geofence_email")
    def test_autorizarlo_despues_apaga_el_flag(self, _mail):
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertTrue(self._flag())

        self.agent.geo_offsite_allowed = True
        self.agent.save(update_fields=["geo_offsite_allowed"])
        geofence_check_task()
        self.assertFalse(self._flag())

    # --- eximidos NO prenden el flag -------------------------------------------

    @patch("agents.tasks._send_geofence_email")
    def test_autorizado_a_salir_no_prende_el_flag(self, _mail):
        self.agent.geo_offsite_allowed = True
        self.agent.save(update_fields=["geo_offsite_allowed"])
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertFalse(self._flag())

    @patch("agents.tasks._send_geofence_email")
    def test_mantencion_no_prende_el_flag(self, _mail):
        self.agent.maintenance_mode = True
        self.agent.save(update_fields=["maintenance_mode"])
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertFalse(self._flag())

    @patch("agents.tasks._send_geofence_email")
    def test_no_reescribe_en_cada_pasada_estando_fuera(self, _mail):
        """El flag ya prendido no debe costar un UPDATE por pasada."""
        self._geo_point(*SANTIAGO, "wifi")
        geofence_check_task()
        self.assertTrue(self._flag())

        with patch(
            "agents.models.Agent.save", side_effect=AssertionError("no debía guardar")
        ):
            # Sigue fuera y con el flag ya en True: no hay nada que escribir.
            geofence_check_task()
        self.assertTrue(self._flag())


class TestSiteCoordinatesValidation(ObserverTestCase):
    """Las coordenadas del sitio son OPCIONALES pero no a medias."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")

    def _patch_site(self, site, payload):
        return self.client.put(f"/clients/sites/{site.pk}/", payload, format="json")

    def test_sitio_se_crea_sin_coordenadas(self):
        r = self.client.post(
            "/clients/sites/",
            {"site": {"client": self.client_obj.pk, "name": "Sin coords"}},
            format="json",
        )
        self.assertIn(r.status_code, (200, 201))

    def test_solo_latitud_es_rechazado(self):
        site = baker.make("clients.Site", client=self.client_obj)
        r = self._patch_site(site, {"site": {"latitude": TALCA[0]}})
        self.assertEqual(r.status_code, 400)

    def test_las_dos_juntas_se_aceptan(self):
        site = baker.make("clients.Site", client=self.client_obj)
        r = self._patch_site(
            site, {"site": {"latitude": TALCA[0], "longitude": TALCA[1]}}
        )
        self.assertIn(r.status_code, (200, 201))
        site.refresh_from_db()
        self.assertAlmostEqual(site.latitude, TALCA[0])

    def test_latitud_fuera_de_rango_es_rechazada(self):
        site = baker.make("clients.Site", client=self.client_obj)
        r = self._patch_site(site, {"site": {"latitude": 95.0, "longitude": 0.0}})
        self.assertEqual(r.status_code, 400)

    def test_null_island_es_rechazado(self):
        site = baker.make("clients.Site", client=self.client_obj)
        r = self._patch_site(site, {"site": {"latitude": 0.0, "longitude": 0.0}})
        self.assertEqual(r.status_code, 400)
