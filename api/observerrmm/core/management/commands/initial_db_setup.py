from contextlib import suppress

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.models import CoreSettings
from observerrmm.constants import ALL_TIMEZONES


class Command(BaseCommand):
    help = "Populates the global site settings on first install"

    def add_arguments(self, parser):
        # Zona horaria por defecto de la consola. Solo se aplica cuando este comando
        # CREA la fila (primera instalación): en una re-ejecución no pisa lo que el
        # cliente haya cambiado después en Ajustes. Sin el flag rige el default del modelo.
        parser.add_argument("--time-zone", dest="time_zone", default="")

    def handle(self, *args, **kwargs):
        time_zone = kwargs.get("time_zone") or ""
        if time_zone and time_zone not in ALL_TIMEZONES:
            raise CommandError(f"Zona horaria desconocida: {time_zone}")

        # can only be 1 instance of this. Prevents error when rebuilding docker container
        with suppress(ValidationError):
            core = CoreSettings()
            if time_zone:
                core.default_time_zone = time_zone
            core.save()
            self.stdout.write("Core db populated")
