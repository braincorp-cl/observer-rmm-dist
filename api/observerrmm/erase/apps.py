from django.apps import AppConfig


class EraseConfig(AppConfig):
    # Módulo Observer Erase — Bloques C (certificación) y D (custodia) del RF
    # v1.0. El Bloque A (comandos destructivos del agente) vive en el agente y
    # entra detrás del gate de ADR-029; acá solo está el gobierno de la orden.
    name = "erase"
    verbose_name = "Observer Erase"
