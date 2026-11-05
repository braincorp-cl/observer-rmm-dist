"""Las descargas de erase dejan traza en el registro de auditoría.

🔴 Lo que esto fija: `RetrievedFileDownload` entrega un archivo recuperado del
equipo de una persona y `EraseCertificatePDF` emite el documento que sale de la
consola hacia un tercero, y ninguna de las dos escribía `AuditLog`. En
`agents/views.py` sí lo hacían las acciones vecinas —`audit_mesh_session`,
`audit_raw_command`, `audit_endpoint_response`—, o sea que tomar control del
equipo dejaba traza y bajarse los documentos de esa persona no.

Este módulo existe para ser defendible ante una auditoría: la pregunta "¿quién
miró los archivos recuperados de este empleado?" tiene que tener respuesta.

🔒 La otra mitad del test es lo que la traza NO dice. Ni el contenido del archivo
ni la ruta completa en el equipo entran a `AuditLog`, que es el audit operativo
PURGABLE: la ruta de un archivo personal es dato del titular y sobreviviría al
adjunto que ya se purgó. Alcanza el nombre del archivo y el id de la fila.

🪤 Todas las aserciones de volumen son DELTAS, nunca conteos absolutos:
`pytest-randomly` baraja el orden y hay fixtures que dejan filas incidentales.
"""

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from accounts.models import Role, User
from agents.models import LostModeState
from erase.models import (
    EraseCertificate,
    FileRetrievalOrder,
    FileRetrievalStatus,
    RetrievedFile,
)
from logs.models import AuditLog
from observerrmm.constants import AuditActionType
from observerrmm.test import ObserverTestCase

RUTA_EN_EL_EQUIPO = "C:/Users/jperez/Mis documentos/finiquito-confidencial.pdf"
NOMBRE_DEL_ARCHIVO = "finiquito-confidencial.pdf"
CONTENIDO = b"texto reservado del titular"
SERIE_DEL_EQUIPO = "SN-SERIE-SECRETA-42"

_ALMACEN = tempfile.mkdtemp()


@override_settings(LOST_MODE_EVIDENCE_BASE_PATH=_ALMACEN, LOST_MODE_EVIDENCE_KEY="")
class RetrievedFileDownloadAuditTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="ACME")
        self.site = baker.make("clients.Site", client=self.client_obj)
        # `serial_number` es una propiedad que lee `wmi_detail`, no una columna.
        self.agent = baker.make(
            "agents.Agent",
            site=self.site,
            hostname="BOX-DESCARGA",
            agent_id="aid-descarga",
            wmi_detail={"bios": [[{"SerialNumber": SERIE_DEL_EQUIPO}]]},
        )
        LostModeState.objects.create(agent=self.agent, active=True, reason="robado")

        self.order = FileRetrievalOrder.objects.create(
            agent=self.agent,
            client=self.client_obj,
            site=self.site,
            agent_id_snapshot=self.agent.agent_id,
            agent_hostname=self.agent.hostname,
            agent_serial=self.agent.serial_number,
            paths=[RUTA_EN_EL_EQUIPO],
            requested_by="john",
            status=FileRetrievalStatus.DONE,
        )
        self.rf = RetrievedFile.objects.create(
            order=self.order,
            source_path=RUTA_EN_EL_EQUIPO,
            asset=SimpleUploadedFile(NOMBRE_DEL_ARCHIVO, CONTENIDO),
            size=len(CONTENIDO),
        )
        self.url = f"/erase/fileretrieval/{self.order.pk}/files/{self.rf.pk}/download/"

    def test_descargar_deja_una_fila_con_el_usuario_correcto(self):
        antes = AuditLog.objects.count()

        r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(AuditLog.objects.count(), antes + 1)

        fila = AuditLog.objects.latest("id")
        self.assertEqual(fila.username, "john")
        self.assertEqual(fila.action, AuditActionType.VIEW)
        self.assertEqual(fila.agent_id, self.agent.agent_id)
        self.assertEqual(fila.agent, self.agent.hostname)
        self.assertIn("downloaded retrieved file", fila.message)

    def test_cada_descarga_suma_una_fila(self):
        """Delta por descarga: el registro cuenta accesos, no archivos."""
        antes = AuditLog.objects.count()

        self.client.get(self.url)
        self.client.get(self.url)
        self.client.force_authenticate(user=self.alice)
        self.client.get(self.url)

        self.assertEqual(AuditLog.objects.count(), antes + 3)
        self.assertEqual(
            list(
                AuditLog.objects.order_by("-id")[:3].values_list("username", flat=True)
            ),
            ["alice", "john", "john"],
        )

    def test_la_traza_no_lleva_la_ruta_del_equipo_ni_el_contenido(self):
        """🔒 Dice quién bajó qué documento, no qué decía ni de dónde salió."""
        self.client.get(self.url)
        fila = AuditLog.objects.latest("id")

        self.assertEqual(
            fila.after_value,
            {"file_id": self.rf.pk, "file_name": NOMBRE_DEL_ARCHIVO},
        )
        self.assertIsNone(fila.before_value)

        volcado = _volcado(fila)
        self.assertNotIn(RUTA_EN_EL_EQUIPO, volcado, "la ruta del equipo entró al log")
        self.assertNotIn("C:/Users", volcado, "la ruta del equipo entró al log")
        self.assertNotIn("Mis documentos", volcado, "la ruta del equipo entró al log")
        self.assertNotIn(
            CONTENIDO.decode(), volcado, "el contenido del archivo entró al log"
        )
        self.assertNotIn(
            self.agent.serial_number, volcado, "la serie del equipo entró al log"
        )

    def test_la_traza_conserva_el_origen_del_request(self):
        """El `debug_info` sobrevive aunque la ruta lleve un `<uuid:pk>`.

        `AuditLog.save()` reemplaza el campo entero por un `{"error": ...}`
        cuando no puede serializarlo, y el convertidor `uuid` de Django entrega
        un `uuid.UUID` en `view_kwargs`. Sin la normalización de
        `observerrmm.middleware.jsonizable`, esta fila perdía en silencio la IP,
        la URL y el método — justo los datos que hacen útil la traza de "quién
        bajó". Es la primera vista con kwarg UUID que escribe `AuditLog`.
        """
        self.client.get(self.url)
        fila = AuditLog.objects.latest("id")

        self.assertNotIn("error", fila.debug_info)
        self.assertEqual(fila.debug_info["url"], self.url)
        self.assertEqual(fila.debug_info["method"], "GET")
        self.assertEqual(fila.debug_info["view_class"], "RetrievedFileDownload")
        self.assertEqual(
            fila.debug_info["view_kwargs"],
            {"pk": str(self.order.pk), "file_id": self.rf.pk},
        )

    def test_un_archivo_sin_contenido_no_deja_traza_de_descarga(self):
        """404: no se bajó nada, así que no hay acceso que registrar."""
        vacio = RetrievedFile.objects.create(
            order=self.order, source_path="C:/Users/jperez/otro.docx"
        )
        antes = AuditLog.objects.count()

        r = self.client.get(
            f"/erase/fileretrieval/{self.order.pk}/files/{vacio.pk}/download/"
        )

        self.assertEqual(r.status_code, 404)
        self.assertEqual(AuditLog.objects.count(), antes)

    def test_un_rol_fuera_de_alcance_no_deja_traza_porque_no_descarga(self):
        rol = Role.objects.create(name="otro-cliente", can_retrieve_files=True)
        rol.can_view_clients.set([baker.make("clients.Client")])
        user = User.objects.create_user(username="ajeno", password="x")
        user.role = rol
        user.save()
        self.client.force_authenticate(user=user)
        antes = AuditLog.objects.count()

        r = self.client.get(self.url)

        self.assertEqual(r.status_code, 404)
        self.assertEqual(AuditLog.objects.count(), antes)


class EraseCertificatePDFAuditTests(ObserverTestCase):
    def setUp(self):
        self.authenticate()
        self.setup_coresettings()
        self.client_obj = baker.make("clients.Client", name="MINSAL")
        self.site = baker.make("clients.Site", client=self.client_obj)

        r_in = self.client.post(
            "/erase/intake/",
            {
                "client": self.client_obj.pk,
                "site": self.site.pk,
                "equipment_serial": "SN-EQUIPO-777",
                "media_serial": "MED-SERIE-999",
                "asset_tag": "ACT-7",
                "ticket_ref": "TCK-1",
                "state": "non_functional",
            },
            format="json",
        )
        self.assertEqual(r_in.status_code, 201)
        r_cert = self.client.post(
            f"/erase/intake/{r_in.json()['id']}/certify-destruction/",
            {"method": "trituracion", "operator": "op-terreno"},
            format="json",
        )
        self.assertEqual(r_cert.status_code, 201)
        self.cert = EraseCertificate.objects.get(
            certificate_id=r_cert.json()["certificate_id"]
        )
        self.url = f"/erase/certificates/{self.cert.pk}/pdf/"

    def test_emitir_el_pdf_deja_una_fila_con_el_usuario_correcto(self):
        antes = AuditLog.objects.count()

        r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(AuditLog.objects.count(), antes + 1)

        fila = AuditLog.objects.latest("id")
        self.assertEqual(fila.username, "john")
        self.assertEqual(fila.action, AuditActionType.VIEW)
        self.assertIn(self.cert.certificate_id, fila.message)
        self.assertEqual(fila.after_value, {"certificate_id": self.cert.certificate_id})

    def test_cada_emision_suma_una_fila(self):
        antes = AuditLog.objects.count()

        self.client.get(self.url)
        self.client.force_authenticate(user=self.alice)
        self.client.get(self.url)

        self.assertEqual(AuditLog.objects.count(), antes + 2)
        self.assertEqual(
            list(
                AuditLog.objects.order_by("-id")[:2].values_list("username", flat=True)
            ),
            ["alice", "john"],
        )

    def test_la_traza_no_lleva_el_documento_ni_las_series(self):
        """🔒 El documento es evidencia PERMANENTE; `AuditLog` se poda."""
        self.client.get(self.url)
        fila = AuditLog.objects.latest("id")

        volcado = _volcado(fila)
        self.assertNotIn("SN-EQUIPO-777", volcado, "la serie del equipo entró al log")
        self.assertNotIn("MED-SERIE-999", volcado, "la serie del medio entró al log")
        # Ni el hash del documento firmado ni su contenido: el certificado
        # íntegro vive en el repositorio append-only y se llega a él por
        # `certificate_id`, que es lo único que la fila guarda.
        self.assertNotIn(self.cert.document_hash, volcado)
        self.assertNotIn("trituracion", volcado)
        self.assertNotIn("op-terreno", volcado)

    def test_el_json_del_certificado_tambien_deja_traza(self):
        """El hueco que este archivo documentaba, cerrado.

        `/erase/certificates/<pk>/json/` entrega el MISMO documento firmado en
        otro formato. Mientras sólo auditara el PDF, bajarse el certificado sin
        dejar traza era cambiar de botón — y no era teórico: la consola llama
        este endpoint desde `web/app/src/api/erase.js:46`.

        🪤 La revisión que lo encontró había concluido que no existía UI de
        `erase` porque miró `web/src/` en vez de `web/app/src/`. La conclusión
        de dejarlo anotado fue correcta; la razón, equivocada, y por eso el
        hueco quedó clasificado como menor de lo que era.
        """
        antes = AuditLog.objects.count()

        r = self.client.get(f"/erase/certificates/{self.cert.pk}/json/")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(AuditLog.objects.count() - antes, 1)

        fila = AuditLog.objects.order_by("-id").first()
        self.assertEqual(fila.username, "john")
        self.assertEqual(fila.after_value["certificate_id"], self.cert.certificate_id)
        # El documento firmado NO entra en el audit purgable: va el
        # identificador, no el `data` ni el `document_hash`.
        self.assertNotIn("data", fila.after_value)
        self.assertNotIn("document_hash", fila.after_value)

    def test_las_dos_vias_del_certificado_auditan_igual(self):
        """PDF y JSON son el mismo acceso: la traza no debe depender del botón."""
        antes = AuditLog.objects.count()

        self.client.get(f"/erase/certificates/{self.cert.pk}/pdf/")
        self.client.get(f"/erase/certificates/{self.cert.pk}/json/")

        self.assertEqual(AuditLog.objects.count() - antes, 2)
        filas = list(AuditLog.objects.order_by("-id")[:2])
        self.assertEqual(
            {f.after_value["certificate_id"] for f in filas},
            {self.cert.certificate_id},
        )


def _volcado(fila: AuditLog) -> str:
    import json

    return json.dumps(
        {
            "username": fila.username,
            "agent": fila.agent,
            "agent_id": fila.agent_id,
            "action": fila.action,
            "object_type": fila.object_type,
            "message": fila.message,
            "before_value": fila.before_value,
            "after_value": fila.after_value,
            "debug_info": fila.debug_info,
        },
        default=str,
    )
