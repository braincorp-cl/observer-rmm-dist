"""Los dos contratos HTTP de la ola 2: custodia y reconciliación.

Feature 053 · ola 2 · RF-06, RF-07 y CA-07. Lo que más se cuida acá es que los
dos sean **autenticados y recortados por rol**: enumerar la custodia o las bajas
de un cliente es exactamente lo que L-02 prohibió para el verificador público.
"""

from datetime import timedelta

from django.utils import timezone
from model_bakery import baker

from accounts.models import Role, User
from erase.models import AssetIntake, CustodyEvent, CustodyEventKind, EraseCertificate
from observerrmm.test import ObserverTestCase


class CustodyApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="Cliente API")
        self.site = baker.make("clients.Site", client=self.client_obj)

    def _crear_acta(self, serial="SN-API-1"):
        return self.client.post(
            "/erase/intake/",
            {
                "client": self.client_obj.pk,
                "site": self.site.pk,
                "equipment_serial": serial,
                "delivered_by": "usuario final",
                "media_type": "ssd",
                "state": "functional",
            },
            format="json",
        )

    # --- el acta nace con su eslabon ---

    def test_crear_un_acta_escribe_el_primer_eslabon(self):
        r = self._crear_acta()
        self.assertEqual(r.status_code, 201)
        intake = AssetIntake.objects.get(pk=r.json()["id"])

        eventos = CustodyEvent.objects.filter(intake=intake)
        self.assertEqual(eventos.count(), 1)
        ev = eventos.get()
        self.assertEqual(ev.kind, CustodyEventKind.RECEIVED)
        self.assertEqual(ev.actor, self.john.username)
        # Identidad congelada: el eslabon sobrevive al acta.
        self.assertEqual(ev.intake_process_id, intake.process_id)
        self.assertEqual(ev.equipment_serial, "SN-API-1")

    def test_el_tipo_de_medio_se_guarda(self):
        r = self._crear_acta()
        self.assertEqual(AssetIntake.objects.get(pk=r.json()["id"]).media_type, "ssd")

    # --- GET de la linea de tiempo ---

    def test_no_autenticado(self):
        self.check_not_authenticated("get", "/erase/reconciliation/")

    def test_linea_de_tiempo_en_orden_de_cadena(self):
        pk = self._crear_acta().json()["id"]
        for kind in ("relocated", "handed_to_processor"):
            self.client.post(
                f"/erase/intake/{pk}/custody/", {"kind": kind}, format="json"
            )

        r = self.client.get(f"/erase/intake/{pk}/custody/")
        self.assertEqual(r.status_code, 200)
        cuerpo = r.json()
        self.assertTrue(cuerpo["chain_intact"])
        self.assertEqual(
            [e["kind"] for e in cuerpo["events"]],
            ["received", "relocated", "handed_to_processor"],
        )
        # La etiqueta viaja resuelta: la consola no mapea tokens.
        self.assertEqual(cuerpo["events"][0]["kind_label"], "Recibido en custodia")

    # --- POST: lo que el contrato rechaza ---

    def test_un_kind_desconocido_es_400(self):
        pk = self._crear_acta().json()["id"]
        r = self.client.post(
            f"/erase/intake/{pk}/custody/", {"kind": "teletransportado"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_una_fecha_futura_es_409(self):
        pk = self._crear_acta().json()["id"]
        futuro = (timezone.now() + timedelta(days=1)).isoformat()
        r = self.client.post(
            f"/erase/intake/{pk}/custody/",
            {"kind": "relocated", "at": futuro},
            format="json",
        )
        self.assertEqual(r.status_code, 409)

    def test_un_segundo_received_es_409(self):
        pk = self._crear_acta().json()["id"]
        r = self.client.post(
            f"/erase/intake/{pk}/custody/", {"kind": "received"}, format="json"
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(CustodyEvent.objects.filter(kind="received").count(), 1)

    def test_el_actor_no_se_acepta_del_cliente(self):
        """Firmar un traslado a nombre de otro no debe ser posible."""
        pk = self._crear_acta().json()["id"]
        r = self.client.post(
            f"/erase/intake/{pk}/custody/",
            {"kind": "relocated", "actor": "otra-persona"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["actor"], self.john.username)

    def test_el_eslabon_no_se_edita_ni_se_borra(self):
        pk = self._crear_acta().json()["id"]
        for metodo in ("put", "patch", "delete"):
            r = getattr(self.client, metodo)(f"/erase/intake/{pk}/custody/")
            self.assertEqual(r.status_code, 405, metodo)


class ReconciliationApiTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.uno = baker.make("clients.Client", name="Alfa")
        self.dos = baker.make("clients.Client", name="Beta")

    def _acta(self, client, serial, **kw):
        return AssetIntake.objects.create(
            process_id=f"OE-IN-{serial}",
            client=client,
            equipment_serial=serial,
            received_by="bodega",
            **kw,
        )

    def _certificar(self, intake):
        return EraseCertificate.objects.create(
            certificate_id=f"CERT-{intake.equipment_serial}",
            kind="physical_destruction",
            client=intake.client,
            intake=intake,
            data={"x": 1},
            document_hash="b" * 64,
        )

    def test_cuenta_ingresados_certificados_y_faltantes(self):
        uno = self._acta(self.uno, "SN-1")
        self._acta(self.uno, "SN-2")
        self._certificar(uno)

        r = self.client.get("/erase/reconciliation/")
        self.assertEqual(r.status_code, 200)
        totales = r.json()["totals"]
        self.assertEqual(totales["intakes"], 2)
        self.assertEqual(totales["certified"], 1)
        self.assertEqual(totales["missing"], 1)

    def test_faltante_es_sin_certificado_no_acta_vieja(self):
        """Un acta de hoy sin certificar YA es faltante (CA-07)."""
        self._acta(self.uno, "SN-HOY")
        r = self.client.get("/erase/reconciliation/")
        faltantes = r.json()["missing_items"]
        self.assertEqual(len(faltantes), 1)
        self.assertEqual(faltantes[0]["process_id"], "OE-IN-SN-HOY")
        # Sin umbral, nadie esta "detenido": detenido es otra cosa que faltante.
        self.assertFalse(faltantes[0]["stalled"])

    def test_el_ultimo_eslabon_dice_donde_se_detuvo(self):
        acta = self._acta(self.uno, "SN-PARADO")
        CustodyEvent.objects.create(
            intake=acta,
            intake_process_id=acta.process_id,
            equipment_serial=acta.equipment_serial,
            kind=CustodyEventKind.HANDED_TO_PROCESSOR,
            at=timezone.now(),
            actor="bodega",
        )
        r = self.client.get("/erase/reconciliation/")
        item = r.json()["missing_items"][0]
        self.assertEqual(item["last_event"]["kind"], "handed_to_processor")

    def test_certificar_saca_el_activo_de_faltantes(self):
        acta = self._acta(self.uno, "SN-CERT")
        self.assertEqual(
            self.client.get("/erase/reconciliation/").json()["totals"]["missing"], 1
        )
        self._certificar(acta)
        self.assertEqual(
            self.client.get("/erase/reconciliation/").json()["totals"]["missing"], 0
        )

    def test_from_posterior_a_to_es_400(self):
        r = self.client.get("/erase/reconciliation/?from=2026-09-30&to=2026-07-01")
        self.assertEqual(r.status_code, 400)

    def test_una_fecha_ilegible_es_400(self):
        """Un filtro que se ignora en silencio daria un informe que no es el
        pedido."""
        r = self.client.get("/erase/reconciliation/?from=ayer")
        self.assertEqual(r.status_code, 400)

    def test_el_alcance_de_rol_recorta_y_los_totales_cuadran(self):
        self._acta(self.uno, "SN-ALFA")
        self._acta(self.dos, "SN-BETA")

        role = Role.objects.create(name="solo-alfa", can_view_erase_certificates=True)
        role.can_view_clients.set([self.uno])
        u = User.objects.create_user(username="limitado", password="x")
        u.role = role
        u.save()
        self.client.force_authenticate(user=u)

        cuerpo = self.client.get("/erase/reconciliation/").json()
        self.assertEqual(cuerpo["totals"]["intakes"], 1)
        self.assertEqual([f["client"] for f in cuerpo["by_client"]], ["Alfa"])
        self.assertEqual(
            [f["process_id"] for f in cuerpo["missing_items"]], ["OE-IN-SN-ALFA"]
        )

    def test_los_faltantes_vienen_paginados(self):
        """El contrato prometía paginar y la primera versión devolvía todo.

        Con tres actas da lo mismo, que es justo por lo que no se notó: hay que
        sembrar más que la página para que la diferencia exista.
        """
        for n in range(7):
            self._acta(self.uno, f"SN-PAG-{n:02d}")

        r = self.client.get("/erase/reconciliation/?limit=3")
        cuerpo = r.json()
        self.assertEqual(len(cuerpo["missing_items"]), 3)
        self.assertEqual(cuerpo["missing_page"]["total"], 7)
        self.assertEqual(cuerpo["missing_page"]["limit"], 3)
        self.assertEqual(cuerpo["missing_page"]["returned"], 3)
        # 🔑 El total NO es el tamaño de la página: es lo que la consola necesita
        # para saber que hay más.
        self.assertEqual(cuerpo["totals"]["missing"], 7)

    def test_la_segunda_pagina_no_repite_ni_salta(self):
        for n in range(7):
            self._acta(self.uno, f"SN-PAG-{n:02d}")

        una = self.client.get("/erase/reconciliation/?limit=3&offset=0").json()
        dos = self.client.get("/erase/reconciliation/?limit=3&offset=3").json()
        tres = self.client.get("/erase/reconciliation/?limit=3&offset=6").json()

        ids = [i["intake_id"] for i in una["missing_items"] + dos["missing_items"]]
        self.assertEqual(len(set(ids)), 6, "las páginas se solapan")
        self.assertEqual(len(tres["missing_items"]), 1)
        todos = ids + [i["intake_id"] for i in tres["missing_items"]]
        self.assertEqual(len(set(todos)), 7, "falta algún faltante entre páginas")

    def test_el_limite_tiene_tope(self):
        """Un `limit` enorme no es una forma de pedir todo."""
        self._acta(self.uno, "SN-TOPE")
        r = self.client.get("/erase/reconciliation/?limit=99999")
        self.assertEqual(r.json()["missing_page"]["limit"], 500)

    def test_los_totales_no_dependen_de_la_pagina(self):
        """Control: paginar cuenta lo mismo que no paginar."""
        for n in range(5):
            self._acta(self.uno, f"SN-TOT-{n:02d}")
        completo = self.client.get("/erase/reconciliation/").json()["totals"]
        pagina = self.client.get("/erase/reconciliation/?limit=2").json()["totals"]
        self.assertEqual(completo, pagina)
