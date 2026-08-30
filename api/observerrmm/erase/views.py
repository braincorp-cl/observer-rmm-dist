import uuid

from django.db.models import Max
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agents.models import Agent, LostModeEvidence, LostModeState
from erase import certificate as cert_mod
from erase import services
from erase.models import (
    AssetIntake,
    CertificateKind,
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

    Se ancla a un caso perdido abierto (RF-G06): el `lost_mode_cycle` vigente. La
    orden no viaja al equipo por sí sola — exige una segunda persona y la ventana
    de arrepentimiento, y el despacho sigue GATED por ADR-029.
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

        order = services.create_order(
            agent=agent,
            client=agent.site.client,
            site=agent.site,
            action=action,
            ordered_by=request.user.username,
            scope=scope,
            dry_run=s.validated_data.get("dry_run", True),
            reason=s.validated_data["reason"],
            lost_mode_cycle=s.validated_data.get("lost_mode_cycle"),
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
        return Response(
            WipePathTemplateSerializer(qs.order_by("name"), many=True).data
        )


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

    Anclada a un caso perdido ABIERTO (RF-G06/RN-01): exige un `LostModeState`
    activo para el equipo — imposible ordenar desde el listado general. No es
    destructiva: no hay doble confirmación ni ventana; el permiso liviano
    `can_retrieve_files` la gobierna.
    """

    permission_classes = [IsAuthenticated, RetrieveFilesPerms]

    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, agent_id=agent_id)

        # RF-G06: sólo desde un caso perdido abierto.
        if not LostModeState.objects.filter(agent=agent, active=True).exists():
            return Response(
                {
                    "detail": "no hay un caso perdido abierto para este equipo; "
                    "fileretrieval se ordena desde el caso, no desde el listado "
                    "general (RF-G06)"
                },
                status=409,
            )

        s = FileRetrievalOrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        cycle = (
            LostModeEvidence.objects.filter(agent=agent).aggregate(m=Max("cycle"))["m"]
            or 0
        )
        try:
            order = services.create_retrieval_order(
                agent=agent,
                client=agent.site.client,
                site=agent.site,
                paths=s.validated_data["paths"],
                requested_by=request.user.username,
                dry_run=s.validated_data.get("dry_run", False),
                lost_mode_cycle=cycle,
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


class AssetIntakeCertifyDestruction(APIView):
    """Emite el certificado de destrucción física (C7) para un activo ingresado.

    Es el flujo de valor inmediato: no necesita el Bloque A ni el Bloque B —
    certifica la destrucción física manual que hoy ya se hace sin certificado.
    """

    permission_classes = [IsAuthenticated, ManageAssetIntakePerms]

    def post(self, request, pk):
        intake = get_object_or_404(
            AssetIntake.objects.filter_by_role(request.user), pk=pk
        )
        s = CertifyDestructionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cert = cert_mod.issue_certificate(
            kind=CertificateKind.PHYSICAL_DESTRUCTION,
            client=intake.client,
            site=intake.site,
            agent=intake.agent,
            intake=intake,
            tenant=intake.client.name,
            asset_tag=intake.asset_tag,
            ticket_ref=intake.ticket_ref,
            equipment={
                "serial": intake.equipment_serial,
                "media_serial": intake.media_serial,
            },
            method_applied=s.validated_data.get("method") or "destrucción física",
            standard_ref="NIST 800-88 Rev.1 Destroy",
            verification_result="PASS",
            operator=s.validated_data.get("operator") or request.user.username,
            actor=request.user.username,
            extra={"destruction_reason": s.validated_data.get("reason", "")},
        )
        return Response(EraseCertificateDetailSerializer(cert).data, status=201)
