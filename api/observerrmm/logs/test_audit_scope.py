"""El registro de auditoría recorta por cliente también en las filas sin agente.

🔴 Lo que esto fija es una fuga de alcance entre clientes. `_audit_log_filter`
(`observerrmm/permissions.py`) construía su `Q` así:

    if can_view_sites:  ...; agent_filter = Q(agent_id=None)
    if can_view_clients: ...; agent_filter = Q(agent_id=None)
    return Q(sites_queryset | clients_queryset | agent_filter)

`agent_filter` entraba con OR y sin ninguna condición más, de modo que TODA fila
de `AuditLog` sin agente quedaba visible para cualquier rol con
`can_view_auditlogs`, cualquiera fuera su alcance. Y las filas sin agente son
justo las sensibles: cambios de rol, altas y bajas de usuario, ediciones de
cliente y de sitio, `CoreSettings`.

Importa porque una instalación sirve a VARIOS clientes con roles recortados por
cliente y por sitio (feature 052, «nadie delega la custodia»): un rol limitado al
cliente A no debe ver la actividad del cliente B. Con el OR suelto la veía
entera, y el panel de auditoría era el camino más corto para enumerar la
operación de la competencia dentro del mismo servidor.
"""

from model_bakery import baker

from accounts.models import Role, User
from logs.models import AuditLog
from observerrmm.constants import AuditActionType, AuditObjType
from observerrmm.test import ObserverTestCase

URL = "/logs/audit/"

PAGINATION = {
    "rowsPerPage": 100,
    "page": 1,
    "sortBy": "entry_time",
    "descending": True,
}


class AuditLogScopeTests(ObserverTestCase):
    """Dos clientes, un rol recortado al A, actividad administrativa del B."""

    def setUp(self):
        self.authenticate()
        self.setup_coresettings()

        self.cliente_a = baker.make("clients.Client", name="CLIENTE-A")
        self.sitio_a = baker.make("clients.Site", client=self.cliente_a)
        self.agente_a = baker.make(
            "agents.Agent", site=self.sitio_a, hostname="BOX-A", agent_id="aid-a"
        )

        self.cliente_b = baker.make("clients.Client", name="CLIENTE-B")
        self.sitio_b = baker.make("clients.Site", client=self.cliente_b)
        self.agente_b = baker.make(
            "agents.Agent", site=self.sitio_b, hostname="BOX-B", agent_id="aid-b"
        )

        # 🪤 Nada de conteos absolutos ni de reusar el fixture de `logs/tests.py`
        # (`create_audit_records`, que depende del orden de importación de sus
        # `cycle(...)`): se siembra lo justo y se afirma por pertenencia.
        #
        # ACTIVIDAD SIN AGENTE DEL CLIENTE B. Es la que el rol de A no debe ver:
        # quien administra el cliente B le tocó el perfil a una cuenta y le editó
        # el sitio. Ninguna de las dos filas cuelga de un agente.
        self.fila_rol_b = AuditLog.objects.create(
            username="admin-b",
            object_type=AuditObjType.USER,
            action=AuditActionType.MODIFY,
            message="admin-b modified user operador-b",
            before_value={"role": None},
            after_value={"role": "Administrador CLIENTE-B"},
        )
        self.fila_sitio_b = AuditLog.objects.create(
            username="admin-b",
            object_type=AuditObjType.SITE,
            action=AuditActionType.MODIFY,
            message="admin-b modified site Casa Central B",
        )

        # Actividad CON agente de cada cliente: control de que el recorte que ya
        # funcionaba sigue funcionando.
        self.fila_agente_a = AuditLog.objects.create(
            username="admin-a",
            agent=self.agente_a.hostname,
            agent_id=self.agente_a.agent_id,
            object_type=AuditObjType.AGENT,
            action=AuditActionType.REMOTE_SESSION,
            message="admin-a used Mesh Central to initiate a remote session",
        )
        self.fila_agente_b = AuditLog.objects.create(
            username="admin-b",
            agent=self.agente_b.hostname,
            agent_id=self.agente_b.agent_id,
            object_type=AuditObjType.AGENT,
            action=AuditActionType.REMOTE_SESSION,
            message="admin-b used Mesh Central to initiate a remote session",
        )

        # El rol recortado al cliente A, con permiso de auditoría.
        self.rol_a = Role.objects.create(
            name="auditor-cliente-a", can_view_auditlogs=True
        )
        self.rol_a.can_view_clients.set([self.cliente_a])
        self.operador_a = User.objects.create_user(username="operador-a", password="x")
        self.operador_a.role = self.rol_a
        self.operador_a.save()

        # Su propia actividad sin agente: tiene que seguir viéndola (es la
        # trazabilidad de lo que él mismo hizo).
        self.fila_propia = AuditLog.objects.create(
            username=self.operador_a.username,
            object_type=AuditObjType.CLIENT,
            action=AuditActionType.MODIFY,
            message="operador-a modified client CLIENTE-A",
        )

    def _ids_visibles(self, user):
        self.client.force_authenticate(user=user)
        r = self.client.patch(URL, {"pagination": PAGINATION}, format="json")
        self.assertEqual(r.status_code, 200)
        return {fila["id"] for fila in r.data["audit_logs"]}

    def test_rol_recortado_no_ve_la_actividad_sin_agente_de_otro_cliente(self):
        """🔴 La fuga: el rol del cliente A veía los cambios de rol del B."""
        visibles = self._ids_visibles(self.operador_a)

        self.assertNotIn(
            self.fila_rol_b.id,
            visibles,
            "el rol recortado al cliente A ve un cambio de perfil del cliente B",
        )
        self.assertNotIn(
            self.fila_sitio_b.id,
            visibles,
            "el rol recortado al cliente A ve la edición de un sitio del cliente B",
        )

    def test_rol_recortado_sigue_viendo_lo_suyo(self):
        """El recorte no le quita al rol ni su alcance ni su propia traza."""
        visibles = self._ids_visibles(self.operador_a)

        self.assertIn(self.fila_agente_a.id, visibles, "perdió su propio alcance")
        self.assertIn(self.fila_propia.id, visibles, "perdió su propia trazabilidad")
        self.assertNotIn(self.fila_agente_b.id, visibles, "ve un equipo ajeno")

    def test_rol_recortado_por_sitio_tampoco(self):
        """Mismo recorte cuando el alcance se delega por SITIO y no por cliente."""
        rol = Role.objects.create(name="auditor-sitio-a", can_view_auditlogs=True)
        rol.can_view_sites.set([self.sitio_a])
        user = User.objects.create_user(username="operador-sitio-a", password="x")
        user.role = rol
        user.save()

        visibles = self._ids_visibles(user)

        self.assertIn(self.fila_agente_a.id, visibles)
        self.assertNotIn(self.fila_rol_b.id, visibles)
        self.assertNotIn(self.fila_sitio_b.id, visibles)
        self.assertNotIn(self.fila_agente_b.id, visibles)

    def test_alcance_por_sitio_y_por_cliente_a_la_vez_no_se_pisan(self):
        """La rama de clientes pisaba la de sitios y el recorte por sitio se perdía.

        Un rol con alcance al SITIO de A y al CLIENTE de B tiene que ver los dos
        equipos. Antes `clients_queryset` no se asignaba nunca —la segunda rama
        escribía otra vez sobre `sites_queryset`— así que el alcance por sitio
        desaparecía en silencio. Acá se nota porque el sitio de A y el cliente de
        B no se solapan.
        """
        rol = Role.objects.create(name="auditor-mixto", can_view_auditlogs=True)
        rol.can_view_sites.set([self.sitio_a])
        rol.can_view_clients.set([self.cliente_b])
        user = User.objects.create_user(username="operador-mixto", password="x")
        user.role = rol
        user.save()

        visibles = self._ids_visibles(user)

        self.assertIn(self.fila_agente_a.id, visibles, "perdió el alcance por sitio")
        self.assertIn(self.fila_agente_b.id, visibles, "perdió el alcance por cliente")

    def test_sin_alcance_sigue_viendo_todo(self):
        """Alcance vacío = todo, que es el criterio del resto de los permisos.

        Un rol con permiso de auditoría y sin recorte de cliente ni de sitio es
        el administrador de la instalación completa. El arreglo no se lo quita:
        lo que se recorta es el rol RECORTADO.
        """
        rol = Role.objects.create(name="auditor-global", can_view_auditlogs=True)
        user = User.objects.create_user(username="operador-global", password="x")
        user.role = rol
        user.save()

        visibles = self._ids_visibles(user)

        for fila in (
            self.fila_rol_b,
            self.fila_sitio_b,
            self.fila_agente_a,
            self.fila_agente_b,
        ):
            self.assertIn(fila.id, visibles)

    def test_superusuario_ve_la_revision_transversal(self):
        """La lectura cruzada entre clientes queda donde corresponde."""
        visibles = self._ids_visibles(self.john)

        for fila in (
            self.fila_rol_b,
            self.fila_sitio_b,
            self.fila_agente_a,
            self.fila_agente_b,
            self.fila_propia,
        ):
            self.assertIn(fila.id, visibles)
