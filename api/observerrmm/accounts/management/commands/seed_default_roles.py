from django.core.management.base import BaseCommand

from accounts.models import Role
from accounts.role_catalog import MANAGED_PERMS, STANDARD_ROLES


class Command(BaseCommand):
    help = (
        "Siembra el catálogo de perfiles estándar de Observer RMM (gobierno, "
        "operación, especialistas y custodia). Idempotente y no destructivo: crea "
        "el rol si falta y nunca pisa un rol que ya existe."
    )

    # Regla de no-pisado, deliberada (mismo criterio que seed_ai_assistant): el
    # despliegue siembra estos roles UNA vez para que una instalación nueva —o una
    # actualización de una instalación previa que aún no los tiene— arranque con una
    # taxonomía formal y con la separación de deberes que ADR-025/ADR-029 piden, sin
    # obligar a crearlos a mano por consola. En cuanto el rol existe, es del cliente:
    # puede cambiarle los permisos, asignarle usuarios o borrarlo, y el deploy deja
    # de tocarlo.
    #
    #   rol ausente           -> se crea con el set de permisos canónico
    #   rol ya existe         -> NO SE TOCA (respeta la personalización del cliente)
    #   --force               -> realinea los permisos del rol con el catálogo: los
    #                            de su lista en True y el resto de la superficie
    #                            gestionada en False. `is_superuser` nunca se toca.
    #   --only "<nombre>"     -> acota la corrida (y el --force) a un solo rol
    #   --dry-run             -> informa qué haría, sin escribir nada
    #
    # is_superuser va SIEMPRE en False en la creación: son roles granulares; el
    # bypass total es del superusuario, no de estos. El superusuario conserva todos
    # los permisos por _has_perm (user.is_superuser o user.role.is_superuser),
    # independiente de estos roles.
    #
    # El catálogo (nombres, familias, descripciones y permisos) vive en
    # accounts/role_catalog.py, que es también la fuente de la documentación
    # publicada en docs.observer.cl/administracion/roles/.

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Realinea con el catálogo los permisos de los roles que ya existen "
                "(no toca is_superuser)."
            ),
        )
        parser.add_argument(
            "--only",
            metavar="NOMBRE",
            help="Procesa solo el rol indicado, por su nombre exacto.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Informa qué haría sin escribir en la base de datos.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        only = options["only"]

        definitions = STANDARD_ROLES
        if only:
            definitions = [r for r in STANDARD_ROLES if r["name"] == only]
            if not definitions:
                names = ", ".join(sorted(r["name"] for r in STANDARD_ROLES))
                self.stderr.write(f"No existe en el catálogo el rol '{only}'. Hay: {names}")
                return

        for definition in definitions:
            name = definition["name"]
            perms = definition["perms"]
            role = Role.objects.filter(name=name).first()

            if role is None:
                if dry_run:
                    self.stdout.write(f"WOULD SEED role: {name}")
                    continue
                role = Role(name=name, is_superuser=False)
                self._apply(role, perms)
                role.save()
                # Marca legible para que Ansible detecte 'changed' (changed_when).
                self.stdout.write(f"SEEDED role: {name}")
            elif force:
                drift = self._drift(role, perms)
                if not drift:
                    self.stdout.write(f"ALIGNED role: {name}")
                    continue
                if dry_run:
                    self.stdout.write(f"WOULD FORCE role: {name} ({', '.join(drift)})")
                    continue
                self._apply(role, perms)
                role.save()
                self.stdout.write(f"FORCED role: {name} ({', '.join(drift)})")
            else:
                self.stdout.write(f"SKIP existing role: {name}")

    @staticmethod
    def _apply(role, perms):
        for perm in MANAGED_PERMS:
            setattr(role, perm, perm in perms)

    @staticmethod
    def _drift(role, perms):
        """Permisos de la superficie gestionada que no coinciden con el catálogo."""
        out = []
        for perm in MANAGED_PERMS:
            expected = perm in perms
            if getattr(role, perm) != expected:
                out.append(f"{'+' if expected else '-'}{perm}")
        return out
