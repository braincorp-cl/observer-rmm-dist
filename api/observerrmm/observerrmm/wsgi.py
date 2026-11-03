"""
WSGI config for observerrmm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "observerrmm.settings")

application = get_wsgi_application()

# Resolver el arbol de URLs aqui carga las vistas una sola vez en el proceso
# maestro; los workers lo heredan por fork() en vez de importarlo cada uno en
# su primera peticion.
from django.urls import get_resolver  # noqa: E402

get_resolver().url_patterns
