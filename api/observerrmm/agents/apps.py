from django.apps import AppConfig


class AgentsConfig(AppConfig):
    name = "agents"

    def ready(self):
        # Conecta la señal post_delete que propaga el borrado del nodo Mesh.
        from agents import signals  # noqa: F401
