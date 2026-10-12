"""047 · permisos Mesh por grupo.

Los usuarios que ven todos los equipos (superusuarios y roles con Mesh sin
restricción de cliente ni sitio) reciben UN link al grupo de dispositivos en vez
de uno por equipo. Los restringidos siguen por equipo. Lo que estos tests atacan:

1. Reparto correcto: global ⇒ grupo; restringido ⇒ sus equipos; sin Mesh ⇒ nada.
2. Que un usuario con sólo el link al grupo NO se borre de Mesh (el sync borra a
   quien no tenga links de nodo: `users_to_delete_globally`).
3. Convergencia: el segundo sync no cambia nada.
4. Migración: el link al grupo se da ANTES de quitar los links por equipo.
5. Cambios de rol en ambos sentidos.
6. Sin un grupo único, se mantiene el reparto por equipo.
"""

from unittest.mock import patch

from model_bakery import baker

from core.tasks import sync_mesh_perms_task
from observerrmm.test import ObserverTestCase

ID_HEX_1 = "854BF86A14715296EAFA759DD788BDB243AC4FD063A8363D2BEE940E330DD340CA737DE96498B16EAE9D79DBF135D798"
ID_HEX_2 = "B5A5637418544B82ADEBE4C3F27B22DB7B207A756061AE52BA7CE2AA6BFE6D3F9D2B4E0A1D5B3EF3044218F3D917AAD4"
GROUP_ID = "mesh//grupo"


class FakeMesh:
    """MeshCentral en memoria: nodos con sus links, el grupo y los usuarios."""

    nodes: dict[str, set[str]] = {}
    group: set[str] = set()
    users: set[str] = set()
    group_ok = True
    calls: list[tuple] = []

    @classmethod
    def reset(cls, node_ids):
        cls.nodes = {n: set() for n in node_ids}
        cls.group = set()
        cls.users = set()
        cls.group_ok = True
        cls.calls = []

    def __init__(self, uri):
        self.mesh_users = {u: {"realname": ""} for u in FakeMesh.users}

    def mesh_action(self, *, payload, wait=True):
        assert payload["action"] == "nodes"
        return {
            "nodes": {
                GROUP_ID: [
                    {"_id": n, "links": {u: {} for u in links}}
                    for n, links in FakeMesh.nodes.items()
                ]
            }
        }

    def get_device_group(self, name):
        if not FakeMesh.group_ok:
            return None
        return {"_id": GROUP_ID, "links": {u: {} for u in FakeMesh.group}}

    def get_unique_mesh_users(self, ormm_agents_list):
        return list({l["_id"] for a in ormm_agents_list for l in a["links"]})

    def add_user_to_mesh(self, *, user_info):
        FakeMesh.calls.append(("adduser", user_info["_id"]))
        FakeMesh.users.add(user_info["_id"])

    def delete_user_from_mesh(self, *, mesh_user_id):
        FakeMesh.calls.append(("deleteuser", mesh_user_id))
        FakeMesh.users.discard(mesh_user_id)
        FakeMesh.group.discard(mesh_user_id)
        for links in FakeMesh.nodes.values():
            links.discard(mesh_user_id)

    def add_users_to_node(self, *, node_id, user_ids):
        FakeMesh.calls.append(("node+", node_id, tuple(sorted(user_ids))))
        FakeMesh.nodes[node_id].update(user_ids)

    def delete_users_from_node(self, *, node_id, user_ids):
        FakeMesh.calls.append(("node-", node_id, tuple(sorted(user_ids))))
        FakeMesh.nodes[node_id].difference_update(user_ids)

    def add_users_to_group(self, *, mesh_id, user_ids):
        FakeMesh.calls.append(("group+", tuple(sorted(user_ids))))
        FakeMesh.group.update(user_ids)

    def remove_users_from_group(self, *, mesh_id, user_ids):
        FakeMesh.calls.append(("group-", tuple(sorted(user_ids))))
        FakeMesh.group.difference_update(user_ids)

    def update_mesh_displayname(self, *, user_info):
        pass


@patch("core.tasks.get_mesh_ws_url", lambda: "ws://mesh")
@patch("core.tasks.MeshSync", FakeMesh)
class TestMeshGroupPerms(ObserverTestCase):
    def setUp(self):
        self.setup_coresettings()
        self.client1 = baker.make("clients.Client")
        self.client2 = baker.make("clients.Client")
        site1 = baker.make("clients.Site", client=self.client1)
        site2 = baker.make("clients.Site", client=self.client2)
        self.agent1 = baker.make_recipe(
            "agents.agent", site=site1, mesh_node_id=ID_HEX_1
        )
        self.agent2 = baker.make_recipe(
            "agents.agent", site=site2, mesh_node_id=ID_HEX_2
        )
        self.node1 = f"node//{self.agent1.hex_mesh_node_id}"
        self.node2 = f"node//{self.agent2.hex_mesh_node_id}"

        self.su = baker.make("accounts.User", username="admin", is_superuser=True)
        self.open_role = baker.make("accounts.Role", can_use_mesh=True)
        self.tech = baker.make("accounts.User", username="tech", role=self.open_role)
        self.narrow_role = baker.make("accounts.Role", can_use_mesh=True)
        self.narrow_role.can_view_clients.set([self.client1])
        self.narrow = baker.make(
            "accounts.User", username="narrow", role=self.narrow_role
        )
        no_mesh_role = baker.make("accounts.Role", can_use_mesh=False)
        self.nomesh = baker.make("accounts.User", username="nomesh", role=no_mesh_role)

        FakeMesh.reset([self.node1, self.node2])

    def test_reparto_global_al_grupo_y_restringido_por_equipo(self):
        sync_mesh_perms_task()

        globales = {self.su.mesh_user_id, self.tech.mesh_user_id}
        self.assertEqual(FakeMesh.group, globales)
        self.assertEqual(FakeMesh.nodes[self.node1], {self.narrow.mesh_user_id})
        self.assertEqual(FakeMesh.nodes[self.node2], set())
        self.assertEqual(FakeMesh.users, globales | {self.narrow.mesh_user_id})
        self.assertNotIn(self.nomesh.mesh_user_id, FakeMesh.users)

    def test_segundo_sync_no_cambia_nada_ni_borra_a_los_globales(self):
        sync_mesh_perms_task()
        FakeMesh.calls = []

        sync_mesh_perms_task()

        self.assertEqual(FakeMesh.calls, [])
        self.assertIn(self.su.mesh_user_id, FakeMesh.users)

    def test_migracion_da_el_grupo_antes_de_quitar_los_links_por_equipo(self):
        # Estado previo a la 047: todos con link por equipo, nadie en el grupo.
        everyone = {self.su.mesh_user_id, self.tech.mesh_user_id}
        FakeMesh.users = everyone | {self.narrow.mesh_user_id}
        FakeMesh.nodes[self.node1] = everyone | {self.narrow.mesh_user_id}
        FakeMesh.nodes[self.node2] = set(everyone)

        sync_mesh_perms_task()

        self.assertEqual(FakeMesh.group, everyone)
        self.assertEqual(FakeMesh.nodes[self.node1], {self.narrow.mesh_user_id})
        self.assertEqual(FakeMesh.nodes[self.node2], set())
        self.assertFalse(any(c[0] == "deleteuser" for c in FakeMesh.calls))
        kinds = [c[0] for c in FakeMesh.calls]
        self.assertLess(kinds.index("group+"), kinds.index("node-"))

    def test_de_global_a_restringido_y_vuelta(self):
        sync_mesh_perms_task()

        self.open_role.can_view_clients.set([self.client2])
        self.open_role.save()
        sync_mesh_perms_task()
        self.assertNotIn(self.tech.mesh_user_id, FakeMesh.group)
        self.assertIn(self.tech.mesh_user_id, FakeMesh.nodes[self.node2])
        self.assertNotIn(self.tech.mesh_user_id, FakeMesh.nodes[self.node1])
        self.assertIn(self.tech.mesh_user_id, FakeMesh.users)

        self.open_role.can_view_clients.clear()
        self.open_role.save()
        sync_mesh_perms_task()
        self.assertIn(self.tech.mesh_user_id, FakeMesh.group)
        self.assertNotIn(self.tech.mesh_user_id, FakeMesh.nodes[self.node2])
        self.assertIn(self.tech.mesh_user_id, FakeMesh.users)

    def test_global_que_pierde_mesh_se_borra(self):
        sync_mesh_perms_task()

        self.open_role.can_use_mesh = False
        self.open_role.save()
        sync_mesh_perms_task()

        self.assertNotIn(self.tech.mesh_user_id, FakeMesh.users)
        self.assertNotIn(self.tech.mesh_user_id, FakeMesh.group)

    def test_sin_grupo_unico_mantiene_links_por_equipo(self):
        FakeMesh.group_ok = False

        sync_mesh_perms_task()

        self.assertEqual(FakeMesh.group, set())
        for node in (self.node1, self.node2):
            self.assertIn(self.su.mesh_user_id, FakeMesh.nodes[node])
            self.assertIn(self.tech.mesh_user_id, FakeMesh.nodes[node])
        self.assertEqual(
            FakeMesh.nodes[self.node1] - FakeMesh.nodes[self.node2],
            {self.narrow.mesh_user_id},
        )
