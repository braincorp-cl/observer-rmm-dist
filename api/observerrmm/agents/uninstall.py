"""Desinstalación manual del agente, avisada por el propio equipo.

Contexto del problema (medido en el código, no supuesto):

El script de desinstalación local (`core/agent_linux.sh uninstall`,
`core/mac_uninstall.sh`, el `[UninstallRun]` del instalador Windows) sólo toca
el equipo: para el servicio, borra el binario, la config y el mesh. No habla con
el servidor. Resultado: la fila `Agent` sobrevive y el equipo queda para siempre
como un agente Offline que ya no existe.

Este módulo cierra ese hueco por el otro lado: el equipo AVISA antes de
destruirse (endpoint `/api/v3/uninstalled/`) y el servidor levanta la alerta,
deja el registro de auditoría y programa el borrado.

Dos decisiones que conviene no deshacer sin leer el porqué:

1. **La alerta nace sin agente** (`agent=None`). `Alert.agent` es
   `on_delete=CASCADE`: una alerta ligada al agente moriría junto con el agente
   que estamos por borrar, o sea junto con lo que está denunciando. Todo el
   contexto (equipo, cliente, sitio, quién, IP, hora) va denormalizado en el
   texto y en el `AuditLog`, que guarda el hostname como texto y no como FK.

   Efecto lateral que hay que conocer: por la rama `custom_alert_queryset` de
   `PermissionQuerySet.filter_by_role`, una alerta con `agent=None` la ve
   cualquier rol con clientes o sitios asignados, no sólo el dueño del equipo.

2. **El borrado va con ventana de gracia** y se cancela si el mismo `agent_id`
   vuelve a dar señales. Reinstalar sobre un equipo existente corre el MISMO
   `uninstall`, así que sin la ventana una reinstalación se llevaría por delante
   el registro que acaba de reaparecer.

El "quién" es una atribución, no una identidad fuerte: quien tiene root en el
equipo puede exportar `SUDO_USER` con el nombre que se le ocurra. Sirve para
saber qué pasó, no para sostener una acusación.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.utils import timezone as djangotime

from alerts.models import Alert
from logs.models import AuditLog, DebugLog
from observerrmm.constants import (
    AlertSeverity,
    AlertType,
    AuditActionType,
    AuditObjType,
    DebugLogType,
)

if TYPE_CHECKING:
    from agents.models import Agent


# Tope de lo que aceptamos del equipo en cada campo de texto libre. Lo que llega
# viene de un endpoint autenticado pero de una máquina que en ese momento está
# siendo desmantelada por alguien con root: no hay razón para confiar en el
# tamaño de nada.
MAX_FIELD_LEN = 255


def _clean(value: Any, *, limit: int = MAX_FIELD_LEN) -> str:
    """Deja el valor en una línea, recortado y sin caracteres de control.

    El actor termina en el asunto de un correo: un `\\r\\n` ahí es inyección de
    cabeceras. Se limpia acá, una vez, en vez de confiar en cada consumidor.
    """
    if value is None:
        return ""
    text = str(value)
    text = "".join(ch for ch in text if ch.isprintable())
    return text.strip()[:limit]


def describe_actor(payload: dict[str, Any]) -> str:
    """Arma la frase del "quién" con lo que el equipo alcanzó a averiguar."""
    actor = _clean(payload.get("actor"))
    if not actor:
        return "desconocido"

    sudo_user = _clean(payload.get("sudo_user"))
    console_user = _clean(payload.get("console_user"))

    # `sudo_user` presente ⇒ el comando se lanzó con sudo y sabemos desde qué
    # cuenta. Es el dato que pidió el usuario y el único que distingue "root" de
    # una persona.
    if sudo_user:
        return f"{sudo_user} (vía sudo)"

    # Windows: la desinstalación corre elevada, así que la cuenta que ejecuta
    # puede ser un administrador distinto de quien está sentado frente al
    # equipo. Cuando difieren, se informan las dos.
    if console_user and console_user.lower() != actor.lower():
        return f"{actor} (sesión de consola: {console_user})"

    return actor


def build_message(agent: "Agent", payload: dict[str, Any], when) -> str:
    actor = describe_actor(payload)
    lan_ips = _clean(payload.get("lan_ips")) or agent.local_ips
    source = _clean(payload.get("source"), limit=40) or "desconocido"

    return (
        f"Desinstalación manual del agente en {agent.hostname} "
        f"({agent.client.name} / {agent.site.name}). "
        f"Ejecutada por {actor} "
        f"el {_local_stamp(when)}. "
        f"IP LAN: {lan_ips or 'desconocida'}. "
        f"IP pública: {agent.public_ip or 'desconocida'}. "
        f"Origen del aviso: {source}."
    )


def _local_stamp(when) -> str:
    """Fecha y hora en la zona del PRODUCTO, no en la de Django.

    `settings.TIME_ZONE` es UTC y no se toca (la BD guarda en UTC a propósito),
    así que `djangotime.localtime()` a secas rinde "01:11 UTC" para algo que
    pasó a las 21:11 en Chile. Quien lee la alerta quiere la hora de su reloj:
    la zona del producto vive en `CoreSettings.default_time_zone`, que es la
    misma que usa el resto de la consola.
    """
    from observerrmm.utils import get_default_timezone

    try:
        stamp = when.astimezone(get_default_timezone())
    except Exception:
        stamp = djangotime.localtime(when)
    return stamp.strftime("%d-%m-%Y %H:%M:%S %Z")


def record_manual_uninstall(
    agent: "Agent", payload: dict[str, Any], *, client_ip: Optional[str] = None
) -> Alert:
    """Deja constancia y avisa. NO borra el agente: de eso se encarga la tarea.

    Escribe siempre, pase lo que pase con el borrado: la alerta y la auditoría
    son el producto principal de esta feature, no un adorno del borrado.
    """
    when = djangotime.now()
    message = build_message(agent, payload, when)

    # Congelado ANTES de cualquier borrado: después de `agent.delete()` no queda
    # de dónde sacarlo.
    hostname = agent.hostname
    client_name = agent.client.name
    site_name = agent.site.name

    alert = Alert.objects.create(
        agent=None,
        alert_type=AlertType.AGENT_UNINSTALL,
        severity=AlertSeverity.ERROR,
        message=message,
        hidden=False,
    )

    AuditLog.objects.create(
        username=describe_actor(payload),
        agent=hostname,
        agent_id=agent.agent_id,
        object_type=AuditObjType.AGENT,
        action=AuditActionType.AGENT_UNINSTALL,
        message=message,
        debug_info={
            "ip": client_ip,
            "client": client_name,
            "site": site_name,
            "plat": agent.plat,
            "mesh_node_id": agent.mesh_node_id,
            "reported": {
                key: _clean(payload.get(key))
                for key in (
                    "actor",
                    "sudo_user",
                    "login_user",
                    "console_user",
                    "lan_ips",
                    "local_time",
                    "source",
                )
            },
        },
    )

    if send_manual_uninstall_email(agent, message):
        # Se estampa igual que en el resto de las alertas: la consola muestra esa
        # marca, y una alerta que salió por correo pero figura sin enviar hace
        # dudar de si el aviso llegó justo cuando más importa.
        alert.email_sent = djangotime.now()
        alert.save(update_fields=["email_sent"])

    return alert


def send_manual_uninstall_email(agent: "Agent", message: str) -> bool:
    """Correo de aviso. Un fallo acá no puede tumbar la alerta ni el borrado."""
    from core.utils import get_core_settings

    try:
        core = get_core_settings()
        _, ok = core.send_mail(
            (
                f"{agent.client.name}, {agent.site.name}, {agent.hostname} - "
                "agente desinstalado manualmente"
            ),
            message,
            alert_template=agent.alert_template,
        )
        return bool(ok)
    except Exception as e:
        DebugLog.error(
            message=f"No se pudo enviar el correo de desinstalación manual: {e}",
            log_type=DebugLogType.AGENT_ISSUES,
        )
        return False


def grace_seconds() -> int:
    minutes = getattr(settings, "MANUAL_UNINSTALL_GRACE_MINUTES", 10)
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 10
    return max(0, minutes) * 60
