"""Feature 055 · el veredicto de categoría de sanitización alcanzable.

Lo que se prueba acá es lo que puede mentir en silencio:

- que **«sin dato» y «sin categoría alcanzable» sigan siendo dos cosas**. La
  regla ingenua —«si no encontré una vía, no hay vía»— es plausible, se escribe
  sola, y convierte en irrecuperable un disco que nadie miró. RN-02 existe para
  prohibirla y acá tiene su control positivo;
- que la versión **SQL** del veredicto (la del filtro) y la versión **Python**
  (la de cada fila) den lo mismo caso por caso;
- que un disco de estado sólido **sin sondear capacidades** no se declare «sin
  categoría»: eso sería afirmar que se preguntó al firmware cuando no se
  preguntó;
- que un medio virtualizado no se confunda con uno sin vía: el medio real está
  en otra parte.
"""

from django.utils import timezone as djangotime
from model_bakery import baker

from agents.mediosalmacenamiento import derivar_veredicto, filtro_por_veredicto
from agents.models import Agent, StorageMediaState, StorageMedium
from observerrmm.constants import (
    STORAGE_BUS_TYPE_FILE_BACKED_VIRTUAL,
    AgentPlat,
    STORAGE_BUS_TYPE_NVME,
    STORAGE_BUS_TYPE_SATA,
    STORAGE_MEDIA_TYPE_HDD,
    STORAGE_MEDIA_TYPE_SSD,
    StorageSanitizationVerdict,
    StorageSelfEncryption,
)
from observerrmm.test import ObserverTestCase


def _estado(agent, **kwargs):
    datos = {
        "supported": True,
        "query_error": None,
        "capabilities_probed": False,
        "measured_at": djangotime.now(),
    }
    datos.update(kwargs)
    return StorageMediaState.objects.create(agent=agent, **datos)


def _disco(agent, **kwargs):
    """Un disco con lo mínimo poblado; cada test sobrescribe lo que importa."""
    datos = {
        "pnp_device_id": r"SCSI\DISK&VEN_X&PROD_Y\4&1",
        "model": "Disco de prueba",
        "serial_number": "SN-0001",
        "firmware_revision": "1.0",
        "size_bytes": 512_110_190_592,
        "bus_type": STORAGE_BUS_TYPE_SATA,
        "media_type_code": STORAGE_MEDIA_TYPE_HDD,
        "spindle_speed": 5400,
        "is_system_disk": True,
        "is_virtual": False,
        "removable": False,
        "self_encrypting": None,
        "sanitize_capabilities": None,
        "measured_at": djangotime.now(),
    }
    datos.update(kwargs)
    return StorageMedium.objects.create(agent=agent, **datos)


class TestVeredictoDeSanitizacion(ObserverTestCase):
    """La regla de RN-03 y RN-02, sin pasar por HTTP."""

    def setUp(self):
        self.setup_coresettings()

    def _agente(self):
        return baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)

    def _veredicto(self, agent):
        return derivar_veredicto(Agent.objects.get(pk=agent.pk))

    # -- los que NO se pueden fundir -------------------------------------

    def test_un_equipo_sin_reporte_es_sin_dato(self):
        """Nunca reportó. Es el que más importa ver en el panel."""
        a = self._agente()
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_DATA)

    def test_un_error_de_consulta_es_sin_dato_no_sin_categoria(self):
        a = self._agente()
        _estado(a, query_error="acceso denegado al espacio de nombres")
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_SSD)
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_DATA)

    def test_estado_solido_sin_sondear_capacidades_es_sin_dato(self):
        """🔑 El control de RN-02 y la razón de ser de `capabilities_probed`.

        Un disco de estado sólido del que no se preguntó al firmware **no** es
        un disco sin vía de sanitización: es un disco que nadie miró. Declararlo
        «sin categoría» afirmaría una medición que no se hizo.
        """
        a = self._agente()
        _estado(a, capabilities_probed=False)
        _disco(
            a, media_type_code=STORAGE_MEDIA_TYPE_SSD, bus_type=STORAGE_BUS_TYPE_NVME
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_DATA)

    def test_estado_solido_sondeado_y_sin_comando_si_es_sin_categoria(self):
        """El mismo disco, ya preguntado: ahí sí se puede afirmar que no hay."""
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            bus_type=STORAGE_BUS_TYPE_NVME,
            self_encrypting=StorageSelfEncryption.NOT_CAPABLE,
            sanitize_capabilities={"supported": False, "commands": []},
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_CATEGORY)

    # -- los veredictos positivos ----------------------------------------

    def test_magnetico_es_clear_remoto_aunque_no_se_sondeen_capacidades(self):
        """El tipo de medio basta para afirmar clear: no hace falta el firmware."""
        a = self._agente()
        _estado(a, capabilities_probed=False)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_HDD, spindle_speed=5400)
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.CLEAR_REMOTE)

    def test_autocifrado_habilitado_es_purge_remoto(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            self_encrypting=StorageSelfEncryption.ENABLED,
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.PURGE_REMOTE)

    def test_autocifrado_capaz_pero_no_habilitado_no_alcanza(self):
        """Sin clave en uso no hay nada que destruir: capaz ≠ habilitado."""
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            self_encrypting=StorageSelfEncryption.CAPABLE,
            sanitize_capabilities={"supported": False, "commands": []},
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_CATEGORY)

    def test_un_comando_de_sanitizacion_es_purge_con_imagen_live(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            sanitize_capabilities={"supported": True, "commands": ["nvme_sanitize"]},
        )
        self.assertEqual(
            self._veredicto(a), StorageSanitizationVerdict.PURGE_LIVE_IMAGE
        )

    def test_purge_gana_sobre_clear_en_un_magnetico_con_comando(self):
        """El estándar prefiere purge cuando las dos vías están disponibles."""
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_HDD,
            sanitize_capabilities={"supported": True, "commands": ["ata_sanitize"]},
        )
        self.assertEqual(
            self._veredicto(a), StorageSanitizationVerdict.PURGE_LIVE_IMAGE
        )

    def test_un_disco_virtualizado_tiene_veredicto_propio(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            is_virtual=True,
            bus_type=STORAGE_BUS_TYPE_FILE_BACKED_VIRTUAL,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.VIRTUAL_MEDIA)

    # -- el disco que manda ----------------------------------------------

    def test_el_veredicto_sale_del_disco_de_sistema_y_no_del_otro(self):
        """RN-03: un disco de datos no cambia el veredicto del equipo."""
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            pnp_device_id="DISCO-SISTEMA",
            is_system_disk=True,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            sanitize_capabilities={"supported": False, "commands": []},
        )
        _disco(
            a,
            pnp_device_id="DISCO-DATOS",
            is_system_disk=False,
            media_type_code=STORAGE_MEDIA_TYPE_HDD,
        )
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_CATEGORY)

    def test_un_equipo_que_reporto_sin_disco_de_sistema_es_sin_dato(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, is_system_disk=False)
        self.assertEqual(self._veredicto(a), StorageSanitizationVerdict.NO_DATA)


class TestLasDosFormasDeLaRegla(ObserverTestCase):
    """El guardián de las dos copias: Python para la fila, SQL para el filtro."""

    def setUp(self):
        self.setup_coresettings()

    def _agente(self):
        return baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)

    def test_sql_y_python_coinciden(self):
        """Cada caso se clasifica con Python y después se busca con SQL.

        Si uno cae en veredictos distintos, una de las dos copias se quedó
        atrás — que es exactamente lo que pasa cuando alguien agrega un
        veredicto y toca sólo un lado del archivo.
        """
        agentes = []

        agentes.append(self._agente())  # sin reporte

        a = self._agente()
        _estado(a, capabilities_probed=False)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_HDD)
        agentes.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=False)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_SSD)
        agentes.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            self_encrypting=StorageSelfEncryption.NOT_CAPABLE,
            sanitize_capabilities={"supported": False, "commands": []},
        )
        agentes.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            self_encrypting=StorageSelfEncryption.ENABLED,
        )
        agentes.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            sanitize_capabilities={"supported": True, "commands": ["nvme_sanitize"]},
        )
        agentes.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, is_virtual=True, bus_type=STORAGE_BUS_TYPE_FILE_BACKED_VIRTUAL)
        agentes.append(a)

        a = self._agente()
        _estado(a, supported=False)
        agentes.append(a)

        a = self._agente()
        _estado(a, query_error="fallo la consulta")
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_HDD)
        agentes.append(a)

        # 🪤 El error VACÍO: en Python una cadena vacía es falsa, en SQL
        # `query_error IS NOT NULL` sería verdadera. Si el filtro no tratara los
        # dos igual, este agente saldría en un veredicto por el filtro y en otro
        # en su propia fila.
        a = self._agente()
        _estado(a, query_error="", capabilities_probed=False)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_HDD)
        agentes.append(a)

        # Reportó, pero el único disco es de datos: no sabemos cuál manda.
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, is_system_disk=False)
        agentes.append(a)

        # Un disco de sistema con tipo de medio NULO: tampoco sabemos.
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, media_type_code=None, spindle_speed=None)
        agentes.append(a)

        # Dos discos: el de sistema manda, el de datos no puede reclamar el
        # veredicto. Si los `Q` no nombraran sus condiciones juntas, el filtro
        # combinaría los dos discos y este caso saldría mal.
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(
            a,
            pnp_device_id="SISTEMA",
            is_system_disk=True,
            media_type_code=STORAGE_MEDIA_TYPE_SSD,
            sanitize_capabilities={"supported": False, "commands": []},
        )
        _disco(
            a,
            pnp_device_id="DATOS",
            is_system_disk=False,
            media_type_code=STORAGE_MEDIA_TYPE_HDD,
            sanitize_capabilities={"supported": True, "commands": ["ata_sanitize"]},
        )
        agentes.append(a)

        for agent in agentes:
            esperado = derivar_veredicto(Agent.objects.get(pk=agent.pk))
            for veredicto in StorageSanitizationVerdict.values:
                encontrado = (
                    Agent.objects.filter(pk=agent.pk)
                    .filter(filtro_por_veredicto(veredicto))
                    .exists()
                )
                self.assertEqual(
                    encontrado,
                    veredicto == esperado,
                    f"{agent.hostname}: Python dice {esperado}, el filtro "
                    f"{'lo incluye' if encontrado else 'no lo incluye'} en {veredicto}",
                )

    def test_un_equipo_sin_fila_no_suma_al_conteo_de_sin_categoria(self):
        """🔑 El control negativo del panel.

        Si «sin dato» y «sin categoría» se fundieran, este equipo —del que no
        sabemos nada— aparecería contado como un equipo sin vía de sanitización,
        y alguien decidiría sobre él.
        """
        a = self._agente()

        en_sin_categoria = (
            Agent.objects.filter(pk=a.pk)
            .filter(filtro_por_veredicto(StorageSanitizationVerdict.NO_CATEGORY))
            .exists()
        )
        en_sin_dato = (
            Agent.objects.filter(pk=a.pk)
            .filter(filtro_por_veredicto(StorageSanitizationVerdict.NO_DATA))
            .exists()
        )

        self.assertFalse(en_sin_categoria)
        self.assertTrue(en_sin_dato)

    def test_cada_agente_cae_en_exactamente_un_veredicto(self):
        """Ningún equipo puede quedar fuera de todos los filtros ni en dos.

        Quedar fuera de todos es peor que un veredicto equivocado: el equipo
        desaparece del panel y nadie lo echa de menos.
        """
        casos = []

        a = self._agente()
        casos.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_HDD)
        casos.append(a)

        a = self._agente()
        _estado(a, capabilities_probed=False)
        _disco(a, media_type_code=STORAGE_MEDIA_TYPE_SSD)
        casos.append(a)

        for agent in casos:
            cuantos = [
                v
                for v in StorageSanitizationVerdict.values
                if Agent.objects.filter(pk=agent.pk)
                .filter(filtro_por_veredicto(v))
                .exists()
            ]
            self.assertEqual(
                len(cuantos), 1, f"{agent.hostname} cayó en {cuantos}, debía caer en 1"
            )


class TestEndpointsDeMedios(ObserverTestCase):
    """El panel y el detalle, por HTTP, que es como los usa la consola."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

    def _agente(self, **kw):
        return baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS, **kw)

    def test_la_flota_muestra_al_que_nunca_reporto(self):
        """🔑 El equipo sin fila tiene que APARECER, no desaparecer.

        Es la razón por la que la consulta sale de `Agent` y no de la tabla de
        medios: el que nunca contestó es justamente el que hay que ir a mirar.
        """
        a = self._agente()

        r = self.client.get("/agents/storagemedia/")

        self.assertEqual(r.status_code, 200)
        filas = {f["agent_id"]: f for f in r.data}
        self.assertIn(a.agent_id, filas)
        self.assertEqual(
            filas[a.agent_id]["verdict"], StorageSanitizationVerdict.NO_DATA
        )
        self.assertIsNone(filas[a.agent_id]["measured_at"])

    def test_la_flota_filtra_por_veredicto(self):
        magnetico = self._agente()
        _estado(magnetico, capabilities_probed=True)
        _disco(magnetico, media_type_code=STORAGE_MEDIA_TYPE_HDD)

        sin_dato = self._agente()

        r = self.client.get(
            f"/agents/storagemedia/?verdict={StorageSanitizationVerdict.CLEAR_REMOTE}"
        )

        self.assertEqual(r.status_code, 200)
        ids = {f["agent_id"] for f in r.data}
        self.assertIn(magnetico.agent_id, ids)
        self.assertNotIn(sin_dato.agent_id, ids)

    def test_un_filtro_desconocido_no_devuelve_la_flota_entera(self):
        """Un filtro que no existe no puede leerse como «todos tienen vía»."""
        self._agente()

        r = self.client.get("/agents/storagemedia/?verdict=inventado")

        self.assertNotEqual(r.status_code, 200)

    def test_la_flota_no_trae_otras_plataformas(self):
        linux = baker.make_recipe("agents.agent", plat=AgentPlat.LINUX)

        r = self.client.get("/agents/storagemedia/")

        self.assertNotIn(linux.agent_id, {f["agent_id"] for f in r.data})

    def test_un_equipo_con_dos_discos_aparece_una_sola_vez(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, pnp_device_id="SISTEMA", is_system_disk=True)
        _disco(a, pnp_device_id="DATOS", is_system_disk=False)

        r = self.client.get("/agents/storagemedia/")

        apariciones = [f for f in r.data if f["agent_id"] == a.agent_id]
        self.assertEqual(len(apariciones), 1)

    def test_el_detalle_trae_todos_los_discos_fijos(self):
        a = self._agente()
        _estado(a, capabilities_probed=True)
        _disco(a, pnp_device_id="SISTEMA", is_system_disk=True)
        _disco(a, pnp_device_id="DATOS", is_system_disk=False)
        _disco(a, pnp_device_id="USB", removable=True)

        r = self.client.get(f"/agents/{a.agent_id}/storagemedia/")

        self.assertEqual(r.status_code, 200)
        ids = [d["pnp_device_id"] for d in r.data["media"]]
        self.assertEqual(ids, ["SISTEMA", "DATOS"])

    def test_el_detalle_de_un_equipo_sin_reporte_no_revienta(self):
        a = self._agente()

        r = self.client.get(f"/agents/{a.agent_id}/storagemedia/")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["verdict"], StorageSanitizationVerdict.NO_DATA)
        self.assertEqual(r.data["media"], [])
        self.assertIsNone(r.data["supported"])

    def test_el_error_de_consulta_viaja_como_causa(self):
        a = self._agente()
        _estado(a, query_error="acceso denegado al espacio de nombres")
        _disco(a)

        r = self.client.get(f"/agents/{a.agent_id}/storagemedia/")

        self.assertEqual(r.data["query_error"], "acceso denegado al espacio de nombres")
        self.assertEqual(r.data["verdict"], StorageSanitizationVerdict.NO_DATA)
        # Y los discos guardados siguen ahí: el error no los borró.
        self.assertEqual(len(r.data["media"]), 1)

    def test_no_autenticado(self):
        self.client.logout()
        self.check_not_authenticated("get", "/agents/storagemedia/")
