"""Feature 030 · Fase 3 · T022 — exportación del caso de un equipo perdido.

El PDF es el entregable que sale de la consola y entra en una carpeta ajena:
una denuncia, un sumario interno, un seguro. Eso manda tres decisiones que no
son de estilo.

1. **El documento tiene que poder leerse sin la consola al lado.** Nadie que lo
   reciba va a tener sesión abierta ni contexto. Por eso lleva la portada con
   el caso completo (quién lo abrió, cuándo, con qué motivo), la política de
   retención vigente y el aviso legal de ADR-025 — y por eso las imágenes van
   EMBEBIDAS en el archivo, no enlazadas: un enlace a la consola es una página
   de login para quien recibe el documento.

2. **Los dos relojes se imprimen, siempre.** `captured_at` es el reloj del
   equipo y `created` el del servidor. Entre los dos puede haber horas si el
   equipo estuvo sin red, y en un documento que puede terminar ante un tribunal
   esa diferencia es exactamente el dato que alguien va a querer discutir.
   Imprimir uno solo sería elegir por el lector.

3. **El permiso de mirar rostros se respeta también acá.** ADR-025 separa
   operar el caso de VER lo que la pantalla mostraba, y un PDF es una forma
   perfecta de saltarse esa separación: se genera una vez y después circula
   solo. Quien no tenga `can_view_lost_evidence` igual puede exportar —el
   recorrido y la cronología son lo que hace falta para una denuncia— pero el
   documento sale SIN imágenes y lo dice en la portada, en vez de salir
   silenciosamente incompleto. Un documento que omite sin avisar es peor que
   uno que no se pudo generar.

🪤 La imagen se descifra al leerla (`asset.open`), así que un ambiente con la
llave perdida no puede exportar las imágenes aunque el permiso esté. Ese caso
NO tumba el PDF: la pieza sale con la nota de por qué falta, que es la misma
distinción entre "no había" y "no se pudo" que sostiene toda la feature.
"""

import base64
import unicodedata
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from django.utils import timezone as djangotime

from observerrmm.constants import LostModeEvidenceKind

from .lostmode_crypto import EvidenceKeyMissing

if TYPE_CHECKING:
    from .models import Agent, LostModeEvidence, LostModeState


# El tope existe para que un caso largo no genere un PDF de cientos de MB que
# nadie puede adjuntar a un correo. Cuando se recorta, el documento LO DICE:
# un recorte silencioso convertiría "esto es todo lo que hubo" en mentira.
MAX_IMAGENES_EMBEBIDAS = 60

# Tipos MIME por extensión. El agente sólo manda PNG y JPEG; cualquier otra cosa
# no debería haber pasado la validación de subida, y si pasó no se embebe.
MIME_POR_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# El nombre del tipo de pieza, en el idioma del documento.
#
# NO se usa `get_kind_display()`: las etiquetas de `LostModeEvidenceKind` están
# en inglés porque son las que ve la API, y este PDF lo lee una persona en un
# mostrador de carabineros. Un informe que mezcla "Ciclo 2" con "Screen Capture"
# se lee como una exportación cruda de una base de datos, no como un documento.
TIPO_DE_PIEZA = {
    LostModeEvidenceKind.SCREEN: "Captura de pantalla",
    LostModeEvidenceKind.WEBCAM: "Foto de la cámara",
    LostModeEvidenceKind.GEO: "Posición del equipo",
}


def _fecha(valor: Optional[Any]) -> str:
    """Formato ISO corto y en la zona del servidor, sin microsegundos.

    Se localiza a la zona configurada y no se deja en UTC porque el documento lo
    lee una persona en Chile, y una hora en UTC en una denuncia obliga a que
    alguien haga la resta a mano.
    """
    if not valor:
        return "—"
    return djangotime.localtime(valor).strftime("%Y-%m-%d %H:%M:%S %Z")


def _coordenadas(pieza: "LostModeEvidence") -> str:
    if pieza.lat is None or pieza.lng is None:
        return "—"

    texto = f"{pieza.lat:.6f}, {pieza.lng:.6f}"
    if pieza.accuracy_m is not None:
        texto += f" (±{pieza.accuracy_m} m)"
    if pieza.source:
        texto += f" · {pieza.source}"
    return texto


def _imagen_embebida(pieza: "LostModeEvidence") -> Dict[str, str]:
    """Devuelve la imagen como data URI, o el motivo por el que no está.

    Nunca lanza: una pieza ilegible no puede impedir que se exporte el resto del
    caso. Lo que sí hace es dejar el motivo por escrito.
    """
    if not pieza.asset:
        return {"uri": "", "motivo": "el equipo no la pudo tomar en este ciclo"}

    nombre = pieza.asset.name.lower()
    mime = next(
        (m for ext, m in MIME_POR_EXTENSION.items() if nombre.endswith(ext)), ""
    )
    if not mime:
        return {
            "uri": "",
            "motivo": "el archivo no tiene un formato que se pueda incrustar",
        }

    try:
        with pieza.asset.open("rb") as fh:
            datos = fh.read()
    except EvidenceKeyMissing:
        # El ambiente perdió la llave. Es un hecho del servidor, no de la
        # evidencia, y quien lea el documento tiene que poder distinguirlo.
        return {"uri": "", "motivo": "está cifrada y este servidor no tiene la llave"}
    except OSError:
        return {"uri": "", "motivo": "el archivo no se pudo leer"}

    if not datos:
        return {"uri": "", "motivo": "el archivo guardado está vacío"}

    b64 = base64.b64encode(datos).decode("ascii")
    return {"uri": f"data:{mime};base64,{b64}", "motivo": ""}


def armar_contexto(
    *,
    agent: "Agent",
    state: Optional["LostModeState"],
    piezas: List["LostModeEvidence"],
    retencion: Dict[str, int],
    cifrado: Optional[bool],
    exportado_por: str,
    con_imagenes: bool,
) -> Dict[str, Any]:
    """Arma todo lo que el documento necesita, sin tocar HTML.

    Vive separada del render por lo mismo de siempre: la CI puede probar QUÉ
    dice el documento —que estén los dos relojes, que las imágenes falten
    cuando falta el permiso, que el recorte se declare— sin depender de
    WeasyPrint ni de parsear un PDF.
    """
    piezas_ctx: List[Dict[str, Any]] = []
    embebidas = 0
    recortadas = 0

    for pieza in piezas:
        fila: Dict[str, Any] = {
            "ciclo": pieza.cycle,
            "tipo": TIPO_DE_PIEZA.get(pieza.kind, pieza.get_kind_display()),
            "es_geo": pieza.kind == LostModeEvidenceKind.GEO,
            "capturado_equipo": _fecha(pieza.captured_at),
            "recibido_servidor": _fecha(pieza.created),
            "usuario_sesion": pieza.session_user or "—",
            "coordenadas": _coordenadas(pieza),
            "nota": pieza.note or "",
            "imagen": "",
            "imagen_ausente": "",
        }

        # Las piezas de geo no tienen imagen por definición: no hay nada que
        # embeber ni que explicar.
        if pieza.kind != LostModeEvidenceKind.GEO:
            if not con_imagenes:
                fila["imagen_ausente"] = (
                    "omitida — quien exportó no tiene permiso para verla"
                )
            elif embebidas >= MAX_IMAGENES_EMBEBIDAS:
                fila["imagen_ausente"] = (
                    "omitida — se alcanzó el tope de tamaño del documento"
                )
                recortadas += 1
            else:
                resultado = _imagen_embebida(pieza)
                if resultado["uri"]:
                    fila["imagen"] = resultado["uri"]
                    embebidas += 1
                else:
                    fila["imagen_ausente"] = resultado["motivo"]

        piezas_ctx.append(fila)

    if state is None:
        estado_caso = "sin caso registrado"
    elif state.active:
        estado_caso = "ABIERTO"
    else:
        estado_caso = "cerrado (equipo recuperado)"

    return {
        "hostname": agent.hostname,
        "agent_id": agent.agent_id,
        "cliente": agent.client.name if agent.client else "—",
        "sitio": agent.site.name if agent.site else "—",
        "sistema": agent.operating_system or "—",
        "estado_caso": estado_caso,
        "motivo": (state.reason if state and state.reason else "—"),
        "marcado_por": (state.marked_by.username if state and state.marked_by else "—"),
        "marcado_el": _fecha(state.marked_at if state else None),
        "recuperado_el": _fecha(state.recovered_at if state else None),
        "cadencia_min": (state.interval_min if state else None),
        "retencion_dias": retencion.get("prune_days"),
        "retencion_cerrado_dias": retencion.get("closed_case_days"),
        # `None` es un tercer valor con significado propio: el servidor no pudo
        # decirlo (llave mal formada). No es lo mismo que "no cifra".
        "cifrado": cifrado,
        "exportado_por": exportado_por,
        "exportado_el": _fecha(djangotime.now()),
        "con_imagenes": con_imagenes,
        "total_piezas": len(piezas_ctx),
        "imagenes_embebidas": embebidas,
        "imagenes_recortadas": recortadas,
        "piezas": piezas_ctx,
    }


def nombre_archivo(agent: "Agent") -> str:
    """Nombre ASCII y sin espacios.

    El archivo viaja por correo, se sube a sistemas de terceros y termina en
    rutas de Windows: un hostname con acento o con dos puntos rompe alguna de
    esas etapas. Mismo criterio que `screenshotFilename` en el agente.

    🪤 `str.isalnum()` NO alcanza para esto: en Python devuelve True para `ñ` y
    para `ó`, así que un hostname como "NOTEBOOK Ñuñoa" pasaba entero. Hay que
    descomponer los acentos y quedarse con el ASCII, que es lo que hace el
    `normalize("NFKD")` de abajo.
    """
    plano = (
        unicodedata.normalize("NFKD", agent.hostname or "equipo")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    limpio = "".join(c if (c.isalnum() or c in "-_") else "-" for c in plano)
    # Un hostname que era todo no-ASCII quedaría en una fila de guiones.
    limpio = limpio.strip("-") or "equipo"
    sello = djangotime.localtime(djangotime.now()).strftime("%Y%m%d-%H%M%S")
    return f"caso-equipo-perdido-{limpio}-{sello}.pdf"


CSS_INFORME = """
@page { size: A4; margin: 18mm 15mm 20mm 15mm;
  @bottom-center { content: "Observer RMM · caso de equipo perdido · página " counter(page) " de " counter(pages);
                   font-size: 8pt; color: #666; } }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #1c1c1c; }
h1 { font-size: 17pt; margin: 0 0 2mm 0; }
h2 { font-size: 12pt; margin: 7mm 0 2mm 0; border-bottom: 1px solid #bbb; padding-bottom: 1mm; }
.sub { color: #555; font-size: 9pt; margin: 0 0 5mm 0; }
table.datos { width: 100%; border-collapse: collapse; }
table.datos th { text-align: left; width: 38mm; font-weight: bold; padding: 1.2mm 2mm 1.2mm 0;
                 vertical-align: top; }
table.datos td { padding: 1.2mm 0; vertical-align: top; }
.aviso { border: 1px solid #c9a227; background: #fdf6e3; padding: 3mm; margin: 4mm 0;
         font-size: 8.5pt; }
.alerta { border: 1px solid #b03030; background: #fbeaea; padding: 3mm; margin: 4mm 0;
          font-size: 8.5pt; }
.pieza { border: 1px solid #ccc; padding: 3mm; margin: 0 0 4mm 0; page-break-inside: avoid; }
.pieza .cab { font-weight: bold; margin-bottom: 1.5mm; }
.pieza .meta { color: #444; font-size: 8.5pt; }
.pieza img { max-width: 100%; max-height: 105mm; margin-top: 2.5mm; border: 1px solid #999; }
.falta { color: #a33; font-style: italic; font-size: 8.5pt; margin-top: 2mm; }
"""


def armar_html(ctx: Dict[str, Any]) -> str:
    """Render a mano, sin motor de plantillas.

    No se usa el Jinja de `ee/reporting` porque este documento no es una
    plantilla que el operador edite: es un formato fijo con valor probatorio.
    Meterlo en el sistema de plantillas lo volvería editable desde la consola, y
    un informe de evidencia que cualquiera puede reescribir no sirve para lo que
    existe. Lo que sí se reutiliza es el motor de PDF (ADR-022).
    """
    from django.utils.html import escape

    def e(v: Any) -> str:
        return escape("" if v is None else str(v))

    if ctx["cifrado"] is True:
        cifrado_txt = "sí, cifrada en reposo en el servidor"
    elif ctx["cifrado"] is False:
        cifrado_txt = "NO — este servidor guarda la evidencia sin cifrar"
    else:
        cifrado_txt = "no se pudo determinar (revisar la llave del servidor)"

    partes: List[str] = [
        "<h1>Caso de equipo perdido o robado</h1>",
        f"<p class='sub'>{e(ctx['hostname'])} · {e(ctx['cliente'])} / {e(ctx['sitio'])}</p>",
        "<h2>El caso</h2>",
        "<table class='datos'>",
        f"<tr><th>Estado</th><td>{e(ctx['estado_caso'])}</td></tr>",
        f"<tr><th>Motivo declarado</th><td>{e(ctx['motivo'])}</td></tr>",
        f"<tr><th>Marcado por</th><td>{e(ctx['marcado_por'])}</td></tr>",
        f"<tr><th>Marcado el</th><td>{e(ctx['marcado_el'])}</td></tr>",
        f"<tr><th>Recuperado el</th><td>{e(ctx['recuperado_el'])}</td></tr>",
        f"<tr><th>Cadencia de captura</th><td>{e(ctx['cadencia_min'])} min</td></tr>",
        "</table>",
        "<h2>El equipo</h2>",
        "<table class='datos'>",
        f"<tr><th>Nombre</th><td>{e(ctx['hostname'])}</td></tr>",
        f"<tr><th>Identificador</th><td>{e(ctx['agent_id'])}</td></tr>",
        f"<tr><th>Cliente / sitio</th><td>{e(ctx['cliente'])} / {e(ctx['sitio'])}</td></tr>",
        f"<tr><th>Sistema</th><td>{e(ctx['sistema'])}</td></tr>",
        "</table>",
        "<h2>Este documento</h2>",
        "<table class='datos'>",
        f"<tr><th>Exportado por</th><td>{e(ctx['exportado_por'])}</td></tr>",
        f"<tr><th>Exportado el</th><td>{e(ctx['exportado_el'])}</td></tr>",
        f"<tr><th>Piezas incluidas</th><td>{e(ctx['total_piezas'])}</td></tr>",
        f"<tr><th>Imágenes embebidas</th><td>{e(ctx['imagenes_embebidas'])}</td></tr>",
        f"<tr><th>Evidencia cifrada</th><td>{e(cifrado_txt)}</td></tr>",
        f"<tr><th>Retención</th><td>{e(ctx['retencion_dias'])} días desde la captura; "
        f"{e(ctx['retencion_cerrado_dias'])} días tras cerrar el caso</td></tr>",
        "</table>",
    ]

    # Las dos advertencias van ARRIBA, antes de la línea de tiempo: quien recibe
    # el documento tiene que saber que está incompleto antes de leerlo, no
    # después de haberlo citado.
    if not ctx["con_imagenes"]:
        partes.append(
            "<div class='alerta'><b>Documento sin imágenes.</b> Quien lo exportó no "
            "tiene concedido el permiso de ver evidencia visual "
            "(<code>can_view_lost_evidence</code>), así que las capturas de pantalla y "
            "las fotos NO están incluidas. La cronología y el recorrido sí lo están.</div>"
        )

    if ctx["imagenes_recortadas"]:
        partes.append(
            f"<div class='alerta'><b>Documento recortado.</b> "
            f"{e(ctx['imagenes_recortadas'])} imágenes se omitieron por el tope de "
            f"tamaño del documento ({MAX_IMAGENES_EMBEBIDAS}). Están completas en la "
            f"consola.</div>"
        )

    partes.append(
        "<div class='aviso'><b>Uso y límites.</b> Esta evidencia se recolectó bajo el "
        "régimen de la decisión ADR-025: motivo obligatorio, permiso dedicado y "
        "registro de auditoría de quién abrió y cerró el caso. Su tratamiento debe "
        "limitarse a la finalidad declarada arriba. Las horas se informan por "
        "duplicado —reloj del equipo y reloj del servidor— porque entre ambos puede "
        "haber diferencia si el equipo estuvo sin red.</div>"
    )

    partes.append("<h2>Línea de tiempo</h2>")

    if not ctx["piezas"]:
        partes.append("<p>No hay evidencia registrada para este equipo.</p>")

    for pieza in ctx["piezas"]:
        partes.append("<div class='pieza'>")
        partes.append(
            f"<div class='cab'>Ciclo {e(pieza['ciclo'])} · {e(pieza['tipo'])}</div>"
        )
        partes.append(
            "<div class='meta'>"
            f"Reloj del equipo: {e(pieza['capturado_equipo'])}<br>"
            f"Reloj del servidor: {e(pieza['recibido_servidor'])}<br>"
            f"Sesión abierta: {e(pieza['usuario_sesion'])}"
        )
        if pieza["es_geo"] or pieza["coordenadas"] != "—":
            partes.append(f"<br>Ubicación: {e(pieza['coordenadas'])}")
        if pieza["nota"]:
            partes.append(f"<br>Motivo declarado por el equipo: {e(pieza['nota'])}")
        partes.append("</div>")

        if pieza["imagen"]:
            partes.append(f"<img src=\"{pieza['imagen']}\" alt=''>")
        elif pieza["imagen_ausente"]:
            partes.append(
                f"<div class='falta'>Sin imagen: {e(pieza['imagen_ausente'])}.</div>"
            )

        partes.append("</div>")

    cuerpo = "".join(partes)
    return f"<html><head><meta charset='utf-8'></head><body>{cuerpo}</body></html>"
