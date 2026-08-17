"""Feature 037 · Fase 2 — el panel de cifrado y su veredicto (T013).

Lo que se prueba acá es lo que puede mentir en silencio:

- que los **cuatro** estados de RF-04 sigan siendo cuatro. La regla ingenua —«si
  no dice que está cifrado, está sin cifrar»— es plausible, es la que se escribe
  sola, y convierte a todo equipo del que no sabemos nada en un incumplidor.
  RN-A03 existe para prohibirla y acá tiene su control positivo;
- que la versión **SQL** del veredicto (la del filtro) y la versión **Python**
  (la de cada fila) den lo mismo caso por caso. Son dos copias de una regla y
  divergen sin avisar: el equipo aparecería en un filtro con una etiqueta y en
  otro con otra;
- que un reporte que **falló** no borre el último estado conocido;
- que el panel muestre a los equipos que **nunca reportaron**, que son los que
  más importan y los que un listado hecho desde la tabla de cifrado perdería;
- que el alcance por rol se aplique (RN-A08) y que un cliente ajeno no se filtre.
"""

from django.utils import timezone as djangotime
from model_bakery import baker

from agents.diskencryption import derivar_estado, filtro_por_estado
from agents.models import Agent, DiskEncryptionHistory, DiskEncryptionVolume
from observerrmm.constants import AgentPlat, DiskEncryptionStatus
from observerrmm.test import ObserverTestCase

base_url = "/agents"


def _volumen(agent, **kwargs):
    """Un volumen con lo mínimo poblado; los tests sobrescriben lo que importa."""
    datos = {
        "device_id": r"\\?\Volume{11111111-1111-1111-1111-111111111111}\\",
        "drive_letter": "C:",
        "protection_status": 1,
        "conversion_status": 1,
        "encryption_method": 6,
        "volume_type": 0,
        "is_system_volume": True,
        "measured_at": djangotime.now(),
    }
    datos.update(kwargs)
    return DiskEncryptionVolume.objects.create(agent=agent, **datos)


def _estado(agent, **kwargs):
    from agents.models import DiskEncryptionState

    datos = {"supported": True, "query_error": None, "measured_at": djangotime.now()}
    datos.update(kwargs)
    return DiskEncryptionState.objects.create(agent=agent, **datos)


class TestVeredictoDeCifrado(ObserverTestCase):
    """La regla de RN-A02 y RN-A03, sin pasar por HTTP."""

    def setUp(self):
        self.setup_coresettings()

    def _agente(self):
        return baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)

    def test_los_cuatro_estados(self):
        casos = {}

        nunca_reporto = self._agente()
        casos[DiskEncryptionStatus.NO_DATA] = nunca_reporto

        cifrado = self._agente()
        _estado(cifrado)
        _volumen(cifrado, protection_status=1)
        casos[DiskEncryptionStatus.ENCRYPTED] = cifrado

        sin_cifrar = self._agente()
        _estado(sin_cifrar)
        _volumen(sin_cifrar, protection_status=0)
        casos[DiskEncryptionStatus.UNENCRYPTED] = sin_cifrar

        no_soportado = self._agente()
        _estado(no_soportado, supported=False)
        casos[DiskEncryptionStatus.UNSUPPORTED] = no_soportado

        for esperado, agent in casos.items():
            got = derivar_estado(Agent.objects.get(pk=agent.pk))
            self.assertEqual(got, esperado, f"{agent.hostname}: {got} != {esperado}")

    def test_control_positivo_la_regla_ingenua_fusiona_sin_dato_con_sin_cifrar(self):
        """El control que le da valor al resto (RN-A03).

        La regla ingenua es la que se escribe sin pensarlo: «cifrado si hay un
        volumen de sistema protegido, y si no, sin cifrar». Coincide con la buena
        en tres de los cuatro casos, y en el cuarto —el equipo del que no
        sabemos nada— afirma algo falso sobre un equipo que quizá sí está
        cifrado. Si algún día las dos coincidieran en todo, esta prueba avisa de
        que el guardián dejó de discriminar.
        """
        agent = self._agente()  # sin fila de estado: nunca reportó

        def regla_ingenua(a):
            volumen = a.disk_encryption_volumes.filter(is_system_volume=True).first()
            if volumen and volumen.protection_status == 1:
                return DiskEncryptionStatus.ENCRYPTED
            return DiskEncryptionStatus.UNENCRYPTED

        buena = derivar_estado(Agent.objects.get(pk=agent.pk))
        ingenua = regla_ingenua(Agent.objects.get(pk=agent.pk))

        self.assertEqual(buena, DiskEncryptionStatus.NO_DATA)
        self.assertEqual(
            ingenua,
            DiskEncryptionStatus.UNENCRYPTED,
            "el control está mal armado: la regla ingenua tiene que decir "
            "'sin cifrar' para que la divergencia pruebe algo",
        )
        self.assertNotEqual(buena, ingenua)

    def test_reporto_pero_sin_volumen_de_sistema_es_sin_dato(self):
        """Reportó, trae volúmenes, y ninguno es el de sistema.

        Pasa cuando `%SystemDrive%` viene vacío en el equipo: el agente prefiere
        no marcar ninguno antes que inventar el veredicto. La consola tiene que
        heredar esa prudencia y no leer la ausencia como cumplimiento.
        """
        agent = self._agente()
        _estado(agent)
        _volumen(agent, is_system_volume=False, drive_letter="D:", protection_status=1)

        self.assertEqual(
            derivar_estado(Agent.objects.get(pk=agent.pk)),
            DiskEncryptionStatus.NO_DATA,
        )

    def test_protection_status_desconocido_no_es_sin_cifrar(self):
        """El 2 de WMI es literalmente «desconocido» (RF-07)."""
        agent = self._agente()
        _estado(agent)
        _volumen(agent, protection_status=2)

        self.assertEqual(
            derivar_estado(Agent.objects.get(pk=agent.pk)),
            DiskEncryptionStatus.NO_DATA,
        )

    def test_error_de_consulta_gana_sobre_los_volumenes_viejos(self):
        """Con error, lo que había guardado no manda: no sabemos (RF-07).

        El caso real: el equipo reportó cifrado ayer y hoy la consulta falla. Las
        filas de volumen SIGUEN ahí a propósito —el handler no las borra cuando
        la lectura falla, para no perder el último estado conocido— y aun así el
        veredicto de hoy tiene que ser «sin dato», nunca «cifrado».
        """
        agent = self._agente()
        _estado(agent, query_error="Espacio de nombres no valido")
        _volumen(agent, protection_status=1)

        self.assertEqual(
            derivar_estado(Agent.objects.get(pk=agent.pk)),
            DiskEncryptionStatus.NO_DATA,
        )

    def test_sql_y_python_coinciden(self):
        """El guardián de las dos copias de la regla.

        Cada agente de la lista se clasifica con la versión Python y después se
        busca con la versión SQL. Si un caso cae en estados distintos, una de las
        dos se quedó atrás — que es exactamente lo que pasa cuando alguien
        agrega un estado y toca sólo un lado del archivo.
        """
        agentes = []

        agentes.append(self._agente())  # sin reporte

        a = self._agente()
        _estado(a)
        _volumen(a, protection_status=1)
        agentes.append(a)

        a = self._agente()
        _estado(a)
        _volumen(a, protection_status=0)
        agentes.append(a)

        a = self._agente()
        _estado(a)
        _volumen(a, protection_status=2)
        agentes.append(a)

        a = self._agente()
        _estado(a, supported=False)
        agentes.append(a)

        a = self._agente()
        _estado(a, query_error="fallo la consulta")
        _volumen(a, protection_status=1)
        agentes.append(a)

        # 🪤 El error VACÍO: en Python una cadena vacía es falsa, en SQL
        # `query_error IS NOT NULL` sería verdadera. Si el filtro no tratara los
        # dos igual, este agente saldría en un estado por el filtro y en otro en
        # su propia fila.
        a = self._agente()
        _estado(a, query_error="")
        _volumen(a, protection_status=1)
        agentes.append(a)

        a = self._agente()
        _estado(a)
        _volumen(a, is_system_volume=False, drive_letter="E:", protection_status=1)
        agentes.append(a)

        # Sin soporte Y con error a la vez. El agente no puede producirlo hoy —el
        # «no soportado» viaja con error nulo— pero las columnas lo admiten, y lo
        # que este caso fija es el ORDEN de las guardas: el error gana, porque
        # «no sabemos» no puede degradarse a una afirmación sobre el equipo.
        a = self._agente()
        _estado(a, supported=False, query_error="acceso denegado")
        agentes.append(a)

        for agent in agentes:
            esperado = derivar_estado(Agent.objects.get(pk=agent.pk))
            for estado in DiskEncryptionStatus.values:
                encontrado = (
                    Agent.objects.filter(pk=agent.pk)
                    .filter(filtro_por_estado(estado))
                    .exists()
                )
                self.assertEqual(
                    encontrado,
                    estado == esperado,
                    f"{agent.hostname}: Python dice {esperado}, el filtro "
                    f"{estado} dice {'sí' if encontrado else 'no'}",
                )


class TestDiskEncryptionEndpoints(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.authenticate()
        self.agent = baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)
        self.url_flota = f"{base_url}/diskencryption/"
        self.url_detalle = f"{base_url}/{self.agent.agent_id}/diskencryption/"

    def test_flota_muestra_al_que_nunca_reporto(self):
        """El caso que un listado hecho desde la tabla de cifrado perdería."""
        r = self.client.get(self.url_flota, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        fila = r.data[0]
        self.assertEqual(fila["agent_id"], self.agent.agent_id)
        self.assertEqual(fila["state"], DiskEncryptionStatus.NO_DATA)
        self.assertIsNone(fila["supported"])
        self.assertIsNone(fila["measured_at"])
        self.assertIsNone(fila["system_volume"])

    def test_flota_no_trae_equipos_de_otras_plataformas(self):
        """La Fase A es Windows; mostrar el resto en «sin dato» sería ruido."""
        baker.make_recipe("agents.agent", plat=AgentPlat.LINUX)
        baker.make_recipe("agents.agent", plat=AgentPlat.DARWIN)

        r = self.client.get(self.url_flota, format="json")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["agent_id"], self.agent.agent_id)

    def test_flota_filtra_por_estado(self):
        _estado(self.agent)
        _volumen(self.agent, protection_status=1)

        otro = baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)
        _estado(otro)
        _volumen(otro, protection_status=0)

        r = self.client.get(
            f"{self.url_flota}?state={DiskEncryptionStatus.ENCRYPTED}", format="json"
        )
        self.assertEqual([f["agent_id"] for f in r.data], [self.agent.agent_id])

        r = self.client.get(
            f"{self.url_flota}?state={DiskEncryptionStatus.UNENCRYPTED}", format="json"
        )
        self.assertEqual([f["agent_id"] for f in r.data], [otro.agent_id])

    def test_flota_rechaza_un_filtro_desconocido(self):
        """No puede devolver la flota entera como si hubiera filtrado."""
        r = self.client.get(f"{self.url_flota}?state=inventado", format="json")
        self.assertEqual(r.status_code, 400)

    def test_flota_filtra_por_cliente_y_sitio(self):
        otro = baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)

        r = self.client.get(
            f"{self.url_flota}?client={self.agent.client.pk}", format="json"
        )
        self.assertEqual([f["agent_id"] for f in r.data], [self.agent.agent_id])

        r = self.client.get(f"{self.url_flota}?site={otro.site.pk}", format="json")
        self.assertEqual([f["agent_id"] for f in r.data], [otro.agent_id])

    def test_flota_recorta_por_rol(self):
        """RN-A08: el estado de cifrado lo ve quien ya puede ver el agente."""
        ajeno = baker.make_recipe("agents.agent", plat=AgentPlat.WINDOWS)

        user = self.create_user_with_roles([])
        self.client.force_authenticate(user=user)
        self.check_not_authorized("get", self.url_flota)

        user.role.can_list_agents = True
        user.role.save()
        r = self.check_authorized("get", self.url_flota)
        self.assertEqual(len(r.data), 2)

        user.role.can_view_clients.set([self.agent.client])
        r = self.client.get(self.url_flota, format="json")
        self.assertEqual([f["agent_id"] for f in r.data], [self.agent.agent_id])

        # Y el detalle del equipo ajeno tampoco: sin esto, el índice recortado
        # sería una barrera de vitrina.
        self.check_not_authorized("get", f"{base_url}/{ajeno.agent_id}/diskencryption/")

    def test_detalle_trae_todos_los_volumenes_y_el_historial(self):
        _estado(self.agent)
        _volumen(self.agent, protection_status=1, key_protector_count=2)
        _volumen(
            self.agent,
            device_id=r"\\?\Volume{22222222-2222-2222-2222-222222222222}\\",
            drive_letter=None,
            is_system_volume=False,
            protection_status=0,
            key_protector_count=None,
        )
        DiskEncryptionHistory.objects.create(
            agent=self.agent,
            device_id=r"\\?\Volume{11111111-1111-1111-1111-111111111111}\\",
            previous_status=None,
            new_status=1,
        )

        r = self.client.get(self.url_detalle, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["volumes"]), 2)
        # El de sistema va primero: es el que decide el veredicto.
        self.assertTrue(r.data["volumes"][0]["is_system_volume"])
        self.assertEqual(r.data["volumes"][0]["key_protector_count"], 2)
        # Y el nulo sigue siendo nulo: un 0 diría "cero protectores" (RN-A06).
        self.assertIsNone(r.data["volumes"][1]["key_protector_count"])
        self.assertIsNone(r.data["volumes"][1]["drive_letter"])
        self.assertEqual(len(r.data["history"]), 1)
        self.assertIsNone(r.data["history"][0]["previous_status"])
        self.assertIsNotNone(r.data["measured_at"])

    def test_detalle_de_un_equipo_sin_reporte_no_revienta(self):
        r = self.client.get(self.url_detalle, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["supported"])
        self.assertEqual(r.data["volumes"], [])
        self.assertEqual(r.data["history"], [])

    def test_no_autenticado(self):
        self.check_not_authenticated("get", self.url_flota)
        self.check_not_authenticated("get", self.url_detalle)
