import hashlib
import uuid

from datetime import datetime, time

from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agents.models import Agent
from core.utils import get_core_settings
from erase import certificate as cert_mod
from erase import services, signing
from erase.models import (
    AssetIntake,
    CertificateKind,
    CustodyEvent,
    CustodyEventKind,
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
    CustodyEventCreateSerializer,
    CustodyEventSerializer,
    EraseAuditRecordSerializer,
    EraseCertificateDetailSerializer,
    EraseCertificateListSerializer,
    FileRetrievalOrderCreateSerializer,
    FileRetrievalOrderSerializer,
    ReconciliationSerializer,
    RetrievedFileSerializer,
    WipeOrderCancelSerializer,
    WipeOrderConfirmSerializer,
    WipeOrderCreateSerializer,
    WipeOrderSerializer,
    WipePathTemplateSerializer,
)
from logs.models import AuditLog
from observerrmm.middleware import get_debug_info
from observerrmm.throttles import VerifyDayThrottle, VerifyMinThrottle


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

        # Feature 055 · RF-10. `crypto_erase` existe en el enum desde la 039 y
        # HOY ES INCUMPLIBLE: no hay vía remota que destruya la clave de un
        # medio. Se midió en staging el 2026-11-01 que quitar el único
        # protector del cifrado del sistema operativo deja la clave maestra del
        # volumen EN CLARO y el dato legible — implementarlo así no sólo no
        # borra: empeora la seguridad del equipo.
        #
        # 🔑 Se bloquea acá, en la puerta HTTP, y no retirando el valor del
        # enum: hay órdenes históricas que lo referencian y una columna no
        # puede dejar de admitir lo que ya guardó. La vista cubre consola, API
        # y llave de integración, que son las tres puertas que existen.
        if action == EraseAction.CRYPTO_ERASE:
            return Response(
                {
                    "detail": (
                        "El crypto-erase remoto no está disponible: ningún medio "
                        "inventariado lo sostiene. Exige un disco autocifrado y "
                        "una vía que destruya su clave, que el endpoint con el "
                        "sistema operativo vivo no puede ofrecer."
                    )
                },
                status=409,
            )

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
        # La traza se escribe ANTES de abrir el archivo y entregar la respuesta:
        # `FileResponse` se consume fuera de la vista (el WSGI itera el cuerpo
        # después del return) y `AuditMiddleware` ya limpió `request_local` para
        # entonces, así que una fila escrita más tarde perdería el `debug_info`
        # —y, si el streaming falla, no quedaría fila de un archivo que el
        # servidor sí abrió y empezó a mandar.
        AuditLog.audit_retrieved_file_download(
            username=request.user.username,
            order=order,
            retrieved_file=rf,
            debug_info=get_debug_info(),
        )
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
        # Mismo motivo que en la descarga del archivo recuperado: la fila se
        # escribe acá, con el `debug_info` del request todavía puesto.
        AuditLog.audit_erase_certificate_pdf(
            username=request.user.username,
            certificate=cert,
            debug_info=get_debug_info(),
        )
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
        # 🔑 Entrega EL MISMO documento firmado que el PDF, en otro formato. Si
        # sólo auditara el PDF, bajarse el certificado sin dejar traza sería
        # cambiar de botón: la consola llama este endpoint desde
        # `web/app/src/api/erase.js:46`, así que el hueco estaba al alcance de
        # cualquiera, no era teórico.
        #
        # Se reusa `audit_erase_certificate_pdf` a propósito en vez de abrir un
        # método gemelo: lo que importa auditar es **el acceso al certificado**,
        # no el formato en que salió. Distinguirlos pediría una categoría nueva
        # en `AuditActionType`, que es un `AlterField` sobre `choices`.
        AuditLog.audit_erase_certificate_pdf(
            username=request.user.username,
            certificate=cert,
            debug_info=get_debug_info(),
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
        claves = signing.public_keys()
        if not claves:
            return Response(
                {
                    "available": False,
                    "detail": "esta instancia no tiene clave de firma configurada; "
                    "los certificados que emite no van firmados y lo declaran en "
                    "su propio bloque de firma",
                    "key_id": "",
                    "algorithm": "",
                    "public_key_pem": "",
                    "keys": [],
                }
            )
        activa = claves[0]
        return Response(
            {
                "available": True,
                # `keys` es el contrato nuevo: TODAS las claves publicables, con su
                # `key_id` y si está activa o retirada. El destinatario toma la que
                # declara el `signature.key_id` de su certificado. Los tres campos
                # sueltos de abajo describen la ACTIVA y se mantienen para no romper
                # a quien ya los consuma.
                "keys": claves,
                "key_id": activa["key_id"],
                "algorithm": activa["algorithm"],
                "public_key_pem": activa["public_key_pem"],
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


class EraseCertificateVerify(APIView):
    """Verificación PÚBLICA de un certificado (053 · ola 4 · RF-08 · CA-08).

    La vía offline —`GET /erase/signing-key/`, entregada en la ola 1— ya permite
    a un tercero probar la **autoría** de la firma sin preguntarle nada a nadie.
    Lo que no puede comprobar solo es el **encadenamiento**: que el certificado
    siga siendo el eslabón que fue dentro del repositorio inmutable de este
    tenant. Eso es lo único que agrega este endpoint, y de ahí su forma.

    🔒 **No hay 404 ni 400 por el identificador.** Exista o no, tenga o no la
    forma correcta, la respuesta es 200 con **las mismas claves**: dos códigos de
    estado distintos convierten el endpoint en un oráculo de existencia y
    permiten barrer el espacio de identificadores contando respuestas, sin leer
    un solo cuerpo (CA-08).

    🔒 **La respuesta es mínima y cerrada** (L-02): identificador, tipo, fecha y
    los tres veredictos. Ni cliente, ni equipo, ni serial, ni operador, ni
    testigo, ni el documento. Quien verifica **ya tiene el certificado en la
    mano**; el portal sólo confirma que es auténtico. Si respondiera más,
    enumerar identificadores permitiría armar el inventario de bajas de un
    cliente.

    🔑 La defensa principal **no** es el límite de tasa: son los 40 bits de
    `new_certificate_id()` y el hecho de que acertar uno no diga de quién es.

    Apagado el interruptor (`CoreSettings.erase_public_verify_enabled`, que nace
    en `False`), la ruta responde 404 y no nombra la función. El matiz honesto:
    `/erase/signing-key/` es público e incondicional, así que la presencia del
    módulo ya es observable; lo que este 404 protege es que esta instalación no
    participe del portal, no la existencia del producto.
    """

    permission_classes = [AllowAny]
    throttle_classes = [VerifyMinThrottle, VerifyDayThrottle]

    def get(self, request, certificate_id):
        if not get_core_settings().erase_public_verify_enabled:
            raise Http404

        # `certificate_id` es unique: una búsqueda por índice, no un recorrido.
        cert = EraseCertificate.objects.filter(certificate_id=certificate_id).first()

        # El MISMO diccionario con y sin resultado. No se arma en dos ramas a
        # propósito: dos ramas divergen, y acá divergir es filtrar.
        respuesta = {
            "found": cert is not None,
            "certificate_id": certificate_id,
            "kind": cert.kind if cert else "",
            "issued_at": cert.created_at if cert else None,
            "document_intact": False,
            "signature_valid": False,
            "signature_present": False,
            "chain_intact": False,
            "valid": False,
        }
        if cert is not None:
            # La MISMA función que usa la consola. Una verificación «ligera»
            # propia del portal sería el peor lugar posible para que divergiera.
            veredicto = cert_mod.verify_certificate(cert)
            for clave in (
                "document_intact",
                "signature_valid",
                "signature_present",
                "chain_intact",
                "valid",
            ):
                respuesta[clave] = veredicto[clave]
        return Response(respuesta)


class AssetIntakeList(APIView):
    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def get(self, request):
        qs = AssetIntake.objects.filter_by_role(request.user).order_by("-created_at")
        return Response(AssetIntakeSerializer(qs, many=True).data)

    def post(self, request):
        s = AssetIntakeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        # El acta y su primer eslabón nacen juntos o no nacen (RF-06). Si el
        # `received` fuera opcional, la cadena de custodia arrancaría en el aire
        # y el origen del medio (RF-09) no tendría de dónde salir.
        with transaction.atomic():
            intake = s.save(
                process_id=f"OE-IN-{uuid.uuid4().hex[:10].upper()}",
                received_by=request.user.username,
            )
            services.record_custody_event(
                intake=intake,
                kind=CustodyEventKind.RECEIVED,
                actor=request.user.username,
                # Cuándo entró a custodia, que puede ser anterior a cuándo se
                # tecleó el acta.
                at=intake.received_at or intake.created_at,
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

        # Feature 055 · si el acta enlaza un equipo, el inventario sabe qué medio
        # tiene y el documento lo publica. Devuelve vacío cuando no hay equipo
        # —una destrucción física puede ser de un disco suelto— y eso es «no
        # consta», no un dato inventado.
        #
        # 🔑 Acá el medio pesa MÁS que en el certificado de borrado remoto: lo que
        # se destruyó es el medio, no el equipo. Esta vista nacía sin él porque la
        # 053 asumió que una destrucción física nunca tiene agente del cual leer;
        # el acta sí puede enlazarlo desde esa misma ola, y entonces el dato está
        # y callarlo es perderlo.
        media_snapshot, capacity_reported, media_type_measured = (
            services.snapshot_del_medio(intake.agent)
        )

        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=intake.client,
            site=intake.site,
            agent=intake.agent,
            intake=intake,
            tenant=intake.client.name,
            asset_tag=intake.asset_tag,
            ticket_ref=intake.ticket_ref,
            media=media_snapshot,
            capacity_reported=capacity_reported,
            media_type_measured=media_type_measured,
            # El EQUIPO sale de lo que el técnico tecleó al recibirlo, no del
            # inventario: el documento describe el activo que entró en custodia,
            # y esa es la descripción que la persona firmó en el acta.
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
            # RF-09: el tipo lo tecleó quien recibió; el origen se compone del
            # acta, no del lugar donde se almacenó el activo.
            media_type=intake.media_type,
            media_origin=services.compose_media_origin(intake),
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


def parse_datetime_param(valor):
    """Un `from`/`to` del contrato HTTP a datetime con zona.

    Acepta fecha sola (`2026-07-01`) y fecha con hora. Una cadena que no es
    ninguna de las dos lanza `ValueError`, que la vista traduce a 400: un filtro
    ilegible que se ignora en silencio daría un informe que no es el pedido.
    """
    if not valor:
        return None

    dt = parse_datetime(valor)
    if dt is None:
        fecha = parse_date(valor)
        if fecha is None:
            raise ValueError(f"'{valor}' no es una fecha válida (AAAA-MM-DD)")
        dt = datetime.combine(fecha, time.min)

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


class AssetIntakeDetail(APIView):
    """El expediente de un activo (feature 053 · ola 2).

    No existía: la consola sólo podía listar actas, así que no había desde dónde
    abrir una para ver su línea de tiempo.
    """

    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def get(self, request, pk):
        intake = get_object_or_404(
            AssetIntake.objects.filter_by_role(request.user), pk=pk
        )
        return Response(AssetIntakeSerializer(intake).data)


class IntakeCustodyEvents(APIView):
    """La cadena de custodia de un acta: leerla y agregarle un eslabón (RF-06).

    🔒 No hay `PUT`, `PATCH` ni `DELETE`, y no es un olvido: un eslabón es
    inmutable. Corregir un error se hace **añadiendo** un evento, no
    reescribiendo el anterior.

    Autenticado y con el mismo permiso que gobierna el acta. No hay variante
    pública: enumerar la custodia de un cliente es justamente lo que L-02
    prohibió para el verificador.
    """

    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def _acta(self, request, pk) -> AssetIntake:
        # 404 y no 403 fuera del alcance de rol: que exista un acta ajena no es
        # información que esta vista deba filtrar.
        return get_object_or_404(
            AssetIntake.objects.filter_by_role(request.user), pk=pk
        )

    def get(self, request, pk):
        intake = self._acta(request, pk)
        eventos = CustodyEvent.objects.filter(intake=intake).order_by("id")
        return Response(
            {
                "intake": {
                    "id": intake.pk,
                    "process_id": intake.process_id,
                    "equipment_serial": intake.equipment_serial,
                },
                "chain_intact": services.verify_custody_chain(intake),
                "events": CustodyEventSerializer(eventos, many=True).data,
            }
        )

    def post(self, request, pk):
        intake = self._acta(request, pk)
        s = CustodyEventCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = s.validated_data

        try:
            evento = services.record_custody_event(
                intake=intake,
                kind=datos["kind"],
                # El actor lo pone el servidor: aceptarlo del cliente permitiría
                # firmar un traslado a nombre de otro.
                actor=request.user.username,
                at=datos.get("at"),
                location=datos.get("location", ""),
                detail=datos.get("detail") or {},
            )
        except services.CustodyEventError as e:
            # 409 y no 400: el cuerpo es válido, lo que choca es el estado del
            # expediente. Mismo código que ya usa la guardia de fileretrieval.
            return Response({"detail": str(e)}, status=409)

        return Response(CustodyEventSerializer(evento).data, status=201)


class ReconciliationReport(APIView):
    """Ingresados, certificados y faltantes por cliente y período (RF-07).

    🔒 **Nunca público.** Responder esto sin cuenta permitiría armar el
    inventario de bajas de un cliente — la misma razón por la que L-02 recortó
    el verificador público al mínimo.

    El alcance de rol se aplica **antes** de agregar, para que los totales
    cuadren con lo que el usuario puede abrir.
    """

    permission_classes = [IsAuthenticated, ViewEraseCertificatesPerms]

    def get(self, request):
        p = request.query_params
        try:
            informe = services.reconciliation(
                qs=AssetIntake.objects.filter_by_role(request.user),
                client=p.get("client") or None,
                desde=parse_datetime_param(p.get("from")),
                hasta=parse_datetime_param(p.get("to")),
                stalled_days=int(p["stalled_days"]) if p.get("stalled_days") else None,
                limit=int(p["limit"]) if p.get("limit") else None,
                offset=int(p["offset"]) if p.get("offset") else 0,
            )
        except (services.CustodyEventError, ValueError) as e:
            return Response({"detail": str(e)}, status=400)

        return Response(ReconciliationSerializer(informe).data)
