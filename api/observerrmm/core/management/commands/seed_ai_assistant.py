from django.core.management.base import BaseCommand

from core.models import CoreSettings


class Command(BaseCommand):
    help = (
        "Siembra la configuración por defecto del Asistente IA (proveedor "
        "OpenAI-compatible) sin pisar nunca la credencial propia del cliente."
    )

    # Regla de no-pisado, deliberada: el despliegue trae una key de cortesía para
    # que el cliente pueda PROBAR la generación de borradores. En cuanto el cliente
    # pone la suya, el deploy deja de tocar el bloque entero. El discriminante es el
    # token: si el que hay en base NO es el que trae este deploy, es del cliente.
    #
    #   token vacío                -> siembra todo (instalación nueva / primer deploy)
    #   token == el de este deploy -> refresca los demás campos (permite mover el
    #                                 modelo por defecto en un release futuro)
    #   token distinto             -> NO TOCA NADA y lo dice
    #
    # Con --force se puede forzar la escritura (rotación de la key de cortesía).

    def add_arguments(self, parser):
        parser.add_argument("--token", required=True)
        parser.add_argument("--base-url", required=True)
        parser.add_argument("--model", required=True)
        parser.add_argument("--max-tokens", type=int, default=4000)
        # Vacío = NO se manda el campo al proveedor. Es el valor correcto por
        # defecto: hay modelos compatibles que rechazan la petición entera con
        # HTTP 400 si reciben una temperatura distinta de la suya (kimi-k3).
        parser.add_argument("--temperature", default="")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **opts):
        core = CoreSettings.objects.first()
        if core is None:
            self.stdout.write("AI assistant seed skipped: no CoreSettings row yet")
            return

        actual = (core.open_ai_token or "").strip()
        nuevo = opts["token"].strip()

        if actual and actual != nuevo and not opts["force"]:
            self.stdout.write(
                "AI assistant seed skipped: the API key was replaced by the customer"
            )
            return

        temp_raw = str(opts["temperature"]).strip()
        temperatura = float(temp_raw) if temp_raw else None

        core.open_ai_token = nuevo
        core.open_ai_base_url = opts["base_url"].strip()
        core.open_ai_model = opts["model"].strip()
        core.open_ai_max_tokens = opts["max_tokens"]
        core.open_ai_temperature = temperatura
        core.save(
            update_fields=[
                "open_ai_token",
                "open_ai_base_url",
                "open_ai_model",
                "open_ai_max_tokens",
                "open_ai_temperature",
            ]
        )
        self.stdout.write(f"AI assistant seeded: {core.open_ai_model}")
