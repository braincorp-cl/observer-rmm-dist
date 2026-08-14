# observer_agent_hardening

Deja el servicio **MeshAgent** (el de MeshCentral, no el agente Go de Observer RMM)
con un drop-in de systemd que le quita `CAP_SYS_MODULE` y le acorta el plazo de
detención.

## El problema, en una línea

Un `lshw` colgado dentro del MeshAgent deja al equipo **en línea y sordo**: el
agente se queda esperando a ese hijo y deja de leer los mensajes del servidor, así
que «Tomar control» sale deshabilitado y ninguna acción llega.

## Por qué en todos los Linux y no sólo donde hay VMware

Medido el 2026-08-14:

| Medición | Resultado |
|---|---|
| Secuencia tras reiniciar el servicio | `lshw -class disk` a los **0,66 s** → `lshw -class disk -disable network` a los **3 s** |
| Core cacheado del agente (`meshagent.db`, clave `CoreModule`) | trae la forma **con** el flag |
| Memoria del MeshCentral que sirve la flota | sólo la forma **con** el flag |
| `md5sum` del binario instalado vs el que publica MeshCentral 1.2.1 | **idénticos** |

O sea: la forma que cuelga viaja en el **core de arranque**, dentro del binario
oficial, y corre **antes** de que el core bueno tome el relevo. Ni actualizar el
agente ni refrescar el core la evitan. La exposición tampoco es «tener VMware hoy»:
es adquirir cualquier driver que se bloquee en `request_module`, y el día que
alguien instale Workstation el equipo queda sordo sin ningún síntoma.

Reportado aguas arriba como `Ylianst/MeshAgent#382` — lo reportable es que un hijo
atascado paralice el bucle de mensajes, no el `lshw`.

## Qué hace

- Escribe `/etc/systemd/system/meshagent.service.d/10-meshagent-hardening.conf`
  con `CapabilityBoundingSet=~CAP_SYS_MODULE` y `TimeoutStopSec=20`.
  Va en `/etc/systemd`, no en `/lib`, porque `/lib` lo reescribe el instalador del
  propio MeshAgent en cada reinstalación.
- `daemon-reload` y reinicio del servicio, **sólo si el archivo cambió**.
- Retira el drop-in manual `10-xsession.conf` que se dejó en terreno el 2026-08-14,
  y sólo si lleva nuestra marca.
- Es **no-op** donde no hay MeshAgent instalado.

## Verificación en el equipo

```bash
grep CapBnd /proc/$(pgrep -x meshagent)/status   # el bit 16 debe estar en 0
ps -eo stat,cmd | grep -E 'lshw|modprobe'        # cero procesos en estado D
ss -tnp | grep meshagent                         # Recv-Q en 0 contra el servidor
```

Y desde la consola: el botón **Tomar control** habilitado y una sesión que abre.

## Alcance

Cubre los equipos a los que se llega por SSH. Los enrolamientos nuevos lo reciben
del instalador (`api/observerrmm/core/agent_linux.sh`); para el resto de la flota
administrada por el RMM el vehículo es un script de la biblioteca.
