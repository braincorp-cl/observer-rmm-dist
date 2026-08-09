"""Censo de nodos Mesh huérfanos: el cruce y lo que se denuncia.

Un nodo huérfano no aparece en ninguna pantalla del RMM —por definición: no hay
fila que lo apunte— así que el único testigo de que existe es este censo. Si el
cruce se equivoca hacia abajo, el censo devuelve «sin huérfanos» y todos se
quedan tranquilos. Ese cero silencioso es lo que estos tests atacan:

1. Que un nodo SIN dueño se cuente (control positivo del cruce).
2. Que un nodo CON dueño no se cuente (control negativo: sin esto, un cruce que
   marcara todo como huérfano también «pasaría» el punto 1).
3. Que un `mesh_node_id` ilegible NO se cuele como conocido — eso taparía un
   huérfano de verdad — y que quede denunciado.
4. Que la falla de MeshCentral se reporte como falla, y NUNCA como «sin
   huérfanos»: sin la lista del mesh, el cero es mentira.
5. Que el hallazgo se escriba en nivel ERROR. `DebugLog.warning` no se escribe
   si `agent_debug_level` es ERROR, que es como corre la flota; un aviso que
   nadie vería es lo mismo que no avisar.
"""

from unittest.mock import AsyncMock, patch

from model_bakery import baker

from core.mesh_orphans import census, known_node_ids
from core.tasks import mesh_orphan_nodes_census_task
from logs.models import DebugLog
from observerrmm.constants import DebugLogLevel
from observerrmm.test import ObserverTestCase

# Id real de la flota (FAZOCAR, 2026-07-28) en la forma hex en que lo guarda
# Agent.mesh_node_id. Su forma b64 —la que usa MeshCentral— la calcula el propio
# código bajo prueba; escribirla a mano acá sería reimplementar la conversión en
# el test y taparía justo el error que importa.
ID_HEX = "854BF86A14715296EAFA759DD788BDB243AC4FD063A8363D2BEE940E330DD340CA737DE96498B16EAE9D79DBF135D798"
ID_HEX_OTRO = "B5A5637418544B82ADEBE4C3F27B22DB7B207A756061AE52BA7CE2AA6BFE6D3F9D2B4E0A1D5B3EF3044218F3D917AAD4"


def _node_id(hex_id: str) -> str:
    """La forma `node//<b64>` que devuelve MeshCentral, vía el mismo helper que
    usa el código de producción."""
    from core.utils import _b64_to_hex

    return f"node//{_b64_to_hex(hex_id)}"


class TestKnownNodeIds(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_agente_con_nodo_queda_como_conocido(self):
        baker.make_recipe("agents.agent", mesh_node_id=ID_HEX)

        conocidos, ilegibles = known_node_ids()

        self.assertIn(_node_id(ID_HEX), conocidos)
        self.assertEqual(ilegibles, 0)

    def test_mesh_node_id_ilegible_no_cuenta_como_conocido(self):
        """Contarlo como conocido escondería un huérfano: cualquier nodo podría
        quedar «explicado» por una fila cuyo id nadie puede leer."""
        baker.make_recipe("agents.agent", mesh_node_id="no-es-hex")

        conocidos, ilegibles = known_node_ids()

        self.assertEqual(conocidos, set())
        self.assertEqual(ilegibles, 1)

    def test_agente_sin_nodo_no_aporta_nada(self):
        baker.make_recipe("agents.agent", mesh_node_id="")

        conocidos, ilegibles = known_node_ids()

        self.assertEqual(conocidos, set())
        self.assertEqual(ilegibles, 0)


class TestCensus(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def _correr_censo(self, nodos):
        with patch("core.mesh_orphans.get_mesh_ws_url", return_value="ws://x"), patch(
            "core.mesh_orphans.get_mesh_device_id", new=AsyncMock(return_value="meshid")
        ), patch(
            "core.mesh_orphans.list_group_nodes", new=AsyncMock(return_value=nodos)
        ):
            return census()

    def test_nodo_sin_dueno_sale_como_huerfano(self):
        r = self._correr_censo([{"_id": _node_id(ID_HEX), "name": "HP-ProOne-400"}])

        self.assertEqual(len(r["orphans"]), 1)
        self.assertEqual(r["orphans"][0]["name"], "HP-ProOne-400")
        self.assertEqual(r["total_nodes"], 1)

    def test_nodo_con_dueno_no_sale_como_huerfano(self):
        """Control negativo del test anterior: sin él, un cruce que marcara TODO
        como huérfano pasaría igual."""
        baker.make_recipe("agents.agent", mesh_node_id=ID_HEX)

        r = self._correr_censo([{"_id": _node_id(ID_HEX), "name": "FAZOCAR"}])

        self.assertEqual(r["orphans"], [])
        self.assertEqual(r["known"], 1)

    def test_separa_el_huerfano_del_que_tiene_dueno(self):
        baker.make_recipe("agents.agent", mesh_node_id=ID_HEX)

        r = self._correr_censo(
            [
                {"_id": _node_id(ID_HEX), "name": "con dueño"},
                {"_id": _node_id(ID_HEX_OTRO), "name": "sin dueño"},
            ]
        )

        self.assertEqual([n["name"] for n in r["orphans"]], ["sin dueño"])
        self.assertEqual(r["total_nodes"], 2)

    def test_sin_grupo_no_devuelve_cero_sino_que_falla(self):
        """Si el grupo del RMM no está, la lista de nodos no significa nada y
        «cero huérfanos» sería una lectura inventada."""
        with patch("core.mesh_orphans.get_mesh_ws_url", return_value="ws://x"), patch(
            "core.mesh_orphans.get_mesh_device_id", new=AsyncMock(return_value=None)
        ):
            with self.assertRaises(RuntimeError):
                census()


class TestCensusTask(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()

    def test_sin_huerfanos_no_ensucia_el_debug_log(self):
        with patch(
            "core.mesh_orphans.census",
            return_value={
                "group": "ObserverRMM",
                "total_nodes": 7,
                "known": 7,
                "skipped": 0,
                "orphans": [],
            },
        ):
            ret = mesh_orphan_nodes_census_task()

        self.assertIn("sin huérfanos", ret)
        self.assertEqual(DebugLog.objects.count(), 0)

    def test_con_huerfanos_denuncia_en_nivel_error(self):
        with patch(
            "core.mesh_orphans.census",
            return_value={
                "group": "ObserverRMM",
                "total_nodes": 8,
                "known": 7,
                "skipped": 0,
                "orphans": [{"_id": _node_id(ID_HEX), "name": "HP-ProOne-400"}],
            },
        ):
            ret = mesh_orphan_nodes_census_task()

        self.assertIn("1 huérfano", ret)
        log = DebugLog.objects.filter(log_level=DebugLogLevel.ERROR).first()
        self.assertIsNotNone(log)
        self.assertIn("HP-ProOne-400", log.message)
        # El mensaje tiene que decir qué hacer: el borrado NO es automático y el
        # que lee esto a las 4 de la mañana no tiene por qué saberlo.
        self.assertIn("bulk_delete_orphans_meshagents", log.message)

    def test_ids_ilegibles_quedan_denunciados(self):
        with patch(
            "core.mesh_orphans.census",
            return_value={
                "group": "ObserverRMM",
                "total_nodes": 3,
                "known": 2,
                "skipped": 1,
                "orphans": [],
            },
        ):
            mesh_orphan_nodes_census_task()

        self.assertTrue(
            DebugLog.objects.filter(
                log_level=DebugLogLevel.ERROR, message__contains="ilegible"
            ).exists()
        )

    def test_meshcentral_caido_se_reporta_como_falla(self):
        """El modo de falla que importa: que una caída del mesh se lea como
        «no hay huérfanos» y el censo quede en verde para siempre."""
        with patch("core.mesh_orphans.census", side_effect=OSError("mesh caído")):
            ret = mesh_orphan_nodes_census_task()

        self.assertTrue(ret.startswith("error:"))
        self.assertNotIn("sin huérfanos", ret)
        self.assertTrue(
            DebugLog.objects.filter(
                log_level=DebugLogLevel.ERROR, message__contains="no se pudo completar"
            ).exists()
        )
