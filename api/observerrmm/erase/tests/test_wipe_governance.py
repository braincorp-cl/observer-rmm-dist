"""Tests de gobernanza y API HTTP del verbo wipe (feature 043 · A2).

Cubre el camino de producción por endpoints: gating server-side por
`can_wipe_device` (RF-04), doble confirmación de dos personas (RF-G02), tope por
orden (RF-07) y la materialización de rutas plantilla + ajustes (RN-07).
"""

from django.test import override_settings
from model_bakery import baker

from accounts.models import Role, User
from erase.models import WipeOrder, WipeOrderStatus, WipePathTemplate
from observerrmm.test import ObserverTestCase


class WipeGovernanceApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()  # john/alice superuser (distinto username)
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-WIPE", agent_id="aid-wipe"
        )

    def _crear(self, **body):
        payload = {
            "action": "wipe",
            "reason": "equipo robado",
            "paths_add": ["C:/Users/x/Documents/secreto.pdf"],
        }
        payload.update(body)
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/orders/",
            payload,
            format="json",
        )

    def test_no_autenticado(self):
        self.check_not_authenticated("get", "/erase/orders/")

    def test_permiso_dedicado_can_wipe_device(self):
        """Un rol sin can_wipe_device NO puede crear una orden de wipe (403)."""
        role = Role.objects.create(name="solo-perdido", can_manage_lost_mode=True)
        u = User.objects.create_user(username="operador", password="x")
        u.role = role
        u.save()
        self.client.force_authenticate(user=u)
        r = self._crear()
        self.assertEqual(r.status_code, 403)

    def test_rutas_plantilla_mas_ajustes(self):
        tpl = WipePathTemplate.objects.create(
            name="Perfil",
            client=self.client_obj,
            paths=["C:/Users/x/Documents", "C:/Users/x/Desktop"],
        )
        r = self._crear(
            template=tpl.pk,
            paths_add=["D:/proyecto"],
            paths_remove=["C:/Users/x/Desktop"],
        )
        self.assertEqual(r.status_code, 201)
        order = WipeOrder.objects.get(pk=r.json()["id"])
        self.assertEqual(
            order.scope["paths"],
            ["C:/Users/x/Documents", "D:/proyecto"],
        )

    @override_settings(WIPE_MAX_PATHS_PER_ORDER=1)
    def test_tope_excedido(self):
        r = self._crear(paths_add=["/a", "/b"])
        self.assertEqual(r.status_code, 422)

    def test_flujo_dos_personas(self):
        order_id = self._crear().json()["id"]
        # john (ordenante) NO puede autoconfirmar → 409
        r_self = self.client.post(
            f"/erase/orders/{order_id}/confirm/",
            {"recovery_seconds": 60},
            format="json",
        )
        self.assertEqual(r_self.status_code, 409)
        # alice (segunda persona) sí confirma → ventana
        self.client.force_authenticate(user=self.alice)
        r_ok = self.client.post(
            f"/erase/orders/{order_id}/confirm/",
            {"recovery_seconds": 60},
            format="json",
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.json()["status"], WipeOrderStatus.RECOVERY_WINDOW)
