import asyncio
from typing import TYPE_CHECKING, Any

import msgpack
import nats
from nats.errors import NoRespondersError
from nats.errors import TimeoutError as NatsTimeout

from observerrmm.exceptions import NatsDown
from observerrmm.helpers import setup_nats_options

if TYPE_CHECKING:
    from nats.aio.client import Client as NClient
    from nats.aio.msg import Msg

NATS_DATA = dict[str, Any]

BULK_NATS_TASKS = list[tuple[str, Any]]


async def _anats_message(*, nc: "NClient", subject: str, data: "NATS_DATA") -> None:
    try:
        payload = msgpack.dumps(data)
    except:
        return

    await nc.publish(subject=subject, payload=payload)


async def abulk_nats_command(*, items: "BULK_NATS_TASKS") -> None:
    """Fire and forget"""
    opts = setup_nats_options()
    try:
        nc = await nats.connect(**opts)
    except Exception:
        raise NatsDown

    tasks = [_anats_message(nc=nc, subject=item[0], data=item[1]) for item in items]
    await asyncio.gather(*tasks)
    await nc.flush()
    await nc.close()


async def nats_request(
    *, nc: "NClient", subject: str, payload: bytes, timeout: float
) -> "Msg":
    """Pide y espera respuesta, tratando «nadie escucha» como un timeout.

    El cliente activa no_responders cuando el servidor anuncia headers, asi que
    si el agente no esta suscrito la peticion no agota el plazo: falla al
    instante con NoRespondersError. Esa excepcion no desciende de TimeoutError,
    de modo que los `except TimeoutError` de los llamadores no la atrapaban y
    subia hasta la vista como un 500. Aqui se traduce al mismo timeout que ya
    saben manejar.
    """
    try:
        return await nc.request(subject, payload, timeout=timeout)
    except NoRespondersError:
        raise NatsTimeout


async def a_nats_cmd(
    *, nc: "NClient", sub: str, data: NATS_DATA, timeout: int = 10
) -> str | Any:
    try:
        msg = await nats_request(
            nc=nc, subject=sub, payload=msgpack.dumps(data), timeout=timeout
        )
    except NatsTimeout:
        return "timeout"

    try:
        return msgpack.loads(msg.data)
    except Exception as e:
        return str(e)
