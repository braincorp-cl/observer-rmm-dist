from rest_framework import permissions

from observerrmm.permissions import _has_perm, _has_perm_on_agent


class AgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if r.method == "GET":
            if "agent_id" in view.kwargs.keys():
                return _has_perm(r, "can_list_agents") and _has_perm_on_agent(
                    r.user, view.kwargs["agent_id"]
                )
            else:
                return _has_perm(r, "can_list_agents")
        elif r.method == "DELETE":
            return _has_perm(r, "can_uninstall_agents") and _has_perm_on_agent(
                r.user, view.kwargs["agent_id"]
            )
        else:
            if r.path == "/agents/maintenance/bulk/":
                return _has_perm(r, "can_edit_agent")
            else:
                return _has_perm(r, "can_edit_agent") and _has_perm_on_agent(
                    r.user, view.kwargs["agent_id"]
                )


class RecoverAgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if "agent_id" not in view.kwargs.keys():
            return _has_perm(r, "can_recover_agents")

        return _has_perm(r, "can_recover_agents") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class MeshPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_use_mesh") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class UpdateAgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_update_agents")


class ManageProcPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_manage_procs") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class EvtLogPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_view_eventlogs") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class SendCMDPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_send_cmd") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class RebootAgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_reboot_agents") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


# Feature 028 · respuesta rápida de endpoint.
#
# Los tres permisos comparten forma pero no se colapsan en una clase
# parametrizada: DRF instancia las clases de `permission_classes` sin argumentos,
# así que una clase por permiso es lo que el framework espera.
#
# Todos verifican además `_has_perm_on_agent`: tener el permiso global no alcanza
# si el rol no llega a ese cliente o sitio.


class SendAlertPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_send_alerts") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class LockAgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_lock_agents") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class SoundAlarmPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_sound_alarm") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class ManageLostModePerms(permissions.BasePermission):
    """Feature 030: marcar un equipo como perdido y recuperarlo.

    A diferencia de los tres de la 028, este permiso cubre además una vista de
    listado que NO lleva `agent_id` en la ruta (el índice de equipos perdidos).
    Por eso la comprobación por agente es condicional: si la vista apunta a un
    equipo concreto se exige también alcance sobre él; si es el listado, basta
    el permiso de rol y el queryset se recorta después con `filter_by_role`.
    Leer `view.kwargs["agent_id"]` a secas reventaría con KeyError en el listado.
    """

    def has_permission(self, r, view) -> bool:
        if not _has_perm(r, "can_manage_lost_mode"):
            return False

        agent_id = view.kwargs.get("agent_id")
        if agent_id is None:
            return True

        return _has_perm_on_agent(r.user, agent_id)


# `ViewLostEvidencePerms` se difiere a la Fase 1 a propósito: hoy no existe
# ninguna vista que sirva evidencia, así que la clase sería código muerto. El
# booleano en `Role` sí se crea ahora, para que la migración de permisos sea una
# sola y no haya que volver a tocar la tabla al empezar a capturar.


class InstallAgentPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_install_agents")


class RunScriptPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_run_scripts") and _has_perm_on_agent(
            r.user, view.kwargs["agent_id"]
        )


class AgentNotesPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        # permissions for GET /agents/notes/ endpoint
        if r.method == "GET":
            # permissions for /agents/<agent_id>/notes endpoint
            if "agent_id" in view.kwargs.keys():
                return _has_perm(r, "can_list_notes") and _has_perm_on_agent(
                    r.user, view.kwargs["agent_id"]
                )
            else:
                return _has_perm(r, "can_list_notes")
        else:
            return _has_perm(r, "can_manage_notes")


class RunBulkPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_run_bulk")


class AgentHistoryPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if "agent_id" in view.kwargs.keys():
            return _has_perm(r, "can_list_agent_history") and _has_perm_on_agent(
                r.user, view.kwargs["agent_id"]
            )

        return _has_perm(r, "can_list_agent_history")


class AgentWOLPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if "agent_id" in view.kwargs.keys():
            return _has_perm(r, "can_send_wol") and _has_perm_on_agent(
                r.user, view.kwargs["agent_id"]
            )

        return _has_perm(r, "can_send_wol")


class AgentRegistryPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if "agent_id" in view.kwargs.keys():
            return _has_perm(r, "can_use_registry") and _has_perm_on_agent(
                r.user, view.kwargs["agent_id"]
            )

        return _has_perm(r, "can_use_registry")
