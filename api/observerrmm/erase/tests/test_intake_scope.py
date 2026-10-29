"""El acta no puede nacer con un cliente que no es el del equipo.

`AssetIntakeSerializer` usa `fields = "__all__"` sobre tres FKs independientes
(`client`, `site`, `agent`), así que nada en el modelo impide grabar un acta del
equipo de un cliente a nombre de otro. Y eso no es un dato cosmético:
`EraseQuerySet.filter_by_role` recorta por `client`/`site`, de modo que un acta
con el cliente equivocado queda **visible para quien no debería verla**.

El control positivo del final es la mitad importante del archivo: sin `agent` no
se valida nada, porque un disco suelto tiene que poder ingresarse igual.
"""

from model_bakery import baker

from erase.models import AssetIntake
from observerrmm.test import ObserverTestCase


class IntakeScopeTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

        # Dos clientes con un sitio cada uno. El equipo vive en el primero.
        self.cliente = baker.make("clients.Client", name="Cliente Propio")
        self.sitio = baker.make("clients.Site", client=self.cliente)
        self.cliente_ajeno = baker.make("clients.Client", name="Cliente Ajeno")
        self.sitio_ajeno = baker.make("clients.Site", client=self.cliente_ajeno)

        self.agent = baker.make(
            "agents.Agent",
            site=self.sitio,
            hostname="BOX-ALCANCE",
            agent_id="aid-alcance",
        )

    def _post(self, **extra):
        cuerpo = {"equipment_serial": "SN-ALCANCE", "state": "functional"}
        cuerpo.update(extra)
        return self.client.post("/erase/intake/", cuerpo, format="json")

    # --- el caso correcto sigue pasando ---

    def test_el_acta_del_equipo_con_su_propio_cliente_se_crea(self):
        antes = AssetIntake.objects.count()
        r = self._post(agent=self.agent.pk, client=self.cliente.pk, site=self.sitio.pk)

        self.assertEqual(r.status_code, 201)
        self.assertEqual(AssetIntake.objects.count() - antes, 1)

        acta = AssetIntake.objects.get(pk=r.json()["id"])
        self.assertEqual(acta.agent_id, self.agent.pk)
        self.assertEqual(acta.client_id, self.cliente.pk)

    def test_el_acta_del_equipo_sin_site_se_crea(self):
        # `site` es opcional en el modelo: si no viene, no hay nada que comparar.
        antes = AssetIntake.objects.count()
        r = self._post(agent=self.agent.pk, client=self.cliente.pk)

        self.assertEqual(r.status_code, 201)
        self.assertEqual(AssetIntake.objects.count() - antes, 1)

    # --- cliente o sitio ajenos: 400, no 403 ---

    def test_cliente_ajeno_es_400(self):
        antes = AssetIntake.objects.count()
        r = self._post(
            agent=self.agent.pk,
            client=self.cliente_ajeno.pk,
            site=self.sitio.pk,
        )

        # 400 y no 403: el rol del usuario no tiene nada que ver, el cuerpo es
        # incoherente consigo mismo.
        self.assertEqual(r.status_code, 400)
        self.assertIn("client", r.json())
        self.assertEqual(AssetIntake.objects.count() - antes, 0)

    def test_sitio_ajeno_es_400(self):
        antes = AssetIntake.objects.count()
        r = self._post(
            agent=self.agent.pk,
            client=self.cliente.pk,
            site=self.sitio_ajeno.pk,
        )

        self.assertEqual(r.status_code, 400)
        self.assertIn("site", r.json())
        self.assertEqual(AssetIntake.objects.count() - antes, 0)

    def test_sitio_del_mismo_cliente_pero_de_otro_equipo_es_400(self):
        # Mismo cliente, otro sitio: el `client` calza y el `site` no. Si sólo se
        # comparara el cliente, esto pasaría.
        otro_sitio = baker.make("clients.Site", client=self.cliente)
        r = self._post(agent=self.agent.pk, client=self.cliente.pk, site=otro_sitio.pk)

        self.assertEqual(r.status_code, 400)
        self.assertIn("site", r.json())

    # --- control positivo: sin equipo no se valida nada ---

    def test_sin_agent_el_disco_suelto_se_ingresa_igual(self):
        antes = AssetIntake.objects.count()
        r = self._post(client=self.cliente_ajeno.pk, site=self.sitio_ajeno.pk)

        # Es el caso que NO debe romperse: un disco suelto no cuelga de ningún
        # equipo enrolado y no hay con qué contrastar su cliente.
        self.assertEqual(r.status_code, 201)
        self.assertEqual(AssetIntake.objects.count() - antes, 1)

        acta = AssetIntake.objects.get(pk=r.json()["id"])
        self.assertIsNone(acta.agent_id)
        self.assertEqual(acta.client_id, self.cliente_ajeno.pk)

    def test_sin_agent_ni_site_se_ingresa_igual(self):
        antes = AssetIntake.objects.count()
        r = self._post(client=self.cliente.pk)

        self.assertEqual(r.status_code, 201)
        self.assertEqual(AssetIntake.objects.count() - antes, 1)
