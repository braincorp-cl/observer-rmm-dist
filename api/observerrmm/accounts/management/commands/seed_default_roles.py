from django.core.management.base import BaseCommand

from accounts.models import Role


class Command(BaseCommand):
    help = (
        "Siembra los roles granulares por defecto del modo perdido/robado y del "
        "bloque Observer Erase (ADR-025 / ADR-029 / feature 042). Idempotente y "
        "no destructivo: crea el rol si falta y nunca pisa un rol que ya existe."
    )

    # Regla de no-pisado, deliberada (mismo criterio que seed_ai_assistant): el
    # despliegue siembra estos roles UNA vez para que una instalación nueva —o una
    # actualización de una instalación previa que aún no los tiene— arranque con la
    # separación de deberes que ADR-025/ADR-029 piden, sin obligar a crearlos a mano
    # por consola. En cuanto el rol existe, es del cliente: puede renombrar sus
    # permisos, asignarle usuarios o borrarlo, y el deploy deja de tocarlo.
    #
    #   rol ausente          -> se crea con el set de permisos canónico
    #   rol ya existe         -> NO SE TOCA (respeta la personalización del cliente)
    #   --force               -> reescribe SOLO los permisos de la superficie gestionada
    #                            (los de abajo), dejando intactos is_superuser y
    #                            cualquier otro permiso que el cliente haya sumado
    #
    # is_superuser va SIEMPRE en False en la creación: son roles granulares; el
    # bypass total es del superusuario, no de estos. El superusuario conserva todos
    # los permisos por _has_perm (user.is_superuser o user.role.is_superuser),
    # independiente de estos roles.

    # Superficie de permisos que este seeder gestiona. Con --force se fijan estos
    # (True los listados por rol, False el resto de la superficie); los permisos
    # FUERA de esta lista nunca se tocan.
    MANAGED_PERMS = [
        "can_list_agents",
        "can_manage_lost_mode",
        "can_view_lost_evidence",
        "can_retrieve_files",
        "can_wipe_device",
        "can_view_erase_certificates",
        "can_manage_asset_intake",
        "can_send_alerts",
        "can_lock_agents",
        "can_sound_alarm",
    ]

    # name -> permisos en True. Todos parten de can_list_agents (llegar a la vista
    # de Equipos perdidos / ver la flota) y nada más: mínimo privilegio.
    ROLE_DEFS = {
        "Operador de Equipos Perdidos": [
            "can_list_agents",
            "can_manage_lost_mode",
            "can_send_alerts",
            "can_lock_agents",
            "can_sound_alarm",
        ],
        "Revisor de Evidencia": [
            "can_list_agents",
            "can_view_lost_evidence",
        ],
        "Recuperador de Archivos": [
            "can_list_agents",
            "can_retrieve_files",
        ],
        "Ordenante de Borrado": [
            "can_list_agents",
            "can_wipe_device",
        ],
        "Auditor de Custodia": [
            "can_list_agents",
            "can_view_erase_certificates",
            "can_manage_asset_intake",
        ],
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Reescribe los permisos gestionados de los roles que ya existen "
                "(no toca is_superuser ni permisos fuera de la superficie)."
            ),
        )

    def handle(self, *args, **options):
        force = options["force"]
        for name, perms in self.ROLE_DEFS.items():
            role, created = Role.objects.get_or_create(name=name)
            if created:
                role.is_superuser = False
                for perm in self.MANAGED_PERMS:
                    setattr(role, perm, perm in perms)
                role.save()
                # Marca legible para que Ansible detecte 'changed' (changed_when).
                self.stdout.write(f"SEEDED role: {name}")
            elif force:
                for perm in self.MANAGED_PERMS:
                    setattr(role, perm, perm in perms)
                role.save()
                self.stdout.write(f"FORCED role: {name}")
            else:
                self.stdout.write(f"SKIP existing role: {name}")
