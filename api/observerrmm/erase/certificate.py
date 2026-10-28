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
import html
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

SCHEMA_VERSION = "observer-erase-cert/2"

# Referencias de la norma VIGENTE. La Rev. 1 de NIST SP 800-88 quedó retirada al
# publicarse la Rev. 2 (sept-2025), e IEEE 2883-2022 es la que define hoy las
# técnicas por tipo de medio. Un certificado que cita una norma retirada es
# atacable justo por donde tiene que sostenerse.
STANDARD_REF_CLEAR = "NIST SP 800-88 Rev. 2 (Clear) · IEEE 2883-2022"
STANDARD_REF_DESTROY = "NIST SP 800-88 Rev. 2 (Destroy) · IEEE 2883-2022"

# Veredicto de verificación. `NOT_VERIFIED` tiene 12 caracteres y cabe en el
# `max_length=16` de `EraseCertificate.verification_result`, así que no hace falta
# migración. Es un valor que el documento DECLARA, no un hueco: afirmar `PASS` sin
# haber comprobado nada es el único punto donde el módulo podría mentir.
VERIFICATION_PASS = "PASS"
VERIFICATION_NOT_VERIFIED = "NOT_VERIFIED"

# El bloque de concurrencia (Apéndice C) se emite SIEMPRE con sus cuatro claves,
# vacías si no hubo segunda persona: un campo vacío declara "no consta", uno
# ausente es ambiguo y deja al lector adivinando si el dato se perdió.
EMPTY_CONCURRENCE = {"name": "", "role": "", "contact": "", "at": ""}

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
    verification_method: str = "",
    verification_evidence: str = "",
    operator: str = "",
    concurrence: Optional[Dict[str, Any]] = None,
    media_disposition: str = "",
    media_disposition_detail: str = "",
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
        # CÓMO se verificó, no solo el veredicto: un "PASS" sin método acreditado
        # no es verificación, es una afirmación.
        "verification_method": verification_method,
        "verification_evidence": verification_evidence,
        "operator": operator,
        # Segunda persona que da fe (Concurrence del Apéndice C). Separada del
        # operador a propósito: si fueran la misma, el documento mostraría a
        # alguien dando fe de su propio trabajo.
        "concurrence": {**EMPTY_CONCURRENCE, **(concurrence or {})},
        # Destino final del medio: el mínimo de la norma no se conforma con decir
        # que se saneó, exige declarar dónde quedó.
        "media_disposition": media_disposition,
        "media_disposition_detail": media_disposition_detail,
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
.nover { background: #fdf2e0; color: #8a5a10; }
.na { color: #8a97a5; }
.sig { margin-top: 16px; font-size: 9px; color: #5a6a7a; word-break: break-all; }
.foot { margin-top: 22px; font-size: 9px; color: #8a97a5; }
"""

_KIND_LABEL = {
    CertificateKind.REMOTE_DESTRUCTION: "Certificado de destrucción remota",
    CertificateKind.PHYSICAL_DESTRUCTION: "Certificado de destrucción física",
}


# Celda vacia, con la misma clase que usa `_row`. Como constante y no inline:
# escrita dentro de una f-string delimitada por comillas dobles habria que
# escapar las del atributo, y `class=&quot;na&quot;` deja la clase sin aplicar.
NA_HTML = "<span class='na'>N/A</span>"


def _row(label: str, value: Any) -> str:
    """Una fila de la tabla, con el valor ESCAPADO.

    🔒 Desde el v2 entran al documento el nombre del testigo, el detalle del
    destino del medio y la nota de verificación, todos tecleados por el operador.
    Sin escapar, van crudos al HTML que renderiza WeasyPrint. Escapar no afecta
    ni al hash ni a la firma: ambos se calculan sobre el JSON canónico, y el PDF
    se re-renderiza del documento.
    """
    if value in (None, "", []):
        return f"<tr><th>{label}</th><td class='na'>N/A</td></tr>"
    return f"<tr><th>{label}</th><td>{html.escape(str(value))}</td></tr>"


def render_html(cert: EraseCertificate) -> str:
    d = cert.data
    equipment = d.get("equipment") or {}
    # `make_model` es lo que trae el inventario del agente en una sola cadena;
    # make/model separados vienen del acta, tecleados al recibir el activo. Se
    # usa lo que haya, sin repetir el fabricante si ya viene dentro del combinado.
    equip_txt = html.escape(
        " · ".join(
            str(v)
            for v in (
                equipment.get("make_model")
                or " ".join(
                    str(x) for x in (equipment.get("make"), equipment.get("model")) if x
                ),
                equipment.get("serial"),
            )
            if v
        )
    )
    verif = d.get("verification_result") or ""
    conc = d.get("concurrence") or {}
    if verif.upper() == VERIFICATION_PASS:
        verif_html = f"<span class='chip pass'>{html.escape(verif)}</span>"
    elif verif.upper() == VERIFICATION_NOT_VERIFIED:
        # Se dice con todas las letras. El chip neutro evita que un lector apurado
        # lo confunda con un visto bueno.
        verif_html = (
            "<span class='chip nover'>SIN VERIFICACIÓN ACREDITADA</span>"
            "<div class='na'>La destrucción no fue presenciada ni registrada; "
            "este certificado no afirma haberla comprobado.</div>"
        )
    else:
        verif_html = html.escape(verif) if verif else NA_HTML
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
            # No usa `_row` porque `equip_txt` ya viene escapado y volver a
            # escaparlo convertiria el separador en entidades.
            f"<tr><th>Equipo</th><td>{equip_txt or NA_HTML}</td></tr>",
            _row("Nombre de red del equipo", equipment.get("hostname")),
            _row("Método aplicado", d.get("method_applied")),
            _row("Estándar de referencia", d.get("standard_ref")),
            f"<tr><th>Resultado de verificación</th><td>{verif_html}</td></tr>",
            _row("Cómo se verificó", d.get("verification_method")),
            _row("Constancia de la verificación", d.get("verification_evidence")),
            _row("Destino final del medio", d.get("media_disposition")),
            _row("Detalle del destino", d.get("media_disposition_detail")),
            _row("Operador responsable", d.get("operator")),
            _row("Da fe (segunda persona)", conc.get("name")),
            _row("Cargo de quien da fe", conc.get("role")),
            _row("Contacto de quien da fe", conc.get("contact")),
            _row("Fecha en que dio fe", conc.get("at")),
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
