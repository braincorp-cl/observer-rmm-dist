"""Permisos del módulo Observer Erase (feature 039, ADR-029).

`WipeDevicePerms` es la llave del borrado destructivo: off por omisión, separado
de `can_manage_lost_mode`. Sigue el molde de `ManageLostModePerms` — exige alcance
sobre el equipo sólo cuando la vista apunta a uno concreto; el listado se recorta
después con `filter_by_role`.
"""

from rest_framework import permissions

from observerrmm.permissions import _has_perm, _has_perm_on_agent


class WipeDevicePerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if not _has_perm(r, "can_wipe_device"):
            return False

        agent_id = view.kwargs.get("agent_id")
        if agent_id is None:
            return True

        return _has_perm_on_agent(r.user, agent_id)


class ViewEraseCertificatesPerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        if not _has_perm(r, "can_view_erase_certificates"):
            return False

        agent_id = view.kwargs.get("agent_id")
        if agent_id is None:
            return True

        return _has_perm_on_agent(r.user, agent_id)


class ManageAssetIntakePerms(permissions.BasePermission):
    def has_permission(self, r, view) -> bool:
        return _has_perm(r, "can_manage_asset_intake")
