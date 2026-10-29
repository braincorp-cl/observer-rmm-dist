"""Recetas de model_bakery para `logs`.

⚠️ DEPENDENCIA DE ORDEN CONOCIDA (anotada, hoy inactiva — no es una fuga)

Los `cycle(...)` de abajo se construyen **al importar el módulo**, así que su
posición es estado de MÓDULO y NO se reinicia entre tests: sobrevive al rollback
del `TestCase` igual que sobreviviría una variable global. Cada
`baker.make_recipe("logs.object_logs", _quantity=N)` consume N valores y deja el
iterador donde quedó, de modo que lo que produce una llamada depende de cuántas
llamadas hubo antes — es decir, del orden de los tests, que `pytest-randomly`
baraja en cada corrida.

Está medido, no es teórico. `object_types` tiene 10 valores (USER es el primero)
y `logs/tests.py::create_audit_records` pide `_quantity=17`, así que las filas
con `object_type=USER` que aporta `object_logs` según el offset de entrada son:

    llamada 0 → offset   0 → 2 filas USER   (+24 de login_logs = 26) ✅
    llamada 1 → offset  17 → 2 filas USER   (+24 = 26)               ✅
    llamada 2 → offset  34 → 2 filas USER   (+24 = 26)               ✅
    llamada 3 → offset  51 → 1 fila  USER   (+24 = 25)               ❌
    llamada 6 → offset 102 → 1 fila  USER   (+24 = 25)               ❌
    llamada 9 → offset 153 → 1 fila  USER   (+24 = 25)               ❌

La aserción `{"objectFilter": ["user"]}: 26` de `test_get_audit_logs` sólo se
sostiene porque hoy `create_audit_records()` tiene EXACTAMENTE dos invocaciones
(`logs/tests.py:107` y `:300`), que caen en los offsets 0 y 17. Un tercer
llamador en el mismo proceso —un test nuevo, `pytest-repeat`, cualquier otro uso
de `logs.object_logs`— arma el fallo, y como el reparto de offsets depende de la
semilla, saldría rojo de forma intermitente y no reproducible.

Si algún día hace falta un tercer llamador: no basta con subir el número
esperado. Hay que quitarle el estado al fixture, p. ej. construyendo el `cycle`
dentro de cada llamada en vez de a nivel de módulo, o pasando `object_type`
explícito desde el test. Mientras haya dos llamadas, esto es una nota, no un bug.

(Ojo: `login_logs` NO tiene el problema para la aserción de `actionFilter:
["login"]`. Su ciclo es de 2 acciones y el fixture crea 11+13=24 filas, y 24
filas alternando dan 12 `login` desde cualquier offset.)
"""

from itertools import cycle

from model_bakery.recipe import Recipe

from observerrmm.constants import AuditActionType, AuditObjType, PAAction, PAStatus

object_types = [
    AuditObjType.USER,
    AuditObjType.SCRIPT,
    AuditObjType.AGENT,
    AuditObjType.POLICY,
    AuditObjType.WINUPDATE,
    AuditObjType.CLIENT,
    AuditObjType.SITE,
    AuditObjType.CHECK,
    AuditObjType.AUTOTASK,
    AuditObjType.CORE,
]

object_actions = [
    AuditActionType.ADD,
    AuditActionType.MODIFY,
    AuditActionType.VIEW,
    AuditActionType.DELETE,
]
agent_actions = [
    AuditActionType.REMOTE_SESSION,
    AuditActionType.EXEC_SCRIPT,
    AuditActionType.EXEC_COMMAND,
]
login_actions = [AuditActionType.FAILED_LOGIN, AuditActionType.LOGIN]

agent_logs = Recipe(
    "logs.AuditLog", action=cycle(agent_actions), object_type=AuditObjType.AGENT
)

object_logs = Recipe(
    "logs.AuditLog", action=cycle(object_actions), object_type=cycle(object_types)
)

login_logs = Recipe(
    "logs.AuditLog", action=cycle(login_actions), object_type=AuditObjType.USER
)

pending_agentupdate_action = Recipe(
    "logs.PendingAction",
    action_type=PAAction.AGENT_UPDATE,
    status=PAStatus.PENDING,
)
