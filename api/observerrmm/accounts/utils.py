from functools import lru_cache
from typing import TYPE_CHECKING, Tuple

from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest

    from accounts.models import Role, User


def is_root_user(*, request: "HttpRequest", user: "User") -> bool:
    root = (
        hasattr(settings, "ROOT_USER")
        and request.user != user
        and user.username == settings.ROOT_USER
    )
    demo = (
        getattr(settings, "DEMO", False) and request.user.username == settings.ROOT_USER
    )
    return root or demo


def is_superuser(user: "User") -> bool:
    return user.role and getattr(user.role, "is_superuser")


def _role_perm_fields() -> "Tuple[str, ...]":
    # Feature 052: los nombres de todos los permisos booleanos de Role, por
    # introspección del modelo.
    #
    # Deliberadamente NO se usa `role_catalog.MANAGED_PERMS`: esa lista cubre los
    # permisos que el catálogo reparte, y un rol hecho a medida por un cliente
    # puede encender cualquier otro. Peor aún, un permiso agregado al modelo en
    # el futuro quedaría fuera del invariante de no-elevación sin que nadie lo
    # note, que es exactamente la clase de hueco que esta feature viene a cerrar.
    #
    # `is_superuser` queda fuera porque no es un permiso sino el interruptor que
    # los ignora a todos; se compara por separado y antes que el resto.
    from django.db.models import BooleanField

    from accounts.models import Role

    return tuple(
        f.name
        for f in Role._meta.get_fields()
        if isinstance(f, BooleanField) and f.name != "is_superuser"
    )


@lru_cache(maxsize=1)
def role_perm_fields() -> "Tuple[str, ...]":
    # Se calcula una sola vez: el modelo no cambia en caliente.
    return _role_perm_fields()


def can_assign_role(actor: "User", target_role: "Role") -> "Tuple[bool, str]":
    """Feature 052 — ¿puede `actor` otorgar `target_role` a alguien?

    Devuelve `(permitido, motivo)`. El motivo viaja al 403 y al registro de
    auditoría, para que ambos digan lo mismo.

    Dos barreras, en este orden:

    1. El invariante de no-elevación (RN-02): nunca un perfil con permisos que
       el actor no tenga, ni uno de superusuario. Es DURO: la lista de
       asignables solo puede restringir por debajo de él, jamás ampliarlo.
    2. La lista de asignables (RN-01): de lo que el invariante permite, solo lo
       que el perfil del actor declara. Lista vacía = nada.

    El invariante va primero a propósito: una lista mal configurada debe seguir
    siendo segura.
    """
    if _actor_es_superusuario(actor):
        return True, ""

    role = actor.role
    if not role:
        return False, "No tienes un perfil asignado, así que no puedes otorgar ninguno."

    if target_role.is_superuser:
        return (
            False,
            f"No puedes asignar el perfil «{target_role.name}»: "
            "es un perfil de superusuario.",
        )

    faltantes = [
        perm
        for perm in role_perm_fields()
        if getattr(target_role, perm, False) and not getattr(role, perm, False)
    ]
    if faltantes:
        return (
            False,
            f"No puedes asignar el perfil «{target_role.name}»: "
            "incluye permisos que tu propio perfil no tiene.",
        )

    # La pertenencia se resuelve EN MEMORIA sobre .all(), no con
    # .filter(pk=...).exists(). Un `filter()` sobre el related manager ignora el
    # prefetch de `get_and_set_role_cache()` y consulta la base en cada llamada,
    # que es justo lo que el requisito de desempeño prohíbe. Con `.all()` sobre un
    # rol cacheado la lista ya viene resuelta y esto no toca la base.
    #
    # Importa doblemente desde que `GetAddRoles.get` llama a esta función una vez
    # por rol para filtrar el listado: con `filter().exists()` eso sería N
    # consultas por cada apertura del selector.
    if target_role.pk not in {r.pk for r in role.assignable_roles.all()}:
        return (
            False,
            f"No puedes asignar el perfil «{target_role.name}»: "
            "no está entre los que tu perfil puede otorgar.",
        )

    return True, ""


def can_manage_user(actor: "User", target_user: "User") -> "Tuple[bool, str]":
    """Feature 052 — ¿puede `actor` escribir sobre la cuenta `target_user`?

    Cubre editar, deshabilitar, eliminar y resetear contraseña o MFA de otra
    persona. No decide sobre el ROL que se le pone: eso es `can_assign_role`.

    Devuelve `(permitido, motivo)`.
    """
    if _actor_es_superusuario(actor):
        return True, ""

    # La propia cuenta siempre: los datos propios y el auto-servicio de
    # contraseña y MFA (issue #686) se conservan. Cambiar el PROPIO rol lo corta
    # RN-03 en la vista, que es el único lugar donde se ve si el payload lo trae.
    if actor.pk == target_user.pk:
        return True, ""

    # RN-04: las cuentas de superusuario son intocables para quien no lo es.
    # Generaliza a toda la clase el trato que `is_root_user` da al usuario raíz.
    if target_user.is_superuser or is_superuser(target_user):
        return (
            False,
            f"No puedes administrar la cuenta «{target_user.username}»: "
            "es una cuenta de superusuario.",
        )

    role = actor.role
    if not role:
        return False, "No tienes un perfil asignado."

    # RN-09: fuera del alcance. La cuenta es VISIBLE en el listado —para
    # conservar la trazabilidad y evitar colisiones de nombre— pero no editable.
    if (
        not target_user.role
        or not role.assignable_roles.filter(pk=target_user.role.pk).exists()
    ):
        nombre = target_user.role.name if target_user.role else "sin perfil"
        return (
            False,
            f"No puedes administrar la cuenta «{target_user.username}»: "
            f"su perfil («{nombre}») no está entre los que tu perfil puede otorgar.",
        )

    return True, ""


def _actor_es_superusuario(actor: "User") -> bool:
    # Mismo cortocircuito que `_has_perm`: el superusuario queda exento de las
    # reglas de delegación, porque si no sería imposible configurarlas.
    return bool(actor.is_superuser or is_superuser(actor))
