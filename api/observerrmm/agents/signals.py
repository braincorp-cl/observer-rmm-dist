from django.db.models.signals import post_delete
from django.dispatch import receiver

from agents.models import Agent


@receiver(post_delete, sender=Agent)
def remove_mesh_node_on_agent_delete(sender, instance, **kwargs):
    """Al borrarse un Agent, propaga el borrado de su nodo en MeshCentral.

    post_delete se emite por cada instancia en TODA ruta de borrado (UI/API,
    admin de Django, queryset .delete() y el command bulk_delete_agents), así
    que el nodo Mesh nunca queda huérfano. El borrado real corre en una tarea
    Celery (throttled) para no bloquear el request ni saturar el puerto 4430.
    """
    # Import diferido: evita cargar Celery al importar el modelo.
    from agents.tasks import remove_mesh_node_task

    mesh_node_id = getattr(instance, "mesh_node_id", None)
    if mesh_node_id:
        remove_mesh_node_task.delay(mesh_node_id)
