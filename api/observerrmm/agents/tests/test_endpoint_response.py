"""Feature 028 · respuesta rápida de endpoint (lock / alert / alarm).

Homologación de las acciones `lock`, `alert` y `alarm` de Prey (backlog 024).

Lo que se prueba acá es lo que puede romperse en silencio:

- que el payload NATS sea exactamente el que el agente espera (un typo en `func`
  o en una clave del payload no falla: el agente simplemente ignora el mensaje);
- que los códigos del agente lleguen al frontend con el prefijo que el
  interceptor de axios necesita para traducirlos (sin prefijo, el operador ve el
  código crudo en pantalla);
- que los tres permisos nuevos funcionen por separado, incluida la vía masiva,
  que es por donde se podrían haber saltado;
- que la duración de la alarma se acote de verdad.
"""

from unittest.mock import patch

from model_bakery import baker

from logs.models import AuditLog
from observerrmm.constants import (
    ALARM_MAX_SECONDS,
    ALARM_MIN_SECONDS,
    AuditActionType,
)
from observerrmm.test import ObserverTestCase

base_url = "/agents"


class TestEndpointResponse(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()
        self.agent = baker.make_recipe("agents.agent")

    # ---------------------------------------------------------------- lock

    @patch("agents.models.Agent.nats_cmd")
    def test_lock_screen(self, nats_cmd):
        url = f"{base_url}/{self.agent.agent_id}/lock/"

        nats_cmd.return_value = "ok"
        r = self.client.post(url, format="json")
        self.assertEqual(r.status_code, 200)
        nats_cmd.assert_called_with({"func": "lock"}, timeout=15)

        self.check_not_authenticated("post", url)

    @patch("agents.models.Agent.nats_cmd")
    def test_lock_sin_sesion_de_usuario(self, nats_cmd):
        """El caso más importante: nadie tiene sesión abierta.

        No es un fallo del agente y el operador tiene que poder distinguirlo, así
        que se responde 400 con el código prefijado en vez de un 200 mentiroso.
        """
        url = f"{base_url}/{self.agent.agent_id}/lock/"

        nats_cmd.return_value = "no_user_session"
        r = self.client.post(url, format="json")

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "endpoint_response:no_user_session")

    @patch("agents.models.Agent.nats_cmd")
    def test_agente_incomunicado(self, nats_cmd):
        """timeout/natsdown NO son códigos del agente: es que no contestó."""
        url = f"{base_url}/{self.agent.agent_id}/lock/"

        for respuesta in ("timeout", "natsdown"):
            nats_cmd.return_value = respuesta
            r = self.client.post(url, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data, "endpoint_response:agent_unreachable")

    @patch("agents.models.Agent.nats_cmd")
    def test_codigo_desconocido_se_normaliza(self, nats_cmd):
        """Un agente viejo puede contestar cualquier cosa.

        Se colapsa a `error` en vez de reenviarlo: el frontend traduce por clave y
        un código que no conoce le quedaría crudo en pantalla al operador.
        """
        url = f"{base_url}/{self.agent.agent_id}/lock/"

        nats_cmd.return_value = "algo que el frontend no conoce"
        r = self.client.post(url, format="json")

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, "endpoint_response:error")

    # --------------------------------------------------------------- alert

    @patch("agents.models.Agent.nats_cmd")
    def test_send_alert(self, nats_cmd):
        url = f"{base_url}/{self.agent.agent_id}/alert/"

        nats_cmd.return_value = "ok"
        r = self.client.post(
            url,
            {"title": "Aviso de TI", "message": "Guarda tu trabajo."},
            format="json",
        )

        self.assertEqual(r.status_code, 200)
        nats_cmd.assert_called_with(
            {
                "func": "alert",
                "payload": {"title": "Aviso de TI", "message": "Guarda tu trabajo."},
            },
            timeout=15,
        )

        self.check_not_authenticated("post", url)

    @patch("agents.models.Agent.nats_cmd")
    def test_alert_rechaza_mensaje_vacio(self, nats_cmd):
        """Sin mensaje no se gasta un viaje por NATS: se corta acá."""
        url = f"{base_url}/{self.agent.agent_id}/alert/"

        for cuerpo in ({"message": ""}, {"message": "   "}, {}):
            r = self.client.post(url, cuerpo, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data, "endpoint_response:empty_message")

        nats_cmd.assert_not_called()

    @patch("agents.models.Agent.nats_cmd")
    def test_alert_recorta_textos_largos(self, nats_cmd):
        url = f"{base_url}/{self.agent.agent_id}/alert/"

        nats_cmd.return_value = "ok"
        self.client.post(
            url, {"title": "T" * 500, "message": "M" * 5000}, format="json"
        )

        enviado = nats_cmd.call_args[0][0]["payload"]
        self.assertEqual(len(enviado["title"]), 120)
        self.assertEqual(len(enviado["message"]), 2000)

    @patch("agents.models.Agent.nats_cmd")
    def test_alert_conserva_acentos(self, nats_cmd):
        """La flota es hispanohablante: el texto tiene que viajar intacto."""
        url = f"{base_url}/{self.agent.agent_id}/alert/"

        mensaje = "Reunión mañana. Año nuevo, ñandú, ¿sí?"
        nats_cmd.return_value = "ok"
        self.client.post(url, {"title": "Atención", "message": mensaje}, format="json")

        self.assertEqual(nats_cmd.call_args[0][0]["payload"]["message"], mensaje)

    # --------------------------------------------------------------- alarm

    @patch("agents.models.Agent.nats_cmd")
    def test_sound_alarm(self, nats_cmd):
        url = f"{base_url}/{self.agent.agent_id}/alarm/"

        nats_cmd.return_value = "ok"
        r = self.client.post(url, {"duration": 45}, format="json")

        self.assertEqual(r.status_code, 200)
        # La duración viaja como TEXTO: el payload NATS es map[string]string en el
        # agente. Mandarla como int haría que el agente la ignore.
        nats_cmd.assert_called_with(
            {"func": "alarm", "payload": {"duration": "45"}}, timeout=15
        )

        self.check_not_authenticated("post", url)

    @patch("agents.models.Agent.nats_cmd")
    def test_alarm_acota_la_duracion(self, nats_cmd):
        """El tope es lo que evita dejar un equipo sonando indefinidamente."""
        url = f"{base_url}/{self.agent.agent_id}/alarm/"
        nats_cmd.return_value = "ok"

        casos = [
            (99999, ALARM_MAX_SECONDS),
            (1, ALARM_MIN_SECONDS),
            (0, ALARM_MIN_SECONDS),
            (-30, ALARM_MIN_SECONDS),
            ("no es un número", 30),
            (None, 30),
        ]

        for entrada, esperado in casos:
            self.client.post(url, {"duration": entrada}, format="json")
            self.assertEqual(
                nats_cmd.call_args[0][0]["payload"]["duration"],
                str(esperado),
                msg=f"duration={entrada!r} debía acotarse a {esperado}",
            )

    @patch("agents.models.Agent.nats_cmd")
    def test_stop_alarm(self, nats_cmd):
        url = f"{base_url}/{self.agent.agent_id}/alarm/"

        nats_cmd.return_value = "ok"
        r = self.client.delete(url, format="json")

        self.assertEqual(r.status_code, 200)
        nats_cmd.assert_called_with({"func": "stopalarm"}, timeout=15)

        self.check_not_authenticated("delete", url)

    # ------------------------------------------------------------ auditoría

    @patch("agents.models.Agent.nats_cmd")
    def test_queda_auditado_quien_y_a_quien(self, nats_cmd):
        """"¿Quién me bloqueó la sesión?" tiene que tener respuesta."""
        nats_cmd.return_value = "ok"

        self.client.post(f"{base_url}/{self.agent.agent_id}/lock/", format="json")

        log = AuditLog.objects.filter(
            action=AuditActionType.ENDPOINT_RESPONSE
        ).last()
        self.assertIsNotNone(log)
        self.assertEqual(log.agent_id, self.agent.agent_id)
        self.assertIn("lock", log.message)

    @patch("agents.models.Agent.nats_cmd")
    def test_el_texto_del_mensaje_queda_en_la_auditoria(self, nats_cmd):
        nats_cmd.return_value = "ok"

        self.client.post(
            f"{base_url}/{self.agent.agent_id}/alert/",
            {"title": "Aviso", "message": "El equipo será retirado hoy."},
            format="json",
        )

        log = AuditLog.objects.filter(
            action=AuditActionType.ENDPOINT_RESPONSE
        ).last()
        self.assertEqual(log.after_value, "El equipo será retirado hoy.")

    @patch("agents.models.Agent.nats_cmd")
    def test_se_audita_incluso_si_el_agente_no_pudo(self, nats_cmd):
        """El intento se registra aunque falle.

        Importa para el caso de uso real: si alguien manda un bloqueo a un equipo
        y falla, el intento tiene que quedar igual — auditar sólo los éxitos
        borraría del registro justamente los casos que se investigan.
        """
        nats_cmd.return_value = "no_user_session"

        self.client.post(f"{base_url}/{self.agent.agent_id}/lock/", format="json")

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditActionType.ENDPOINT_RESPONSE
            ).exists()
        )


class TestEndpointResponsePermissions(ObserverTestCase):
    def setUp(self):
        self.setup_client()
        self.setup_coresettings()
        self.agent = baker.make_recipe("agents.agent")

    @patch("agents.models.Agent.nats_cmd")
    def test_los_tres_permisos_son_independientes(self, nats_cmd):
        """Cada acción exige SU permiso y ninguno habilita a los otros.

        Es la razón de haber creado tres permisos en vez de uno: mandar un mensaje
        es inocuo, bloquear interrumpe al usuario y la alarma lo expone frente a
        quien tenga al lado. Un rol de mesa de ayuda puede necesitar el primero
        sin los otros dos.
        """
        nats_cmd.return_value = "ok"

        TODOS = ("can_send_alerts", "can_lock_agents", "can_sound_alarm")
        cuerpo = {"message": "hola"}

        casos = [
            ("can_send_alerts", "post", "alert"),
            ("can_lock_agents", "post", "lock"),
            ("can_sound_alarm", "post", "alarm"),
            ("can_sound_alarm", "delete", "alarm"),
        ]

        ajeno = baker.make_recipe("agents.agent")

        for perm, metodo, accion in casos:
            url = f"{base_url}/{self.agent.agent_id}/{accion}/"
            url_ajeno = f"{base_url}/{ajeno.agent_id}/{accion}/"

            user = self.create_user_with_roles([])
            self.client.force_authenticate(user=user)

            # rol vacío: prohibido
            self.check_not_authorized(metodo, url, cuerpo)

            # los OTROS dos permisos no alcanzan
            for otro in TODOS:
                if otro != perm:
                    setattr(user.role, otro, True)
            user.role.save()
            self.check_not_authorized(metodo, url, cuerpo)

            # con el permiso correcto: permitido
            setattr(user.role, perm, True)
            user.role.save()
            self.check_authorized(metodo, url, cuerpo)

            # y el permiso global no basta si el rol no alcanza a ese cliente: las
            # tres clases verifican también `_has_perm_on_agent`.
            user.role.can_view_clients.set([self.agent.client])
            self.check_authorized(metodo, url, cuerpo)
            self.check_not_authorized(metodo, url_ajeno, cuerpo)

    @patch("agents.tasks.bulk_endpoint_response_task.delay")
    def test_bulk_no_permite_saltarse_los_permisos(self, bulk_task):
        """`can_run_bulk` por sí solo no habilita bloquear la flota.

        Sin este chequeo, la vía masiva sería una puerta trasera a los tres
        permisos nuevos: quien pudiera correr acciones masivas podría bloquear
        todos los equipos sin tener `can_lock_agents`.
        """
        url = f"{base_url}/actions/bulk/"
        payload = {
            "mode": "lock",
            "target": "all",
            "monType": "all",
            "osType": "all",
            "agents": [],
            "client": None,
            "site": None,
        }

        user = self.create_user_with_roles(["can_run_bulk", "can_list_agents"])
        self.client.force_authenticate(user=user)

        r = self.client.post(url, payload, format="json")
        self.assertEqual(r.status_code, 403)
        bulk_task.assert_not_called()

        user.role.can_lock_agents = True
        user.role.save()

        r = self.client.post(url, payload, format="json")
        self.assertEqual(r.status_code, 200)
        bulk_task.assert_called_once()
