import hashlib
import uuid

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agents.models import Agent
from erase import certificate as cert_mod
from erase import services, signing
from erase.models import (
    AssetIntake,
    CertificateKind,
    DestructionEvidence,
    DestructionVerification,
    EraseAction,
    EraseCertificate,
    FileRetrievalOrder,
    WipeOrder,
    WipePathTemplate,
)
from erase.permissions import (
    ManageAssetIntakePerms,
    RetrieveFilesPerms,
    ViewEraseCertificatesPerms,
    WipeDevicePerms,
)
from erase.serializers import (
    AssetIntakeSerializer,
    CertifyDestructionSerializer,
    EraseAuditRecordSerializer,
    EraseCertificateDetailSerializer,
    EraseCertificateListSerializer,
    FileRetrievalOrderCreateSerializer,
    FileRetrievalOrderSerializer,
    RetrievedFileSerializer,
    WipeOrderCancelSerializer,
    WipeOrderConfirmSerializer,
    WipeOrderCreateSerializer,
    WipeOrderSerializer,
    WipePathTemplateSerializer,
)


class WipeOrderList(APIView):
    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def get(self, request):
        qs = WipeOrder.objects.filter_by_role(request.user).select_related(
            "agent", "client", "site"
        )
        return Response(WipeOrderSerializer(qs, many=True).data)


class WipeOrderCreate(APIView):
    """Ordena un borrado sobre un equipo. Nace pendiente de segunda confirmación.

    Cuelga de un expediente, nunca del listado general (RF-12): un caso de equipo
    perdido ABIERTO o un acta de ingreso a baja. Lo resuelve el servidor con
    `services.resolve_order_anchor`, así que la guardia no depende de la consola y
    cubre por igual la API y la llave de integración. La orden no viaja al equipo
    por sí sola — exige una segunda persona y la ventana de arrepentimiento, y el
    despacho sigue GATED por ADR-029.
    """

    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)
        s = WipeOrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        action = s.validated_data["action"]
        scope = s.validated_data.get("scope") or {}

        # wipe (feature 043): materializa las rutas = plantilla + ajustes (RN-07) y
        # valida el tope por orden (RF-07) ANTES de crear. Las órdenes ya emitidas no
        # se alteran si la plantilla cambia después: se congela en `scope`.
        if action == EraseAction.WIPE:
            template = None
            template_id = s.validated_data.get("template")
            if template_id is not None:
                template = get_object_or_404(
                    WipePathTemplate.objects.filter_by_role(request.user),
                    pk=template_id,
                )
            paths = services.resolve_wipe_paths(
                template=template,
                paths_add=s.validated_data.get("paths_add") or [],
                paths_remove=s.validated_data.get("paths_remove") or [],
            )
            try:
                services.validate_wipe_paths(paths)
            except services.OrderStateError as e:
                return Response({"detail": str(e)}, status=422)
            scope = {**scope, "paths": paths}

        # RF-12: el expediente lo decide el servidor. El `lost_mode_cycle` que
        # venga en el payload se acepta e IGNORA (el serializer lo sigue
        # aceptando para no romper el diálogo de la consola): es un contador de
        # capturas de evidencia, no la prueba de que el caso esté abierto.
        try:
            anchor = services.resolve_order_anchor(agent=agent)
        except services.OrderAnchorError as e:
            return Response({"detail": str(e)}, status=409)

        order = services.create_order(
            agent=agent,
            client=agent.site.client,
            site=agent.site,
            action=action,
            ordered_by=request.user.username,
            scope=scope,
            dry_run=s.validated_data.get("dry_run", True),
            reason=s.validated_data["reason"],
            lost_mode_cycle=anchor.lost_mode_cycle,
            intake=anchor.intake,
        )
        return Response(WipeOrderSerializer(order).data, status=201)


class WipeOrderDetail(APIView):
    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def get(self, request, pk):
        order = get_object_or_404(WipeOrder.objects.filter_by_role(request.user), pk=pk)
        data = WipeOrderSerializer(order).data
        data["audit_records"] = EraseAuditRecordSerializer(
            order.audit_records.order_by("id"), many=True
        ).data
        # Enlace al certificado C (feature 043 · T019): no-null sólo si la orden
        # se ejecutó y verificó (RF-10/D-07); el frontend ofrece su descarga.
        cert = order.certificates.first()
        data["certificate"] = cert.pk if cert else None
        return Response(data)


class WipeOrderConfirm(APIView):
    """Segunda confirmación (RF-G02). Debe ser una persona distinta a la que ordenó."""

    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def post(self, request, pk):
        order = get_object_or_404(WipeOrder.objects.filter_by_role(request.user), pk=pk)
        s = WipeOrderConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.confirm_order(
                order=order,
                confirmed_by=request.user.username,
                recovery_seconds=s.validated_data.get("recovery_seconds"),
            )
        except services.OrderStateError as e:
            return Response({"detail": str(e)}, status=409)
        return Response(WipeOrderSerializer(order).data)


class WipeOrderCancel(APIView):
    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def post(self, request, pk):
        order = get_object_or_404(WipeOrder.objects.filter_by_role(request.user), pk=pk)
        s = WipeOrderCancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.cancel_order(
                order=order,
                cancelled_by=request.user.username,
                reason=s.validated_data.get("reason", ""),
            )
        except services.OrderStateError as e:
            return Response({"detail": str(e)}, status=409)
        return Response(WipeOrderSerializer(order).data)


class WipePathTemplateList(APIView):
    """Plantillas de rutas para precargar una orden de wipe (feature 043 · T017).

    Sólo lectura y gobernado por `can_wipe_device`, igual que las órdenes. Con
    `?agent_id=` recorta a las plantillas del cliente/sitio del equipo (el diálogo
    de wipe se abre desde la ficha de un equipo); sin él, devuelve todo lo que el
    rol autoriza (`filter_by_role`). No hay materialización acá: sólo lista la
    base de rutas que el ordenante ajusta y el servidor congela al crear.
    """

    permission_classes = [IsAuthenticated, WipeDevicePerms]

    def get(self, request):
        qs = WipePathTemplate.objects.filter_by_role(request.user).select_related(
            "client", "site"
        )
        agent_id = request.query_params.get("agent_id")
        if agent_id:
            agent = get_object_or_404(Agent, agent_id=agent_id)
            qs = qs.filter(client=agent.site.client)
        return Response(WipePathTemplateSerializer(qs.order_by("name"), many=True).data)


class FileRetrievalOrderList(APIView):
    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def get(self, request):
        qs = FileRetrievalOrder.objects.filter_by_role(request.user).select_related(
            "agent", "client", "site"
        )
        agent_id = request.query_params.get("agent_id")
        if agent_id:
            qs = qs.filter(agent__agent_id=agent_id)
        return Response(FileRetrievalOrderSerializer(qs, many=True).data)


class FileRetrievalOrderCreate(APIView):
    """Ordena recuperar archivos de un equipo (fileretrieval).

    Mismo expediente que el camino destructivo (RF-12): caso de equipo perdido
    abierto o acta de ingreso. El ancla es idéntica a propósito, para que no se
    pueda borrar un activo en baja sin poder antes rescatar sus archivos. No es
    destructiva: no hay doble confirmación ni ventana; el permiso liviano
    `can_retrieve_files` la gobierna.
    """

    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        # RF-12: el mismo helper que el camino destructivo. Antes esto era un
        # bloque inline que exigía caso perdido y coaccionaba el ciclo a 0; el 0
        # inventaba un ciclo para el caso recién denunciado, que no tiene ninguno.
        try:
            anchor = services.resolve_order_anchor(agent=agent)
        except services.OrderAnchorError as e:
            return Response({"detail": str(e)}, status=409)

        s = FileRetrievalOrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            order = services.create_retrieval_order(
                agent=agent,
                client=agent.site.client,
                site=agent.site,
                paths=s.validated_data["paths"],
                requested_by=request.user.username,
                dry_run=s.validated_data.get("dry_run", False),
                lost_mode_cycle=anchor.lost_mode_cycle,
                intake=anchor.intake,
            )
        except services.OrderStateError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(FileRetrievalOrderSerializer(order).data, status=201)


class FileRetrievalOrderDetail(APIView):
    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def get(self, request, pk):
        order = get_object_or_404(
            FileRetrievalOrder.objects.filter_by_role(request.user), pk=pk
        )
        data = FileRetrievalOrderSerializer(order).data
        data["files"] = RetrievedFileSerializer(
            order.files.order_by("id"), many=True
        ).data
        return Response(data)


class FileRetrievalOrderCancel(APIView):
    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def post(self, request, pk):
        order = get_object_or_404(
            FileRetrievalOrder.objects.filter_by_role(request.user), pk=pk
        )
        try:
            services.cancel_retrieval_order(
                order=order,
                cancelled_by=request.user.username,
                reason=request.data.get("reason", ""),
            )
        except services.OrderStateError as e:
            return Response({"detail": str(e)}, status=409)
        return Response(FileRetrievalOrderSerializer(order).data)


class RetrievedFileDownload(APIView):
    """Descarga un archivo recuperado (descifrado al vuelo por el storage)."""

    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def get(self, request, pk, file_id):
        order = get_object_or_404(
            FileRetrievalOrder.objects.filter_by_role(request.user), pk=pk
        )
        rf = get_object_or_404(order.files, pk=file_id)
        if not rf.asset:
            return Response({"detail": "el archivo no tiene contenido"}, status=404)
        resp = FileResponse(rf.asset.open("rb"), as_attachment=True)
        return resp


class EraseCertificateList(APIView):
    permission_classes = [IsAuthenticated, ViewEraseCertificatesPerms]

    def get(self, request):
        qs = EraseCertificate.objects.filter_by_role(request.user).order_by("-id")
        # La pestaña de la ficha del activo recorta al equipo con `?agent_id=` (el
        # identificador público del agente, no el pk). Sin el filtro, el listado
        # general devuelve todo lo que el rol ya autoriza (reportería, RF-C).
        agent_id = request.query_params.get("agent_id")
        if agent_id:
            qs = qs.filter(agent__agent_id=agent_id)
        return Response(EraseCertificateListSerializer(qs, many=True).data)


class EraseCertificateDetail(APIView):
    permission_classes = [IsAuthenticated, ViewEraseCertificatesPerms]

    def get(self, request, pk):
        cert = get_object_or_404(
            EraseCertificate.objects.filter_by_role(request.user), pk=pk
        )
        data = EraseCertificateDetailSerializer(cert).data
        data["verification"] = cert_mod.verify_certificate(cert)
        return Response(data)


class EraseCertificatePDF(APIView):
    permission_classes = [IsAuthenticated, ViewEraseCertificatesPerms]

    def get(self, request, pk):
        cert = get_object_or_404(
            EraseCertificate.objects.filter_by_role(request.user), pk=pk
        )
        pdf = cert_mod.render_pdf(cert)
        resp = FileResponse(iter([pdf]), content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="{cert.certificate_id}.pdf"'
        )
        return resp


class EraseCertificateJSON(APIView):
    permission_classes = [IsAuthenticated, ViewEraseCertificatesPerms]

    def get(self, request, pk):
        cert = get_object_or_404(
            EraseCertificate.objects.filter_by_role(request.user), pk=pk
        )
        return Response(cert_mod.certificate_json(cert))


class EraseSigningKey(APIView):
    """Publica la clave PÚBLICA con la que se firman los certificados.

    🔑 Sin esto la firma es decorativa fuera de Observer. Quien recibe un
    certificado tiene `signature.value`, `algorithm` y `key_id`, pero **ninguna
    llave contra la cual verificar**: lo único que puede comprobar solo —recalcular
    el `document_hash`— prueba consistencia interna, no autoría. `public_key_pem()`
    existía en las dos implementaciones de `Signer` desde la 039 y **no se llamaba
    desde ninguna parte**.

    Sin autenticación a propósito: el destinatario de un certificado es un tercero
    —un cliente, un auditor, un tribunal— que no tiene cuenta en la consola. Lo que
    se expone es una clave pública, que no es un secreto; publicarla es justamente
    su función. La clave privada vive en `ERASE_SIGNING_KEY` y no sale de acá.

    Si la instancia no tiene clave configurada, lo **dice** en lugar de devolver un
    404 ambiguo o una respuesta vacía: es el mismo criterio con el que ya se emite
    un certificado sin firma declarándolo.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        signer = signing.get_signer()
        if signer is None:
            return Response(
                {
                    "available": False,
                    "detail": "esta instancia no tiene clave de firma configurada; "
                    "los certificados que emite no van firmados y lo declaran en "
                    "su propio bloque de firma",
                    "key_id": "",
                    "algorithm": "",
                    "public_key_pem": "",
                }
            )
        return Response(
            {
                "available": True,
                "key_id": signer.key_id(),
                "algorithm": signer.alg,
                "public_key_pem": signer.public_key_pem(),
                "verification": (
                    "El campo firmado es el JSON canónico del documento: "
                    "json.dumps(document, sort_keys=True, separators=(',', ':'), "
                    "ensure_ascii=False).encode('utf-8'). `document_hash` es su "
                    "SHA-256 en hexadecimal y `signature.value` es la firma RSA-PSS "
                    "(MGF1-SHA256) de esos mismos bytes, en base64. El salt es el "
                    "MÁXIMO que admite la clave, no el largo del digest: con "
                    "openssl hay que verificar con 'rsa_pss_saltlen:-2' (auto) o "
                    "'max'; con '-1' falla una firma válida."
                ),
                "verification_openssl": (
                    "openssl dgst -sha256 -verify clave.pem "
                    "-sigopt rsa_padding_mode:pss -sigopt rsa_pss_saltlen:-2 "
                    "-signature firma.bin documento-canonico.bin"
                ),
            }
        )


class AssetIntakeList(APIView):
    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def get(self, request):
        qs = AssetIntake.objects.filter_by_role(request.user).order_by("-created_at")
        return Response(AssetIntakeSerializer(qs, many=True).data)

    def post(self, request):
        s = AssetIntakeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        intake = s.save(
            process_id=f"OE-IN-{uuid.uuid4().hex[:10].upper()}",
            received_by=request.user.username,
        )
        return Response(AssetIntakeSerializer(intake).data, status=201)


def _sha256_archivo(archivo) -> str:
    """SHA-256 del adjunto, leído por bloques y dejando el puntero al inicio.

    Por bloques y no de un `read()`: el tope son 15 MiB, pero cargarlo entero en
    memoria por cada certificación es gratuito de evitar. El `seek(0)` del final
    es obligatorio — sin él el `FileField` guardaría un archivo de 0 bytes.
    """
    h = hashlib.sha256()
    for bloque in archivo.chunks(64 * 1024):
        h.update(bloque)
    archivo.seek(0)
    return h.hexdigest()


class AssetIntakeCertifyDestruction(APIView):
    """Emite el certificado de destrucción física (C7) para un activo ingresado.

    Es el flujo de valor inmediato: no necesita el Bloque A ni el Bloque B —
    certifica la destrucción física manual que hoy ya se hace sin certificado.

    🔑 El veredicto se DERIVA de lo acreditado, no se asume. Hasta la feature 053
    esta vista emitía `verification_result="PASS"` fijo en el código: era el único
    punto del módulo que atestiguaba algo que no había verificado. Ahora `PASS`
    exige método acreditado Y testigo nombrado; si no, el documento declara
    `NOT_VERIFIED` y lo dice con todas las letras en el PDF.
    """

    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def post(self, request, pk):
        intake = get_object_or_404(
            AssetIntake.objects.filter_by_role(request.user), pk=pk
        )
        s = CertifyDestructionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data

        metodo_verif = datos.get("verification_method") or ""
        testigo = (datos.get("concurrence_name") or "").strip()
        # Acreditado = declaró un método distinto de "ninguno" Y nombró a alguien
        # que da fe. Una sola de las dos no alcanza: un método sin testigo no
        # tiene quién lo sostenga, y un testigo sin método no dice qué presenció.
        acreditado = bool(
            metodo_verif and metodo_verif != DestructionVerification.NONE and testigo
        )

        # La evidencia se guarda ANTES de emitir, para poder citar su hash dentro
        # del documento firmado. Vive en tabla propia y es purgable: el
        # certificado conserva el hash, no el archivo, así que la retención puede
        # borrar la foto sin invalidar —ni tocar— el documento inmutable.
        evidencia = None
        archivo = datos.get("evidence_file")
        if archivo is not None:
            evidencia = DestructionEvidence(
                intake=intake,
                original_name=(archivo.name or "")[:255],
                size=archivo.size or 0,
                sha256=_sha256_archivo(archivo),
                uploaded_by=request.user.username,
            )
            evidencia.asset = archivo
            evidencia.save()

        concurrence = {
            "name": testigo,
            "role": datos.get("concurrence_role") or "",
            "contact": datos.get("concurrence_contact") or "",
            "at": timezone.now().isoformat() if testigo else "",
        }

        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=intake.client,
            site=intake.site,
            agent=intake.agent,
            intake=intake,
            tenant=intake.client.name,
            asset_tag=intake.asset_tag,
            ticket_ref=intake.ticket_ref,
            # Acá no hay agente del cual leer inventario —una destrucción física
            # puede ser de un disco suelto—, así que el equipo sale de lo que el
            # técnico tecleó al recibirlo.
            equipment={
                "make": intake.equipment_make,
                "model": intake.equipment_model,
                "make_model": " ".join(
                    x for x in (intake.equipment_make, intake.equipment_model) if x
                ),
                "serial": intake.equipment_serial,
                "media_serial": intake.media_serial,
                "hostname": getattr(intake.agent, "hostname", "") or "",
            },
            method_applied=datos.get("method") or "destrucción física",
            standard_ref=cert_mod.STANDARD_REF_DESTROY,
            verification_result=(
                cert_mod.VERIFICATION_PASS
                if acreditado
                else cert_mod.VERIFICATION_NOT_VERIFIED
            ),
            verification_method=metodo_verif,
            verification_evidence=datos.get("verification_evidence") or "",
            operator=datos.get("operator") or request.user.username,
            concurrence=concurrence,
            media_disposition=intake.media_disposition,
            media_disposition_detail=intake.media_disposition_detail,
            actor=request.user.username,
            extra={
                "destruction_reason": datos.get("reason", ""),
                # El hash viaja DENTRO del documento firmado: sobrevive a la purga
                # del adjunto y permite comprobar, si alguien conserva una copia,
                # que es la misma que el certificado citó.
                "evidence_sha256": evidencia.sha256 if evidencia else "",
                "evidence_filename": evidencia.original_name if evidencia else "",
            },
        )
        return Response(EraseCertificateDetailSerializer(cert).data, status=201)
