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

from django.conf import settings
from django.utils import timezone

from erase import signing
from erase.models import (
    CertificateKind,
    EraseAuditRecord,
    EraseCertificate,
)

SCHEMA_VERSION = "observer-erase-cert/3"

# Referencias de la norma VIGENTE. La Rev. 1 de NIST SP 800-88 quedó retirada al
# publicarse la Rev. 2 (sept-2025), e IEEE 2883-2022 es la que define hoy las
# técnicas por tipo de medio. Un certificado que cita una norma retirada es
# atacable justo por donde tiene que sostenerse.
#
# 🔑 El wipe NO cita la categoría «Clear», y la razón es la definición literal del
# glosario del r2: *clear* sanitiza «all user-addressable storage locations» — el
# MEDIO COMPLETO. Borrar rutas es la sanitización **selectiva/parcial** de la §4.2,
# donde el propio estándar advierte que es difícil verificar que el dato no se
# derramó (bloques remapeados, overprovisioning), prefiere sanitizar el medio
# entero siempre que se pueda, y da como único ejemplo de vía selectiva el
# cryptographic erase, no la sobrescritura.
#
# Declarar la técnica y el alcance, en vez de una categoría que no corresponde, es
# lo que mantiene creíble el resto del documento: un certificado que sobredeclara
# pierde todo su valor el día que alguien lo audita.
STANDARD_REF_SELECTIVE = (
    "Sanitización selectiva por sobrescritura "
    "(NIST SP 800-88 Rev. 2, §4.2) · IEEE 2883-2022"
)
STANDARD_REF_DESTROY = "NIST SP 800-88 Rev. 2 (Destroy) · IEEE 2883-2022"

# Alias retirado. `STANDARD_REF_CLEAR` nombraba una categoría que el wipe nunca
# alcanzó; se conserva apuntando al texto correcto para que nada que lo importe
# quede roto, pero no debe usarse en código nuevo.
STANDARD_REF_CLEAR = STANDARD_REF_SELECTIVE

# Lo que el documento dice que NO es. Va junto al alcance porque el límite es
# parte del dato: sin esta línea, «sanitización» invita a leer «el disco quedó
# limpio», que es justamente lo que no ocurrió.
SCOPE_DISCLAIMER_SELECTIVE = (
    "Alcance limitado a las rutas indicadas. NO constituye sanitización del "
    "medio (Clear/Purge/Destruct según NIST SP 800-88 Rev. 2 e IEEE 2883-2022): "
    "el resto del medio no fue alterado y puede conservar datos."
)

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
#
# 🔑 Feature 055 — `media` y `capacity_reported` SALIERON de acá. La afirmación
# era falsa para esos dos: son **inventario del medio**, no medición del
# borrado, y el agente los puede leer con el sistema operativo vivo. Lo que sí
# sigue exigiendo el Bloque B es todo lo que describe la OPERACIÓN sobre el
# medio completo: cuánto se borró de verdad, si había áreas ocultas, cuántas
# pasadas, qué patrones, qué sectores fallaron y en qué entorno corrió.
#
# `smart_summary` se queda acá por decisión y no por olvido: los contadores de
# fiabilidad son otra fuente, con otra latencia y otra discusión de retención.
B_ONLY_NA = {
    "capacity_erased": None,
    "hpa_dco_detected": "N/A (requiere Bloque B — imagen live)",
    "passes": None,
    "patterns": None,
    "verification_level": "N/A (requiere Bloque B)",
    "bad_sectors": None,
    "smart_summary": None,
    "environment_hash": None,
}


# Ruta del recurso que publica la clave pública de firma (feature 053 · RF-08).
SIGNING_KEY_PATH = "/erase/signing-key/"


def signing_key_url() -> str:
    """URL absoluta donde el destinatario obtiene la clave para verificar.

    Viaja DENTRO del documento, así que queda cubierta por la firma: un
    certificado alterado no puede apuntar a la clave de otro. Es lo que convierte
    la firma en algo verificable por un tercero — sin esto el destinatario tiene
    la firma y ninguna llave contra la cual probarla.

    Si el ambiente no declara dominio, se emite la ruta relativa en lugar de
    inventar un host: un `https://None/...` sería peor que decir menos.
    """
    hosts = getattr(settings, "ALLOWED_HOSTS", None) or []
    host = hosts[0] if hosts else ""
    if not host or host == "*":
        return SIGNING_KEY_PATH
    proto = getattr(settings, "ORMM_PROTO", "https")
    return f"{proto}://{host}{SIGNING_KEY_PATH}"


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
    # Lo que el certificado NO acredita. Se emite SIEMPRE, vacío cuando no aplica,
    # por el mismo criterio que el bloque de concurrencia: un campo vacío declara
    # "no consta", uno ausente deja al lector adivinando.
    scope_note: str = "",
    verification_result: str = "",
    verification_method: str = "",
    verification_evidence: str = "",
    operator: str = "",
    concurrence: Optional[Dict[str, Any]] = None,
    media_disposition: str = "",
    media_disposition_detail: str = "",
    media_type: str = "",
    media_origin: str = "",
    # Feature 055 · inventario del MEDIO, no del equipo. Nulo es "no consta",
    # que es lo que corresponde cuando no hay inventario: el certificado no
    # inventa un disco que nadie midió.
    media: Optional[Dict[str, Any]] = None,
    capacity_reported: Optional[int] = None,
    media_type_measured: str = "",
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
        "scope_note": scope_note,
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
        # Tipo y origen del medio: los dos campos del mínimo del Apéndice C que
        # la ola 1 no emitió (RF-09). El origen es el *Media Source* de la norma
        # —de dónde provino el medio, no dónde se almacenó—, así que se compone
        # del acta y no del lugar donde se lo recibió. Vacío = no consta.
        # Lo que DECLARÓ el acta, tecleado por una persona.
        "media_type": media_type,
        "media_origin": media_origin,
        # Lo que MIDIÓ el agente. Se emite aparte y nunca pisa lo declarado:
        # cuando los dos existen y difieren, el documento muestra ambos. Esa
        # discrepancia es justo lo que un certificado defendible tiene que
        # exponer, no resolver en silencio.
        "media_type_measured": media_type_measured,
        "media": media,
        "capacity_reported": capacity_reported,
        "started_at": started_at,
        "finished_at": finished_at,
        "last_known_location": last_known_location,
        "software_version": software_version,
        # Dónde se obtiene la clave para verificar la firma de este documento
        # (RF-08). Va firmada junto al resto para que no se pueda sustituir.
        "signing_key_url": signing_key_url(),
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
    # Con el `key_id` del PROPIO certificado: se verifica con la clave que lo
    # firmó, no con la activa. Si no, retirar una clave invalidaría de golpe
    # todo lo que firmó, incluido el chip «firma válida» de la consola.
    sig_ok = signing.verify_document(canonical, cert.signature, cert.signing_key_id)
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


def _discrepancia_de_medio(d: Dict[str, Any]) -> str:
    """Lo que el acta declaró frente a lo que el agente midió.

    🔑 Sólo habla cuando los DOS existen y no coinciden. Que uno falte no es
    discrepancia: es que no consta, y para eso ya está su propia fila vacía.

    El documento expone el desacuerdo en vez de elegir un ganador. Un
    certificado que silenciosamente prefiere una de las dos fuentes le quita al
    lector la única señal de que alguien se equivocó — y esa señal es
    exactamente lo que hace al documento defendible.
    """
    declarado = (d.get("media_type") or "").strip()
    medido = (d.get("media_type_measured") or "").strip()
    if not declarado or not medido:
        return ""
    if declarado.casefold() == medido.casefold():
        return ""
    return (
        f"El acta declara «{declarado}» y la medición del equipo indica "
        f"«{medido}». Ambos se conservan tal como se registraron."
    )


def _capacidad_legible(d: Dict[str, Any]) -> str:
    """La capacidad en bytes, con su equivalente aproximado al lado.

    Los bytes van primero porque son el dato exacto que se firmó; el redondeo
    es una cortesía para el lector, no la fuente.
    """
    bytes_ = d.get("capacity_reported")
    if not isinstance(bytes_, int) or bytes_ <= 0:
        return ""
    gb = bytes_ / 1_000_000_000
    return f"{bytes_:,} bytes (~{gb:,.0f} GB)".replace(",", ".")


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
            _row("Alcance de la sanitización", d.get("scope_note")),
            f"<tr><th>Resultado de verificación</th><td>{verif_html}</td></tr>",
            _row("Cómo se verificó", d.get("verification_method")),
            _row("Constancia de la verificación", d.get("verification_evidence")),
            _row("Tipo de medio (declarado en el acta)", d.get("media_type")),
            _row("Tipo de medio (medido por el agente)", d.get("media_type_measured")),
            _row("Discrepancia del tipo de medio", _discrepancia_de_medio(d)),
            _row("Modelo del medio", (d.get("media") or {}).get("model")),
            _row("Fabricante del medio", (d.get("media") or {}).get("manufacturer")),
            _row("Serie del medio", (d.get("media") or {}).get("serial")),
            _row("Firmware del medio", (d.get("media") or {}).get("firmware")),
            _row("Capacidad declarada del medio", _capacidad_legible(d)),
            _row("Origen del medio", d.get("media_origin")),
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
