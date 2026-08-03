import asyncio
import time

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from agents.models import Agent


class Command(BaseCommand):
    help = "Envía comando WMI a agentes activos sin hardware detail (serial BIOS vacío o nulo)"

    def handle(self, *args, **kwargs):
        sin_serial = Agent.objects.filter(
            Q(wmi_detail__isnull=True)
            | Q(wmi_detail={})
            | Q(wmi_detail__bios__0__0__SerialNumber__isnull=True)
            | Q(wmi_detail__bios__0__0__SerialNumber="")
        )

        total = sin_serial.count()
        self.stdout.write(self.style.WARNING(f"Agentes sin serial/wmi_detail: {total}"))

        ahora = timezone.now()
        enviados = 0

        for a in sin_serial:
            umbral = timedelta(minutes=a.offline_time) + timedelta(seconds=30)
            if a.last_seen and (ahora - a.last_seen) < umbral:
                asyncio.run(a.nats_cmd({"func": "wmi"}, wait=False))
                self.stdout.write(f"  → WMI enviado: {a.hostname}")
                enviados += 1
                time.sleep(0.5)

        self.stdout.write(
            self.style.SUCCESS(f"Completado: {enviados}/{total} agentes notificados")
        )
