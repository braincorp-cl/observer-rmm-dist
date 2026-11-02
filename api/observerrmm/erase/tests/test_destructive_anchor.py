"""El expediente que autoriza una orden (feature 053 · RF-12 · CA-09).

Antes de esta feature la guardia no existía en el servidor para el camino
destructivo: `WipeOrderCreate` aceptaba `lost_mode_cycle` del payload y no
validaba nada, así que la convención «se ordena desde el caso, nunca desde el
listado general» la sostenía solo la consola. Acá se verifica que la decisión es
del servidor y que son DOS los expedientes válidos, ambos gobernados: un caso de
equipo perdido abierto o un acta de ingreso a baja.

El control positivo que importa es `test_caso_abierto_sin_evidencia_pasa`: un
equipo recién denunciado no tiene ninguna captura de evidencia, así que su ciclo
es `None`. Si la guardia se hubiera atado a `lost_mode_cycle` —lo que el nombre
del campo invita a hacer— ese equipo, el más urgente de todos, sería justo el que
no podría ordenar nada.
"""

from unittest.mock import patch

from model_bakery import baker

from agents.models import LostModeEvidence, LostModeState
from erase.models import AssetIntake, FileRetrievalOrder, WipeOrder
from observerrmm.test import ObserverTestCase

# El equipo no existe: el despacho best-effort de fileretrieval deja la orden en
# cola, que es lo que estos tests quieren (importa el ancla, no el transporte).
_SIN_AGENTE = object()


async def _nats_caido(*a, **k):
    return "natsdown"


class DestructiveAnchorTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()  # john/alice superuser
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-ANCLA", agent_id="aid-ancla"
        )

    # --- utilidades -----------------------------------------------------
    def _abrir_caso(self, active=True):
        return LostModeState.objects.create(
            agent=self.agent, active=active, reason="robado"
        )

    def _acta(self, process_id="PROC-1", agent=_SIN_AGENTE):
        return AssetIntake.objects.create(
            process_id=process_id,
            client=self.client_obj,
            site=self.site,
            agent=self.agent if agent is _SIN_AGENTE else agent,
            received_by="bodega",
            equipment_serial="SN-ANCLA",
        )

    def _ordenar_wipe(self, **body):
        # 🪤 La acción NO puede ser `crypto_erase`: desde la feature 055 la vista
        # la rechaza con 409 ANTES de mirar el expediente (RF-10). Con ella, los
        # casos que esperan 201 fallarían y —peor— los que esperan 409 pasarían
        # por la razón equivocada, verificando un bloqueo distinto del que este
        # archivo existe para probar.
        payload = {"action": "fullwipe", "reason": "baja del activo"}
        payload.update(body)
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/orders/", payload, format="json"
        )

    def _ordenar_rescate(self, **body):
        payload = {"paths": ["C:/Users/x/informe.docx"]}
        payload.update(body)
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/fileretrieval/",
            payload,
            format="json",
        )

    # --- sin expediente -------------------------------------------------
    def test_sin_expediente_no_crea_nada(self):
        antes = WipeOrder.objects.count()
        r = self._ordenar_wipe()
        self.assertEqual(r.status_code, 409)
        # Delta y no conteo absoluto: con pytest-randomly el orden cambia.
        self.assertEqual(WipeOrder.objects.count() - antes, 0)

    def test_caso_cerrado_no_alcanza(self):
        """El caso fino: la fila de LostModeState existe, el caso NO está abierto.

        `LostModeState` sobrevive al cierre del caso por diseño (guarda la
        configuración del equipo), así que un `filter(agent=agent)` sin
        `active=True` sería una no-guardia: dejaría pasar a cualquier equipo que
        alguna vez estuvo perdido.
        """
        self._abrir_caso(active=False)
        antes = WipeOrder.objects.count()
        r = self._ordenar_wipe()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(WipeOrder.objects.count() - antes, 0)

    def test_con_permiso_pero_sin_expediente_es_409_no_403(self):
        """La guardia es independiente del permiso: john tiene can_wipe_device."""
        r = self._ordenar_wipe()
        self.assertEqual(r.status_code, 409)

    # --- caso perdido abierto -------------------------------------------
    def test_caso_abierto_sin_evidencia_pasa(self):
        """CA-09: equipo recién denunciado, cero capturas ⇒ ciclo None, no 0."""
        self._abrir_caso()
        r = self._ordenar_wipe()
        self.assertEqual(r.status_code, 201)
        order = WipeOrder.objects.get(pk=r.json()["id"])
        self.assertIsNone(order.lost_mode_cycle)
        self.assertIsNone(order.intake_id)

    def test_ciclo_lo_deriva_el_servidor_y_no_el_payload(self):
        self._abrir_caso()
        LostModeEvidence.objects.create(agent=self.agent, cycle=3)
        r = self._ordenar_wipe(lost_mode_cycle=99)
        self.assertEqual(r.status_code, 201)
        order = WipeOrder.objects.get(pk=r.json()["id"])
        self.assertEqual(order.lost_mode_cycle, 3)

    # --- acta de ingreso -------------------------------------------------
    def test_solo_acta_sin_caso_pasa(self):
        """Lo que desbloquea T023/T024 de la 043: un equipo de descarte se borra
        sin tener que mentir marcándolo como perdido."""
        acta = self._acta()
        r = self._ordenar_wipe()
        self.assertEqual(r.status_code, 201)
        order = WipeOrder.objects.get(pk=r.json()["id"])
        self.assertEqual(order.intake_id, acta.pk)
        self.assertIsNone(order.lost_mode_cycle)

    def test_queda_atada_al_acta_mas_reciente_y_no_se_mueve(self):
        """La FK congela el expediente: un acta posterior NO se adueña de la orden."""
        self._acta(process_id="PROC-VIEJA")
        reciente = self._acta(process_id="PROC-RECIENTE")
        order = WipeOrder.objects.get(pk=self._ordenar_wipe().json()["id"])
        self.assertEqual(order.intake_id, reciente.pk)

        self._acta(process_id="PROC-POSTERIOR")
        order.refresh_from_db()
        self.assertEqual(order.intake_id, reciente.pk)

    def test_caso_abierto_le_gana_al_acta(self):
        self._abrir_caso()
        self._acta()
        order = WipeOrder.objects.get(pk=self._ordenar_wipe().json()["id"])
        self.assertIsNone(order.intake_id)

    def test_acta_de_otro_equipo_no_sirve(self):
        """El acta ancla al equipo que nombra, no al cliente."""
        otro = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-OTRO", agent_id="aid-otro"
        )
        self._acta(agent=otro)
        self.assertEqual(self._ordenar_wipe().status_code, 409)

    def test_acta_sin_equipo_no_ancla(self):
        """Un disco suelto se ingresa sin agente; esa acta no autoriza órdenes
        sobre ningún equipo enrolado."""
        self._acta(agent=None)
        self.assertEqual(self._ordenar_wipe().status_code, 409)

    # --- el camino no destructivo usa el MISMO ancla ---------------------
    @patch("agents.models.Agent.nats_cmd", _nats_caido)
    def test_rescate_por_acta_ahora_pasa(self):
        """Antes de la 053 esto daba 409: fileretrieval solo aceptaba caso perdido."""
        acta = self._acta()
        r = self._ordenar_rescate()
        self.assertEqual(r.status_code, 201)
        order = FileRetrievalOrder.objects.get(pk=r.json()["id"])
        self.assertEqual(order.intake_id, acta.pk)

    @patch("agents.models.Agent.nats_cmd", _nats_caido)
    def test_rescate_sin_expediente_sigue_en_409(self):
        antes = FileRetrievalOrder.objects.count()
        self.assertEqual(self._ordenar_rescate().status_code, 409)
        self.assertEqual(FileRetrievalOrder.objects.count() - antes, 0)

    @patch("agents.models.Agent.nats_cmd", _nats_caido)
    def test_rescate_con_caso_sin_evidencia_no_inventa_ciclo_cero(self):
        """El bloque inline que se reemplazó coaccionaba el ciclo a 0."""
        self._abrir_caso()
        r = self._ordenar_rescate()
        self.assertEqual(r.status_code, 201)
        order = FileRetrievalOrder.objects.get(pk=r.json()["id"])
        self.assertIsNone(order.lost_mode_cycle)


class CryptoEraseNoSeOfreceTests(ObserverTestCase):
    """Feature 055 · RF-10 — una promesa que no se puede cumplir se retira.

    `crypto_erase` está en el enum desde la feature 039 y nunca tuvo
    implementación posible. Se midió en staging el 2026-11-01 que la vía
    aparente —quitar los protectores del cifrado del sistema operativo— deja la
    clave maestra del volumen EN CLARO y el dato legible: no sólo no borra,
    empeora la seguridad del equipo.

    Se bloquea en la puerta HTTP y NO retirando el valor del enum: hay órdenes
    históricas que lo referencian, y una columna no puede dejar de admitir lo
    que ya guardó.
    """

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent", site=self.site, hostname="BOX-CE", agent_id="aid-ce"
        )
        LostModeState.objects.create(agent=self.agent, active=True, reason="robado")

    def _ordenar(self, action):
        return self.client.post(
            f"/erase/agents/{self.agent.agent_id}/orders/",
            {"action": action, "reason": "baja del activo"},
            format="json",
        )

    def test_crypto_erase_se_rechaza_con_motivo_y_no_crea_orden(self):
        antes = WipeOrder.objects.count()

        r = self._ordenar("crypto_erase")

        self.assertEqual(r.status_code, 409)
        self.assertIn("crypto-erase", r.data["detail"].lower())
        self.assertEqual(WipeOrder.objects.count(), antes)

    def test_el_rechazo_gana_aunque_el_expediente_este_en_regla(self):
        """El bloqueo no es un efecto secundario de otra guarda.

        Este equipo tiene caso abierto, así que la guardia de expediente lo
        dejaría pasar. Si el 409 desapareciera al arreglar el expediente, el
        bloqueo estaría colgando de la guarda equivocada.
        """
        r = self._ordenar("crypto_erase")
        self.assertEqual(r.status_code, 409)
        self.assertNotIn("expediente", r.data["detail"].lower())

    def test_las_demas_acciones_destructivas_siguen_pasando(self):
        """🔑 El control que impide que el bloqueo se lleve puesto al resto."""
        r = self._ordenar("fullwipe")
        self.assertEqual(r.status_code, 201)
