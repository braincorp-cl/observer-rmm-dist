"""El portal público de verificación de certificados (053 · ola 4 · RF-08/RNF-03/CA-08).

Lo que este archivo cuida no es que el endpoint funcione —eso es fácil—, es que
**no diga de más**. El portal es la única ruta de consulta sin autenticación del
producto, abierta en instalaciones de producción, y el daño posible no es que
alguien verifique un certificado ajeno: es que alguien **enumere** identificadores
y arme el inventario de bajas de un cliente.

De ahí las dos propiedades que estos tests fijan y que una revisión futura va a
querer «mejorar»:

1. **El conjunto de claves es cerrado** (`L-02`). Nadie va a agregar el número de
   serie a propósito; lo va a agregar porque «da contexto al que verifica».
2. **No hay 404 ni 400 por el identificador** (`CA-08`). Dos códigos de estado
   distintos son un oráculo de existencia: con él se barre el espacio contando
   respuestas, sin leer un solo cuerpo.

🔑 El límite de tasa NO es la defensa principal. Lo son los 40 bits de
`new_certificate_id()` y el hecho de que acertar uno no diga de quién es.
"""

import hashlib

from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from model_bakery import baker

from erase import certificate as cert_mod
from erase.models import CertificateKind, EraseCertificate
from observerrmm.test import ObserverTestCase
from observerrmm.throttles import VerifyDayThrottle, VerifyMinThrottle

URL = "/erase/verify/{}/"

# El contrato de L-02, literal. Comparación de CONJUNTOS: una clave de más hace
# fallar el test, que es el punto entero.
CLAVES = {
    "found",
    "certificate_id",
    "kind",
    "issued_at",
    "document_intact",
    "signature_valid",
    "signature_present",
    "chain_intact",
    "valid",
}

# Lo que NUNCA puede aparecer, aunque alguien lo agregue «para dar contexto».
PROHIBIDAS = {
    "data",
    "document",
    "document_hash",
    "record_hash",
    "prev_hash",
    "client",
    "client_id",
    "tenant",
    "agent",
    "agent_id",
    "serial",
    "equipment",
    "equipment_serial",
    "asset_tag",
    "operator",
    "concurrence",
    "ticket_ref",
    "site",
    "method_applied",
    "detail",
    "reason",
}


class _Base(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="Cliente X")
        self._encender()
        # El throttle cuenta por IP en la caché del proceso: sin esto, una clase
        # anterior puede dejar el contador arriba y teñir de 429 lo que no es.
        cache.clear()

    def _encender(self, valor: bool = True) -> None:
        # save() invalida CORESETTINGS_CACHE_KEY (core/models.py:364), así que la
        # vista lee el valor nuevo y no el cacheado.
        self.coresettings.erase_public_verify_enabled = valor
        self.coresettings.save()

    def _emitir(self, **kw) -> EraseCertificate:
        return cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=self.client_obj,
            tenant="Cliente X",
            operator="john",
            **kw,
        )

    def _get(self, certificate_id: str):
        self.client.logout()
        return self.client.get(URL.format(certificate_id))


class ContratoMinimoTests(_Base):
    """T072 — el conjunto de claves es exactamente el de L-02, ni una más."""

    def test_la_respuesta_tiene_exactamente_las_claves_del_contrato(self):
        cert = self._emitir()
        r = self._get(cert.certificate_id)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        print("\n  claves =", sorted(d))
        # Conjuntos, no assertIn: una clave de más TIENE que hacer fallar esto.
        self.assertEqual(set(d), CLAVES)

    def test_no_viaja_nada_que_permita_armar_el_inventario_de_bajas(self):
        """Control explícito, por si el conjunto se relaja en una revisión."""
        cert = self._emitir(asset_tag="ACT-1", ticket_ref="T-1")
        d = self._get(cert.certificate_id).json()
        filtradas = PROHIBIDAS & set(d)
        self.assertEqual(filtradas, set(), f"el portal filtró: {filtradas}")
        # Tampoco en los valores: el nombre del cliente no aparece en ningún lado.
        self.assertNotIn("Cliente X", str(d))
        self.assertNotIn("john", str(d))

    def test_el_identificador_que_vuelve_es_el_que_se_pidio(self):
        cert = self._emitir()
        d = self._get(cert.certificate_id).json()
        self.assertEqual(d["certificate_id"], cert.certificate_id)
        self.assertEqual(d["kind"], cert.kind)
        self.assertTrue(d["issued_at"])


class SinOraculoTests(_Base):
    """T073 — inexistente y formato inválido son INDISTINGUIBLES de un válido.

    🔴 Este es el test que una refactorización va a romper sin querer: devolver
    404 cuando no existe es lo natural en REST, y acá es exactamente la fuga.
    """

    def test_un_identificador_inexistente_responde_200_con_las_mismas_claves(self):
        r = self._get("OE-20261029-NOEXISTE1")
        print("  inexistente ->", r.status_code, sorted(r.json()))
        self.assertEqual(
            r.status_code,
            200,
            "un 404 convierte el endpoint en un oráculo de existencia: "
            "permite barrer el espacio de identificadores contando respuestas",
        )
        self.assertEqual(set(r.json()), CLAVES)
        self.assertFalse(r.json()["found"])
        self.assertFalse(r.json()["valid"])

    def test_un_formato_invalido_tampoco_se_distingue(self):
        """Un 400 diría «ese identificador no tiene la forma correcta», que
        también es información sobre qué forma tiene uno válido."""
        for malo in ("hola", "OE-sin-sufijo", "12345", "OE-20261029-"):
            with self.subTest(malo=malo):
                r = self._get(malo)
                self.assertEqual(r.status_code, 200, f"{malo} -> {r.status_code}")
                self.assertEqual(set(r.json()), CLAVES)
                self.assertFalse(r.json()["found"])

    def test_existente_y_inexistente_difieren_SOLO_en_los_valores(self):
        cert = self._emitir()
        vivo = self._get(cert.certificate_id).json()
        muerto = self._get("OE-20261029-NOEXISTE1").json()
        self.assertEqual(set(vivo), set(muerto))
        # Y el no encontrado no deja ningún campo en null salvo la fecha, que no
        # existe: un `None` de más también sería una diferencia de forma.
        self.assertEqual(muerto["kind"], "")
        self.assertIsNone(muerto["issued_at"])


class InterruptorTests(_Base):
    """T074 — apagado, la URL NO EXISTE; encendido, responde."""

    def test_apagado_responde_404_de_ruta(self):
        self._encender(False)
        cert = self._emitir()
        r = self._get(cert.certificate_id)
        print("  apagado ->", r.status_code)
        self.assertEqual(r.status_code, 404)
        # 🔑 Un 403 confirmaría que el producto tiene la función y que este
        # tenant la apagó. El cuerpo no puede nombrarla.
        cuerpo = r.content.decode().lower()
        for palabra in ("verify", "certificad", "deshabilit", "disabled"):
            self.assertNotIn(palabra, cuerpo)

    def test_encendido_responde(self):
        cert = self._emitir()
        self.assertEqual(self._get(cert.certificate_id).status_code, 200)

    def test_una_instalacion_recien_migrada_nace_apagada(self):
        """El default es la decisión, no una intención escrita en un documento."""
        from core.models import CoreSettings

        self.assertFalse(
            CoreSettings._meta.get_field("erase_public_verify_enabled").default
        )
        self._encender(False)
        self.assertEqual(self._get("OE-20261029-NOEXISTE1").status_code, 404)


class VeredictosTests(_Base):
    """T075 — los tres veredictos salen de `verify_certificate()`, sin sesión."""

    def test_un_certificado_integro_da_los_tres_en_verde(self):
        with override_settings(ERASE_SIGNING_KEY=""):
            cert = self._emitir()
        d = self._get(cert.certificate_id).json()
        print("  íntegro ->", {k: d[k] for k in ("document_intact", "chain_intact")})
        self.assertTrue(d["found"])
        self.assertTrue(d["document_intact"])
        self.assertTrue(d["chain_intact"])
        # Sin clave configurada: no firmado, y lo DICE en vez de dar inválido.
        self.assertFalse(d["signature_present"])
        self.assertFalse(d["signature_valid"])
        self.assertTrue(d["valid"])

    def test_la_cadena_rota_se_ve_y_no_dice_por_que(self):
        """Se rompe por SQL crudo: es justo la amenaza que la cadena detecta —
        alguien con acceso a la base, por fuera del modelo append-only."""
        cert = self._emitir()
        with connection.cursor() as c:
            c.execute(
                "UPDATE erase_erasecertificate SET prev_hash = %s WHERE id = %s",
                ["0" * 64, cert.pk],
            )
        d = self._get(cert.certificate_id).json()
        print("  cadena rota ->", d["chain_intact"], "| valid =", d["valid"])
        self.assertFalse(d["chain_intact"])
        self.assertFalse(d["valid"])
        # Ni el eslabón vecino, ni el hash esperado, ni una explicación.
        self.assertEqual(set(d), CLAVES)

    def test_el_documento_alterado_se_ve_sin_mostrar_el_documento(self):
        cert = self._emitir()
        with connection.cursor() as c:
            c.execute(
                "UPDATE erase_erasecertificate SET document_hash = %s WHERE id = %s",
                ["0" * 64, cert.pk],
            )
        d = self._get(cert.certificate_id).json()
        self.assertFalse(d["document_intact"])
        self.assertFalse(d["valid"])
        self.assertEqual(set(d), CLAVES)

    def test_un_certificado_v1_verifica_por_el_portal(self):
        """Si el portal sólo sirviera para los nuevos, no serviría.

        El literal congelado de `canonical_bytes` vive en `test_cert_appendix_c`;
        acá lo que se prueba es que el portal NO ramifica por versión de esquema.
        """
        doc = {
            "schema": "observer-erase-cert/1",
            "certificate_id": "OE-20260101-VIEJO00002",
            "kind": CertificateKind.REMOTE_DESTRUCTION,
            "tenant": "Cliente X",
            "standard_ref": "NIST SP 800-88r1 Clear",
            "operator": "bob",
        }
        cert = EraseCertificate(
            certificate_id=doc["certificate_id"],
            kind=doc["kind"],
            client=self.client_obj,
            tenant="Cliente X",
            data=doc,
            document_hash=hashlib.sha256(cert_mod.canonical_bytes(doc)).hexdigest(),
        )
        cert.save()
        d = self._get(cert.certificate_id).json()
        print("  v1 ->", d["valid"])
        self.assertTrue(d["found"])
        self.assertTrue(d["document_intact"])
        self.assertTrue(d["valid"])
        self.assertEqual(set(d), CLAVES)


@override_settings(
    # 🔴 Sin esto, NINGÚN throttle puede cortar en la suite: `ObserverTestCase`
    # corre con `ObserverDummyCache` (observerrmm/test.py:23), que no guarda
    # nada, y `SimpleRateThrottle` lleva su historial justamente en la caché.
    # Es la razón por la que los throttles de login del producto no tienen un
    # test de efecto: con la caché de pruebas siempre devuelven 200.
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class LimiteDeTasaTests(_Base):
    """T077 — el límite corta, y corta igual para válidos que para inexistentes.

    🪤 Dos trampas, las dos encontradas midiendo y no leyendo:

    1. La tasa **no** se puede bajar con `override_settings(REST_FRAMEWORK=...)`:
       `SimpleRateThrottle.THROTTLE_RATES` se evalúa **al importar la clase**, así
       que el override deja la tasa real en pie. Hay que parchear el atributo.
    2. La caché de la suite es **dummy**, y el throttle vive en la caché. Con las
       dos cosas sin resolver el test pasa en verde sin haber probado nada:
       cinco peticiones seguidas daban cinco 200.
    """

    def setUp(self):
        super().setUp()
        self._tasas = VerifyMinThrottle.THROTTLE_RATES
        tasas = dict(self._tasas)
        tasas.update({"verify_min": "3/minute", "verify_day": "100/day"})
        VerifyMinThrottle.THROTTLE_RATES = tasas
        VerifyDayThrottle.THROTTLE_RATES = tasas

    def tearDown(self):
        VerifyMinThrottle.THROTTLE_RATES = self._tasas
        VerifyDayThrottle.THROTTLE_RATES = self._tasas
        cache.clear()
        super().tearDown()

    def test_una_rafaga_termina_en_429(self):
        cert = self._emitir()
        codigos = [self._get(cert.certificate_id).status_code for _ in range(5)]
        print("  ráfaga ->", codigos)
        self.assertIn(429, codigos)

    def test_el_limite_no_distingue_existente_de_inexistente(self):
        """Si sólo se limitaran los fallidos, el throttle volvería a ser el
        oráculo que el resto del contrato evita."""
        cert = self._emitir()
        for _ in range(4):
            self._get(cert.certificate_id)
        # Agotado con identificadores VÁLIDOS, uno inexistente también corta.
        self.assertEqual(self._get("OE-20261029-NOEXISTE1").status_code, 429)

    def test_la_tasa_real_del_producto_es_la_que_se_despliega(self):
        """Control de que el parche de arriba no esconde una tasa ausente."""
        VerifyMinThrottle.THROTTLE_RATES = self._tasas
        self.assertIn("verify_min", self._tasas)
        self.assertIn("verify_day", self._tasas)
        print("  tasas reales ->", self._tasas["verify_min"], self._tasas["verify_day"])
