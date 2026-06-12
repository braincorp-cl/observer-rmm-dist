from django.core.management.base import BaseCommand

from observerrmm.utils import get_celery_queue_len


class Command(BaseCommand):
    help = "Get the celery queue length"

    def handle(self, *args, **kwargs):
        ret = get_celery_queue_len()
        self.stdout.write(str(ret))
