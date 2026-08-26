"""Generación del certificado de borrado — documento canónico, firma, PDF (C1/C2).

El certificado es un par **JSON + PDF cubiertos por la misma firma**. El JSON es la
fuente: se arma un documento canónico, se calcula su `document_hash`, se firma ese
documento y se emite la fila inmutable `EraseCertificate` (que además lo encadena
en el repositorio C3). El PDF se re-renderiza del mismo documento cuando se pide,
así que no se persiste el blob.

**Encuadre honesto (sin Bloque B).** Este generador certifica destrucción remota
(acciones del Bloque A) o destrucción física manual (C7). Los campos propios del
borrado de disco fin-de-vida (método ATA/NVMe, SMART, verificación por relectura de
sectores, HPA/DCO) se emiten como `null`/`"N/A"` con la nota de que aplican al
Bloque B. Cuando B exista, llena esos campos con el mismo esquema.
"""

import hashlib
import json
import uuid
from typing import Any, Dict, Optional

from django.utils import timezone

from erase import signing
from erase.models import (
    CertificateKind,
    EraseAuditRecord,
    EraseCertificate,
)

SCHEMA_VERSION = "observer-erase-cert/1"

# Campos que sólo el Bloque B (imagen live de borrado de disco) puede llenar. Se
# emiten explícitos como N/A para que el certificado no mienta por omisión.
B_ONLY_NA = {
    "media": None,
    "capacity_reported": None,
    "capacity_erased": None,
    "hpa_dco_detected": "N/A (requiere Bloque B — imagen live)",
    "passes": None,
    "patterns": None,
    "verification_level": "N/A (requiere Bloque B)",
    "bad_sectors": None,
    "smart_summary": None,
    "environment_hash": None,
}


def new_certificate_id() -> str:
    fecha = timezone.now().strftime("%Y%m%d")
    return f"OE-{fecha}-{uuid.uuid4().hex[:10].upper()}"


def canonical_bytes(document: Dict[str, Any]) -> bytes:
    """Bytes canónicos que se firman y se hashean. Determinista y estable."""
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def build_document(
    *,
    certificate_id: str,
    kind: str,
    tenant: str,
    asset_tag: str = "",
    ticket_ref: str = "",
    equipment: Optional[Dict[str, Any]] = None,
    method_applied: str = "",
    standard_ref: str = "",
    verification_result: str = "",
    operator: str = "",
    started_at: str = "",
    finished_at: str = "",
    last_known_location: Optional[Dict[str, Any]] = None,
    software_version: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    document: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "certificate_id": certificate_id,
        "kind": kind,
        "ticket_ref": ticket_ref,
        "tenant": tenant,
        "asset_tag": asset_tag,
        "equipment": equipment or {},
        "method_applied": method_applied,
        "standard_ref": standard_ref,
        "verification_result": verification_result,
        "operator": operator,
        "started_at": started_at,
        "finished_at": finished_at,
        "last_known_location": last_known_location,
        "software_version": software_version,
    }
    document.update(B_ONLY_NA)
    if extra:
        document.update(extra)
    return document


def issue_certificate(
    *,
    kind: str,
    client,
    tenant: str = "",
    site=None,
    agent=None,
    order=None,
    intake=None,
    actor: str = "",
    **doc_fields: Any,
) -> EraseCertificate:
    """Emite un certificado: arma el documento, lo firma y crea la fila inmutable.

    Deja además un `EraseAuditRecord` de emisión encadenado. Todo dentro de la
    escritura append-only de cada store.
    """
    certificate_id = new_certificate_id()
    tenant = tenant or getattr(client, "name", "")

    document = build_document(
        certificate_id=certificate_id,
        kind=kind,
        tenant=tenant,
        **doc_fields,
    )

    canonical = canonical_bytes(document)
    document_hash = hashlib.sha256(canonical).hexdigest()
    signature_b64, alg, key_id = signing.sign_document(canonical)

    cert = EraseCertificate(
        certificate_id=certificate_id,
        kind=kind,
        order=order,
        intake=intake,
        client=client,
        site=site,
        agent=agent,
        tenant=tenant,
        asset_tag=doc_fields.get("asset_tag", ""),
        method_applied=doc_fields.get("method_applied", ""),
        standard_ref=doc_fields.get("standard_ref", ""),
        verification_result=doc_fields.get("verification_result", ""),
        operator=doc_fields.get("operator", ""),
        started_at=doc_fields.get("started_at") or None,
        finished_at=doc_fields.get("finished_at") or None,
        software_version=doc_fields.get("software_version", ""),
        data=document,
        document_hash=document_hash,
        signature=signature_b64,
        signature_alg=alg,
        signing_key_id=key_id,
    )
    cert.save()

    EraseAuditRecord(
        order=order,
        agent_id=getattr(agent, "agent_id", "") or "",
        hostname=getattr(agent, "hostname", "") or "",
        event="certificate_issued",
        actor=actor,
        detail={
            "certificate_id": certificate_id,
            "kind": kind,
            "document_hash": document_hash,
            "signed": bool(signature_b64),
        },
    ).save()

    return cert


def certificate_json(cert: EraseCertificate) -> Dict[str, Any]:
    """El par JSON del certificado: documento + bloque de firma verificable."""
    return {
        "document": cert.data,
        "document_hash": cert.document_hash,
        "signature": {
            "value": cert.signature,
            "algorithm": cert.signature_alg,
            "key_id": cert.signing_key_id,
        },
        "chain": {
            "prev_hash": cert.prev_hash,
            "record_hash": cert.record_hash,
        },
    }


def verify_certificate(cert: EraseCertificate) -> Dict[str, Any]:
    """Verifica documento (hash), firma y encadenado del certificado."""
    canonical = canonical_bytes(cert.data)
    doc_ok = hashlib.sha256(canonical).hexdigest() == cert.document_hash
    sig_ok = signing.verify_document(canonical, cert.signature)
    chain_ok = cert.record_hash == cert.compute_record_hash(cert.prev_hash)
    return {
        "certificate_id": cert.certificate_id,
        "document_intact": doc_ok,
        "signature_valid": sig_ok,
        "signature_present": bool(cert.signature),
        "chain_intact": chain_ok,
        "valid": doc_ok and chain_ok and (sig_ok or not cert.signature),
    }


# --- Render PDF -------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: 'DejaVu Sans', sans-serif; color: #1a2027; font-size: 11px; }
h1 { color: #0b5cad; font-size: 20px; margin-bottom: 0; }
.sub { color: #5a6a7a; font-size: 12px; margin-top: 2px; }
.meta { margin: 14px 0; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
th, td { text-align: left; padding: 5px 7px; border-bottom: 1px solid #dce3ea; vertical-align: top; }
th { width: 34%; color: #37475a; font-weight: 600; }
.chip { display: inline-block; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.pass { background: #e3f6e8; color: #1c7a3d; }
.na { color: #8a97a5; }
.sig { margin-top: 16px; font-size: 9px; color: #5a6a7a; word-break: break-all; }
.foot { margin-top: 22px; font-size: 9px; color: #8a97a5; }
"""

_KIND_LABEL = {
    CertificateKind.REMOTE_DESTRUCTION: "Certificado de destrucción remota",
    CertificateKind.PHYSICAL_DESTRUCTION: "Certificado de destrucción física",
}


def _row(label: str, value: Any) -> str:
    if value in (None, "", []):
        return f"<tr><th>{label}</th><td class='na'>N/A</td></tr>"
    return f"<tr><th>{label}</th><td>{value}</td></tr>"


def render_html(cert: EraseCertificate) -> str:
    d = cert.data
    equipment = d.get("equipment") or {}
    equip_txt = " · ".join(
        str(v)
        for v in (
            equipment.get("make"),
            equipment.get("model"),
            equipment.get("serial"),
        )
        if v
    )
    verif = d.get("verification_result") or ""
    verif_html = (
        f"<span class='chip pass'>{verif}</span>"
        if verif.upper() == "PASS"
        else (verif or "<span class='na'>N/A</span>")
    )
    title = _KIND_LABEL.get(cert.kind, "Certificado de borrado")
    signed_line = (
        f"Firmado — {cert.signature_alg}, key {cert.signing_key_id}"
        if cert.signature
        else "SIN FIRMA (ambiente sin clave configurada)"
    )
    rows = "".join(
        [
            _row("Identificador del certificado", cert.certificate_id),
            _row("Ticket de baja", d.get("ticket_ref")),
            _row("Cliente / organización", cert.tenant),
            _row("Etiqueta del activo", d.get("asset_tag")),
            _row("Equipo", equip_txt),
            _row("Método aplicado", d.get("method_applied")),
            _row("Estándar de referencia", d.get("standard_ref")),
            f"<tr><th>Resultado de verificación</th><td>{verif_html}</td></tr>",
            _row("Operador responsable", d.get("operator")),
            _row("Inicio", d.get("started_at")),
            _row("Fin", d.get("finished_at")),
            _row("Versión del software", d.get("software_version")),
            _row("Hash del documento", cert.document_hash),
        ]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"></head><body>
    <h1>Observer Erase</h1>
    <div class="sub">{title}</div>
    <div class="meta"><table>{rows}</table></div>
    <div class="sig">{signed_line}<br>Encadenamiento: prev={cert.prev_hash or '(génesis)'} · record={cert.record_hash}</div>
    <div class="foot">Documento generado por Observer Erase. Verificable por su identificador o hash.
    Los campos de borrado de disco de fin de vida (medio, SMART, HPA/DCO, verificación por sectores)
    aplican al módulo de imagen live y se emiten como N/A en este certificado.</div>
    </body></html>"""


def render_pdf(cert: EraseCertificate) -> bytes:
    from ee.reporting.utils import generate_pdf

    return generate_pdf(html=render_html(cert), css=_CSS)
