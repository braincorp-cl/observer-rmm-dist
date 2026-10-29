"""El certificado cumple el mínimo del Apéndice C y no afirma lo que no verificó.

Feature 053 · ola 1 · RF-01…RF-05 y RNF-04. La vara es el **Apéndice C de NIST
SP 800-88 Rev. 2** (sept-2025), que reemplazó a la Rev. 1 y fija el contenido
mínimo del certificado. Antes de esta feature el documento fallaba en cuatro
puntos a la vez, los cuatro visibles en el papel que se le entrega a un tercero:

1. citaba la Rev. 1, retirada;
2. ponía el **hostname en la casilla del modelo**;
3. mostraba a la misma persona como operador y como quien da fe;
4. afirmaba `PASS` **fijo en el código** en la vía de destrucción física, sin
   foto, sin testigo y sin peso.

Lo que más se cuida acá es la **compatibilidad v1**: un certificado ya emitido es
inmutable y tiene que seguir verificando. Se sostiene porque no se tocó
`canonical_bytes` ni se escribe sobre `data` — las dos únicas cosas que lo
romperían, ya que `verify_certificate` recomputa sobre el `data` almacenado tal
cual y no reconstruye el documento con `build_document`.
"""

import hashlib
import os
import tempfile

from cryptography.fernet import Fernet
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from agents.models import LostModeState
from erase import certificate as cert_mod
from erase import services
from erase.models import (
    AssetIntake,
    CertificateKind,
    DestructionEvidence,
    EraseAuditRecord,
    EraseCertificate,
    ImmutableRecordError,
    WipeOrderStatus,
)
from observerrmm.test import ObserverTestCase

LLAVE = Fernet.generate_key().decode()
TMP = tempfile.mkdtemp()

# Hash canonico del documento v1 de `CompatibilidadV1Tests._v1()`, congelado.
# Ver el comentario en ese metodo antes de tocarlo.
HASH_V1_CONGELADO = "56aa15b79957b50a872c9a96ca4066f628f82054b14eecdb278db4a951b5b831"


class _Base(ObserverTestCase):
    def setUp(self):
        self.authenticate()  # john/alice
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="Cliente X")
        self.site = baker.make("clients.Site", client=self.client_obj)
        self.agent = baker.make(
            "agents.Agent",
            site=self.site,
            hostname="BOX-HOSTNAME",
            agent_id="aid-apc",
            # `serial_number` y `make_model` son PROPIEDADES derivadas de
            # `wmi_detail`, no campos: baker no las puede setear. Con `{}`,
            # `make_model` devuelve el centinela "unknown make/model", que es
            # justo lo que el filtro tiene que convertir en "".
            wmi_detail={},
        )

    def _acta(self, **kw):
        datos = dict(
            process_id=f"P-{AssetIntake.objects.count() + 1}",
            client=self.client_obj,
            site=self.site,
            received_by="bodega",
            equipment_serial="SN-DISCO",
            equipment_make="Seagate",
            equipment_model="ST1000",
        )
        datos.update(kw)
        return AssetIntake.objects.create(**datos)

    def _wipe_certificado(self, *, intake=None, confirmado_por="alice"):
        """Una orden de wipe que llega a emitir certificado.

        🪤 Exige `dry_run=False` y estado `DISPATCHED`: con los defaults de
        `create_order` la orden entra por el camino del simulacro, no emite nada,
        y el `except Exception` blindado de `issue_wipe_certificate` no deja
        rastro porque la función ni se llama.
        """
        LostModeState.objects.get_or_create(
            agent=self.agent, defaults={"active": True, "reason": "robado"}
        )
        order = services.create_order(
            agent=self.agent,
            client=self.client_obj,
            site=self.site,
            action="crypto_erase",
            ordered_by="john",
            dry_run=False,
            intake=intake,
        )
        order.status = WipeOrderStatus.DISPATCHED
        order.confirmed_by = confirmado_por
        order.save()
        services.apply_wipe_report(
            order=order, result={"/a": "ok"}, verified=True, method_applied="m1"
        )
        return EraseCertificate.objects.get(order=order)

    def _certificar_c7(self, acta=None, **body):
        acta = acta or self._acta()
        return self.client.post(
            f"/erase/intake/{acta.pk}/certify-destruction/", body, format="multipart"
        )


class CompatibilidadV1Tests(_Base):
    """Un certificado emitido antes de la 053 sigue verificando y renderizando."""

    def _v1(self) -> EraseCertificate:
        """Un v1 armado a mano, con el esquema y la norma de entonces."""
        doc = {
            "schema": "observer-erase-cert/1",
            "certificate_id": "OE-20260101-VIEJO00001",
            "kind": CertificateKind.REMOTE_DESTRUCTION,
            "tenant": "Cliente X",
            "asset_tag": "ACT-1",
            "ticket_ref": "T-1",
            "equipment": {"make": "HP", "model": "ProOne 400", "serial": "S9"},
            "method_applied": "crypto_erase",
            "standard_ref": "NIST SP 800-88r1 Clear",
            "verification_result": "PASS",
            "operator": "bob",
            "started_at": "",
            "finished_at": "",
            "last_known_location": None,
            "software_version": "1.4.0",
        }
        cert = EraseCertificate(
            certificate_id=doc["certificate_id"],
            kind=doc["kind"],
            client=self.client_obj,
            tenant="Cliente X",
            data=doc,
            # 🔑 CONGELADO A PROPOSITO, no `sha256(canonical_bytes(doc))`.
            # Calcularlo con la funcion actual haria el test una tautologia:
            # pasaria siempre, incluso si alguien cambiara `canonical_bytes` y
            # con eso invalidara TODOS los certificados ya emitidos. Este literal
            # se calculo el 2026-10-28 con la implementacion vigente; si cambia el
            # orden de las claves, los separadores o el escape, este test cae —
            # que es justo la regresion que hay que cazar. Si cae: NO actualizar
            # el literal, revisar el cambio en `canonical_bytes`.
            document_hash=HASH_V1_CONGELADO,
        )
        cert.save()
        return cert

    def test_un_v1_sigue_siendo_valido(self):
        """El hash guardado es un literal: esto prueba que `canonical_bytes`
        sigue produciendo los mismos bytes que el dia que se emitio."""
        v = cert_mod.verify_certificate(self._v1())
        self.assertTrue(v["document_intact"])
        self.assertTrue(v["chain_intact"])
        # Sin firma el certificado es válido declarándolo, no inválido.
        self.assertFalse(v["signature_present"])
        self.assertTrue(v["valid"])

    def test_un_v1_renderiza_sin_ramificar_por_version(self):
        html = cert_mod.render_html(self._v1())
        self.assertIn("HP ProOne 400", html)  # equipment sin `make_model`
        # Los campos que el v1 no tiene salen N/A, no revientan ni quedan vacíos.
        self.assertIn("Da fe (segunda persona)", html)
        self.assertIn("N/A", html)

    def test_control_negativo_un_byte_distinto_lo_invalida(self):
        """Muta `data` EN MEMORIA, no con `save()`.

        Guardar lanzaría `ImmutableRecordError` y el test pasaría por el motivo
        equivocado: probaría la inmutabilidad, no la detección del cambio.
        """
        cert = self._v1()
        cert.data["operator"] = "bob!"  # un byte distinto
        v = cert_mod.verify_certificate(cert)
        self.assertFalse(v["document_intact"])
        self.assertFalse(v["valid"])

    def test_y_que_guardarlo_esta_prohibido(self):
        cert = self._v1()
        cert.data["operator"] = "bob!"
        with self.assertRaises(ImmutableRecordError):
            cert.save()


class NormaVigenteTests(_Base):
    """RF-01: las dos vías citan la norma vigente, ninguna la retirada."""

    def test_wipe_cita_rev_2(self):
        d = self._wipe_certificado().data
        self.assertIn("Rev. 2", d["standard_ref"])
        self.assertIn("IEEE 2883", d["standard_ref"])
        self.assertNotIn("800-88r1", d["standard_ref"])

    def test_destruccion_fisica_cita_rev_2(self):
        r = self._certificar_c7()
        self.assertEqual(r.status_code, 201)
        d = EraseCertificate.objects.get(pk=r.json()["id"]).data
        self.assertIn("Rev. 2", d["standard_ref"])
        self.assertIn("IEEE 2883", d["standard_ref"])
        self.assertNotIn("800-88r1", d["standard_ref"])

    def test_ningun_certificado_nuevo_menciona_la_rev_1(self):
        self._wipe_certificado()
        self._certificar_c7()
        for cert in EraseCertificate.objects.all():
            self.assertNotIn("800-88r1", cert.data["standard_ref"], cert.certificate_id)


class ConcurrenciaTests(_Base):
    """RF-02: quien da fe es una segunda persona, y el bloque se emite siempre."""

    def test_el_wipe_confirmado_pone_al_confirmador_como_quien_da_fe(self):
        d = self._wipe_certificado(confirmado_por="alice").data
        self.assertEqual(d["operator"], "john")
        self.assertEqual(d["concurrence"]["name"], "alice")
        self.assertNotEqual(d["concurrence"]["name"], d["operator"])

    def test_sin_segunda_persona_las_cuatro_claves_van_vacias(self):
        d = self._wipe_certificado(confirmado_por="").data
        self.assertEqual(set(d["concurrence"]), {"name", "role", "contact", "at"})
        self.assertTrue(all(v == "" for v in d["concurrence"].values()))
        # Y el operador NO se cuela en el lugar de quien da fe.
        self.assertNotEqual(d["concurrence"]["name"], d["operator"])


class EquipoTests(_Base):
    """RF-04: cada dato del equipo en su casilla, y nunca un centinela."""

    def test_el_hostname_no_viaja_como_modelo(self):
        eq = self._wipe_certificado().data["equipment"]
        self.assertEqual(eq["hostname"], "BOX-HOSTNAME")
        self.assertNotEqual(eq["model"], "BOX-HOSTNAME")
        self.assertNotEqual(eq["make_model"], "BOX-HOSTNAME")

    def test_sin_inventario_queda_vacio_y_no_el_centinela(self):
        """Control negativo: `wmi_detail={}` ⇒ `make_model` es un centinela."""
        self.assertEqual(self.agent.make_model, "unknown make/model")
        eq = self._wipe_certificado().data["equipment"]
        self.assertEqual(eq["make_model"], "")
        self.assertNotIn("unknown", eq["make_model"])
        self.assertNotIn("error", eq["make_model"])

    def test_el_acta_aporta_fabricante_y_modelo(self):
        d = EraseCertificate.objects.get(pk=self._certificar_c7().json()["id"]).data
        self.assertEqual(d["equipment"]["make"], "Seagate")
        self.assertEqual(d["equipment"]["model"], "ST1000")
        self.assertEqual(d["equipment"]["make_model"], "Seagate ST1000")


class VeredictoTests(_Base):
    """RF-05: `PASS` sólo con método acreditado Y testigo nombrado."""

    def _c7(self, **body):
        return EraseCertificate.objects.get(pk=self._certificar_c7(**body).json()["id"])

    def test_sin_acreditar_nada_dice_no_verificado(self):
        cert = self._c7()
        self.assertEqual(cert.verification_result, "NOT_VERIFIED")
        html = cert_mod.render_html(cert)
        self.assertNotIn("PASS", html)
        self.assertIn("SIN VERIFICACIÓN ACREDITADA", html)

    def test_metodo_sin_testigo_no_alcanza(self):
        self.assertEqual(
            self._c7(verification_method="photographic").verification_result,
            "NOT_VERIFIED",
        )

    def test_testigo_sin_metodo_tampoco_alcanza(self):
        self.assertEqual(
            self._c7(concurrence_name="Ana Soto").verification_result,
            "NOT_VERIFIED",
        )

    def test_metodo_y_testigo_dan_pass(self):
        cert = self._c7(
            verification_method="witnessed",
            concurrence_name="Ana Soto",
            concurrence_role="Jefa de bodega",
        )
        self.assertEqual(cert.verification_result, "PASS")
        self.assertEqual(cert.data["concurrence"]["name"], "Ana Soto")
        self.assertTrue(cert.data["concurrence"]["at"])
        self.assertIn("PASS", cert_mod.render_html(cert))

    def test_presenciada_sin_nombrar_al_testigo_se_rechaza(self):
        """La única combinación incoherente la ataja el serializer, con 400."""
        r = self._certificar_c7(verification_method="witnessed")
        self.assertEqual(r.status_code, 400)
        self.assertIn("concurrence_name", r.json())

    def test_el_veredicto_cabe_en_la_columna(self):
        largo = EraseCertificate._meta.get_field("verification_result").max_length
        self.assertLessEqual(len(cert_mod.VERIFICATION_NOT_VERIFIED), largo)


class DestinoDelMedioTests(_Base):
    """RF-03: el destino se declara, y vacío cuando de verdad no consta."""

    def test_viaja_desde_el_acta(self):
        acta = self._acta(
            media_disposition="destroyed",
            media_disposition_detail="trituradora certificada",
        )
        d = EraseCertificate.objects.get(
            pk=self._certificar_c7(acta=acta).json()["id"]
        ).data
        self.assertEqual(d["media_disposition"], "destroyed")
        self.assertEqual(d["media_disposition_detail"], "trituradora certificada")

    def test_anclado_a_caso_perdido_va_presente_y_vacio(self):
        """Un campo vacío declara «no consta»; uno ausente es ambiguo."""
        d = self._wipe_certificado().data
        self.assertIn("media_disposition", d)
        self.assertEqual(d["media_disposition"], "")


@override_settings(LOST_MODE_EVIDENCE_BASE_PATH=TMP, LOST_MODE_EVIDENCE_KEY=LLAVE)
class EvidenciaPurgableTests(_Base):
    """L-04: el certificado es permanente, la evidencia es purgable.

    🪤 El override cubre la CLASE entera, no sólo la petición: el almacén resuelve
    la ruta en cada uso, así que leer `ev.asset` fuera del bloque volvería a
    apuntar a la ruta de producción.
    """

    CONTENIDO = b"JPEGFAKE" * 64

    def _con_foto(self):
        r = self._certificar_c7(
            verification_method="photographic",
            concurrence_name="Ana Soto",
            evidence_file=SimpleUploadedFile(
                "destruccion.jpg", self.CONTENIDO, content_type="image/jpeg"
            ),
        )
        self.assertEqual(r.status_code, 201)
        return EraseCertificate.objects.get(pk=r.json()["id"])

    def test_la_foto_se_guarda_y_su_hash_viaja_en_el_documento(self):
        cert = self._con_foto()
        ev = DestructionEvidence.objects.get()
        esperado = hashlib.sha256(self.CONTENIDO).hexdigest()
        self.assertEqual(ev.sha256, esperado)
        self.assertEqual(cert.data["evidence_sha256"], esperado)
        self.assertEqual(cert.data["evidence_filename"], "destruccion.jpg")
        # La columna `size` guarda el tamaño EN CLARO.
        self.assertEqual(ev.size, len(self.CONTENIDO))

    def test_el_adjunto_queda_cifrado_en_reposo(self):
        self._con_foto()
        ev = DestructionEvidence.objects.get()
        # El `seek(0)` del hasher importa: sin él se guardarían 0 bytes.
        self.assertTrue(ev.asset)
        with open(os.path.join(TMP, ev.asset.name), "rb") as f:
            crudo = f.read()
        self.assertGreater(len(crudo), 0)
        self.assertNotIn(self.CONTENIDO, crudo)

    def test_purgar_la_evidencia_no_invalida_el_certificado(self):
        cert = self._con_foto()
        esperado = cert.data["evidence_sha256"]
        DestructionEvidence.objects.get().delete()
        v = cert_mod.verify_certificate(cert)
        self.assertTrue(v["document_intact"])
        self.assertTrue(v["valid"])
        # El hash sigue en el documento firmado: si alguien conserva una copia,
        # se puede comprobar que es la misma que el certificado citó.
        self.assertEqual(cert.data["evidence_sha256"], esperado)

    def test_sin_foto_no_se_crea_fila_de_evidencia(self):
        antes = DestructionEvidence.objects.count()
        cert = EraseCertificate.objects.get(pk=self._certificar_c7().json()["id"])
        self.assertEqual(DestructionEvidence.objects.count() - antes, 0)
        self.assertEqual(cert.data["evidence_sha256"], "")


class TablaDelCertificadoCongeladaTests(ObserverTestCase):
    """La ola 2 no toca `erase_erasecertificate`, y esto lo vigila.

    El hash congelado de `_v1()` prueba que `canonical_bytes` sigue produciendo
    los mismos bytes. Este test cubre el otro flanco: que el **esquema** de la
    tabla del certificado no cambió. Si una migración futura le agrega, quita o
    renombra una columna, acá se entera alguien.

    🪤 Si este test cae, la pregunta NO es "actualizo la lista". Es por qué se
    está migrando una tabla que guarda documentos inmutables ya firmados.
    """

    COLUMNAS = {
        "agent_id",
        "asset_tag",
        "certificate_id",
        "client_id",
        "created_at",
        "data",
        "document_hash",
        "finished_at",
        "id",
        "intake_id",
        "kind",
        "method_applied",
        "operator",
        "order_id",
        "prev_hash",
        "record_hash",
        "signature",
        "signature_alg",
        "signing_key_id",
        "site_id",
        "software_version",
        "standard_ref",
        "started_at",
        "tenant",
        "verification_result",
    }

    def test_el_esquema_del_certificado_no_cambio(self):
        from django.db import connection

        with connection.cursor() as cursor:
            columnas = {
                c.name
                for c in connection.introspection.get_table_description(
                    cursor, "erase_erasecertificate"
                )
            }
        self.assertEqual(columnas, self.COLUMNAS)

    def test_la_cadena_de_custodia_no_vive_en_la_tabla_del_certificado(self):
        """Control: los eventos nuevos tienen tabla propia, no columnas acá."""
        from django.db import connection

        self.assertIn("erase_custodyevent", connection.introspection.table_names())


@override_settings(LOST_MODE_EVIDENCE_BASE_PATH=TMP, LOST_MODE_EVIDENCE_KEY=LLAVE)
class LaRetencionNoTocaElCertificadoTests(_Base):
    """Ola 3 (RNF-06/L-04): la purga borra el adjunto y NADA más.

    🔴 Este control no se puede saltar, y no alcanza con comprobar que no se
    lance `ImmutableRecordError`: la ola 2 demostró que un borrado en cascada
    **se lleva filas append-only sin dispararlo**. Hay que contar filas y
    re-verificar el documento.
    """

    CONTENIDO = b"JPEGFAKE" * 64

    def _con_foto(self):
        r = self._certificar_c7(
            verification_method="photographic",
            concurrence_name="Ana Soto",
            evidence_file=SimpleUploadedFile(
                "destruccion.jpg", self.CONTENIDO, content_type="image/jpeg"
            ),
        )
        self.assertEqual(r.status_code, 201)
        return EraseCertificate.objects.get(pk=r.json()["id"])

    def test_purgar_el_adjunto_deja_el_certificado_intacto_y_verificable(self):
        from django.utils import timezone

        from erase.tasks import prune_erase_attachments

        cert = self._con_foto()
        sha_citado = cert.data["evidence_sha256"]
        certs_antes = EraseCertificate.objects.count()
        audit_antes = EraseAuditRecord.objects.count()

        # Envejecer el adjunto más allá de cualquier plazo posible.
        DestructionEvidence.objects.update(
            uploaded_at=timezone.now() - timezone.timedelta(days=4000)
        )
        prune_erase_attachments()

        # 1. El binario se fue.
        ev = DestructionEvidence.objects.get()
        self.assertFalse(ev.asset)

        # 2. Delta 0 en las dos tablas append-only. Contando filas, no esperando
        #    una excepción que un CASCADE no lanzaría.
        self.assertEqual(EraseCertificate.objects.count() - certs_antes, 0)
        self.assertEqual(EraseAuditRecord.objects.count() - audit_antes, 0)

        # 3. El documento sigue verificando en las TRES comprobaciones.
        cert.refresh_from_db()
        v = cert_mod.verify_certificate(cert)
        self.assertTrue(v["document_intact"])
        self.assertTrue(v["chain_intact"])
        self.assertTrue(v["valid"])

        # 4. El hash citado sobrevive: es lo que hace defendible la purga.
        self.assertEqual(cert.data["evidence_sha256"], sha_citado)
        self.assertEqual(ev.sha256, sha_citado)

    def test_la_purga_no_mueve_el_hash_congelado_de_la_ola_1(self):
        """🔒 Si esto cae, se tocó `canonical_bytes` o la tabla del certificado.

        El hash congelado es el `document_hash` **almacenado** del v1, y
        `verify_certificate` lo recomputa sobre `data` y los compara: por eso
        `document_intact is True` **es** la comprobación del congelado, y no hace
        falta recalcularlo acá a mano.
        """
        from erase.tasks import prune_erase_attachments

        v1 = CompatibilidadV1Tests._v1(self)
        self.assertEqual(v1.document_hash, HASH_V1_CONGELADO)

        prune_erase_attachments()

        v1.refresh_from_db()
        self.assertEqual(v1.document_hash, HASH_V1_CONGELADO)
        self.assertTrue(cert_mod.verify_certificate(v1)["document_intact"])
