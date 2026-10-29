"""La retención del adjunto se resuelve en UN lugar y su piso no se puede bajar.

Feature 053 · ola 3 · RNF-06 / L-04. El certificado es **permanente**; lo que
caduca es el adjunto, y su plazo lo fija el cliente sobre un piso legal.

Dos cosas se cuidan acá por encima del resto:

1. **La precedencia vive en un solo lugar** (`resolve_attachment_retention`). Si
   se resolviera en dos, la consola mostraría un número y la purga aplicaría otro,
   y la diferencia sólo se descubriría cuando faltara un archivo.
2. **El piso se aplica al leer, no sólo al guardar.** El validador del campo cubre
   el formulario y la API; no cubre un `loaddata`, un `queryset.update()` ni una
   fila escrita antes de que el validador existiera. Un piso que se puede esquivar
   no es un piso, así que hay un control por cada vía.
"""

from clients.models import Client
from core.utils import get_core_settings
from erase.services import resolve_attachment_retention
from model_bakery import baker
from observerrmm.constants import ERASE_ATTACHMENT_RETENTION_FLOOR_DAYS as PISO
from observerrmm.test import ObserverTestCase


class _Base(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.cliente = baker.make("clients.Client", name="Cliente Retencion")

    def _global(self, dias):
        core = get_core_settings()
        core.erase_attachment_retention_days = dias
        core.save()
        return core


class PrecedenciaTests(_Base):
    def test_nulo_hereda_el_global(self):
        self._global(500)
        self.assertIsNone(self.cliente.erase_attachment_retention_days)
        self.assertEqual(resolve_attachment_retention(client=self.cliente), 500)

    def test_el_valor_del_cliente_pisa_al_global(self):
        self._global(500)
        self.cliente.erase_attachment_retention_days = 730
        self.cliente.save()
        self.assertEqual(resolve_attachment_retention(client=self.cliente), 730)

    def test_subirlo_es_libre(self):
        self._global(PISO)
        self.cliente.erase_attachment_retention_days = 1825
        self.cliente.save()
        self.assertEqual(resolve_attachment_retention(client=self.cliente), 1825)

    def test_sin_cliente_devuelve_el_global(self):
        self._global(500)
        self.assertEqual(resolve_attachment_retention(), 500)

    def test_vaciarlo_vuelve_a_heredar_y_no_es_cero_dias(self):
        """El nulo es «sin decidir». Si se leyera como 0, purgaría TODO."""
        self._global(500)
        self.cliente.erase_attachment_retention_days = 730
        self.cliente.save()
        self.cliente.erase_attachment_retention_days = None
        self.cliente.save()
        self.assertEqual(resolve_attachment_retention(client=self.cliente), 500)


class PisoTests(_Base):
    def test_el_validador_rechaza_por_debajo_del_piso(self):
        from django.core.exceptions import ValidationError

        self.cliente.erase_attachment_retention_days = 30
        with self.assertRaises(ValidationError):
            self.cliente.full_clean()

    def test_el_piso_se_aplica_al_leer_aunque_el_orm_esquive_el_validador(self):
        """🔑 El control que importa: `update()` NO pasa por el validador."""
        self._global(PISO)
        Client.objects.filter(pk=self.cliente.pk).update(
            erase_attachment_retention_days=30
        )
        self.cliente.refresh_from_db()
        # La fila quedó en 30 —el ORM no valida— y aun así la lectura da el piso.
        self.assertEqual(self.cliente.erase_attachment_retention_days, 30)
        self.assertEqual(resolve_attachment_retention(client=self.cliente), PISO)

    def test_el_piso_corrige_un_global_por_debajo(self):
        """🪤 El `default` desplegado del campo global es 365, y el piso 366.

        Un día de diferencia que estaba en el código sin razón documentada. El
        global NO se movió (es un valor ya desplegado en instancias vivas); se
        corrige al leer, que es donde la obligación legal se vuelve efectiva.
        """
        self._global(365)
        self.assertEqual(resolve_attachment_retention(), 366)
        self.assertEqual(resolve_attachment_retention(client=self.cliente), 366)


class ContratoHTTPTests(_Base):
    """`interfaces/retention.md`: el campo viaja por `PUT /clients/{pk}/`."""

    def _put(self, payload):
        return self.client.put(
            f"/clients/{self.cliente.pk}/", {"client": payload}, format="json"
        )

    def test_guarda_y_devuelve_el_campo(self):
        r = self._put(
            {"name": self.cliente.name, "erase_attachment_retention_days": 730}
        )
        self.assertIn(r.status_code, (200, 201))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.erase_attachment_retention_days, 730)

        g = self.client.get(f"/clients/{self.cliente.pk}/")
        self.assertEqual(g.status_code, 200)
        # 🪤 Si el campo no estuviera en la tupla `fields` de ClientSerializer,
        # el PUT de arriba habría respondido 200 y descartado el valor en
        # silencio. Este GET es lo que lo destapa.
        self.assertEqual(g.json()["erase_attachment_retention_days"], 730)

    def test_por_debajo_del_piso_da_400(self):
        r = self._put(
            {"name": self.cliente.name, "erase_attachment_retention_days": 30}
        )
        self.assertEqual(r.status_code, 400)
        self.cliente.refresh_from_db()
        self.assertIsNone(self.cliente.erase_attachment_retention_days)

    def test_null_explicito_vuelve_a_heredar(self):
        self.cliente.erase_attachment_retention_days = 730
        self.cliente.save()
        r = self._put(
            {"name": self.cliente.name, "erase_attachment_retention_days": None}
        )
        self.assertIn(r.status_code, (200, 201))
        self.cliente.refresh_from_db()
        self.assertIsNone(self.cliente.erase_attachment_retention_days)

    def test_omitirlo_lo_deja_intacto(self):
        """`partial=True` en la vista: la ausencia es «sin cambio», no `null`."""
        self.cliente.erase_attachment_retention_days = 730
        self.cliente.save()
        r = self._put({"name": self.cliente.name})
        self.assertIn(r.status_code, (200, 201))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.erase_attachment_retention_days, 730)
