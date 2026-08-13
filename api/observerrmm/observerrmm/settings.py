import os
import sys
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

from observerrmm.util_settings import get_backend_url, get_root_domain, get_webdomain

BASE_DIR = Path(__file__).resolve().parent.parent

# Biblioteca de scripts del producto. Vive DENTRO del árbol desplegado
# (api/observerrmm/scripts/library/), no en un repo externo clonado: un clone del
# dist ya la trae y el deploy solo tiene que cargarla en la BD. Antes apuntaba a
# /opt/observer-community-scripts, que Ansible llenaba clonando un repo ajeno.
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts", "library")

DOCKER_BUILD = False

LOG_DIR = os.path.join(BASE_DIR, "observerrmm/private/log")

EXE_DIR = os.path.join(BASE_DIR, "observerrmm/private/exe")

LINUX_AGENT_SCRIPT = BASE_DIR / "core" / "agent_linux.sh"
MACOS_AGENT_SCRIPT = BASE_DIR / "core" / "agent_macos.sh"

MAC_UNINSTALL = BASE_DIR / "core" / "mac_uninstall.sh"

# Evidencia del modo perdido/robado (feature 030, ADR-025). Ruta propia, fuera de
# la de los assets de reporting: distinto régimen de retención y de acceso. Se
# puede pisar desde local_settings.py para montarla en otro volumen.
LOST_MODE_EVIDENCE_BASE_PATH = "/opt/observer/lostmode/evidence"

# Llave Fernet del cifrado en reposo de esa evidencia (030 · T020, ADR-025 punto
# 5). Vacía = sin cifrar. NO se versiona ni se pone a mano acá: la genera
# install.yml por ambiente (patrón autovault) y la renderiza en
# local_settings.py, que se RE-RENDERIZA en cada deploy — una llave parchada a
# mano en el servidor se perdería en silencio y, peor, dejaría la evidencia ya
# cifrada ilegible. Ver agents/lostmode_crypto.py.
LOST_MODE_EVIDENCE_KEY = ""

AUTH_USER_MODEL = "accounts.User"

# latest release
ORMM_VERSION = "1.4.9"

WEB_VERSION = "0.2.1"

# bump this version everytime vue code is changed
# to alert user they need to manually refresh their browser
APP_VER = "0.1.2"

# https://github.com/braincorp-cl/observer-agent-dist/releases
LATEST_AGENT_VER = "2.15.15"

MESH_VER = "1.1.32"

NATS_SERVER_VER = "2.14.0"

# Install Nushell on the agent
# https://github.com/nushell/nushell
INSTALL_NUSHELL = True
# GitHub version to download. The file will be downloaded from GitHub, extracted and installed.
# Version to download. If INSTALL_NUSHELL_URL is not provided, the file will be downloaded from GitHub,
# extracted and installed.
INSTALL_NUSHELL_VERSION = "0.112.2"
# URL to download directly. This is expected to be the direct URL, unauthenticated, uncompressed, ready to be installed.
# Use {OS}, {ARCH} and {VERSION} to specify the GOOS, GOARCH and INSTALL_NUSHELL_VERSION respectively.
# Windows: The ".exe" extension will be added automatically.
# Examples:
#   https://examplle.com/download/nushell/{OS}/{ARCH}/{VERSION}/nu
#   https://examplle.com/download/nushell/nu-{VERSION}-{OS}-{ARCH}
INSTALL_NUSHELL_URL = ""
# Enable Nushell config on the agent
# The default is to not enable the config because it could change how scripts run.
# However, disabling the config prevents plugins from being registered.
# https://github.com/nushell/nushell/issues/10754
# False: --no-config-file option is added to the command line.
# True: --config and --env-config options are added to the command line and point to the Agent's directory.
NUSHELL_ENABLE_CONFIG = False

# Install Deno on the agent
# https://github.com/denoland/deno
INSTALL_DENO = True
# Version to download. If INSTALL_DENO_URL is not provided, the file will be downloaded from GitHub,
# extracted and installed.
INSTALL_DENO_VERSION = "v1.46.3"
# URL to download directly. This is expected to be the direct URL, unauthenticated, uncompressed, ready to be installed.
# Use {OS}, {ARCH} and {VERSION} to specify the GOOS, GOARCH and INSTALL_DENO_VERSION respectively.
# Windows: The ".exe" extension will be added automatically.
# Examples:
#   https://examplle.com/download/deno/{OS}/{ARCH}/{VERSION}/deno
#   https://examplle.com/download/deno/deno-{VERSION}-{OS}-{ARCH}
INSTALL_DENO_URL = ""
# Default permissions for Deno
# Space separated list of permissions as listed in the documentation.
# https://docs.deno.com/runtime/manual/basics/permissions#permissions
# Examples:
#   DENO_DEFAULT_PERMISSIONS = "--allow-sys --allow-net --allow-env"
#   DENO_DEFAULT_PERMISSIONS = "--allow-all"
DENO_DEFAULT_PERMISSIONS = "--allow-all"

# for the update script, bump when need to recreate venv
PIP_VER = "48"

SETUPTOOLS_VER = "80.9.0"
WHEEL_VER = "0.45.1"

AGENT_BASE_URL = "https://agents.observer.cl"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

ASGI_APPLICATION = "observerrmm.asgi.application"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False  # disabled for performance, enable when we add translation support
USE_TZ = True

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "observerrmm/static/")]

REST_KNOX = {
    "TOKEN_TTL": timedelta(hours=5),
    "AUTO_REFRESH": True,
    "MIN_REFRESH_INTERVAL": 600,
}

DEMO = False
DEBUG = False
ADMIN_ENABLED = False
HOSTED = False
SWAGGER_ENABLED = False
REDIS_HOST = "127.0.0.1"

# Agent check-in intervals (seconds), random (min, max) per agent → built-in jitter.
# GAP-052: los valores inflados previos (disks ~2.8 días, wmi hasta 70 h) dejaban a un
# agente recién enrolado sin inventario por horas/días. Recalibrados a los defaults
# upstream del agente (responsivos para flotas normales). El ÚNICO con riesgo real de
# OOM en MeshCentral es CHECKIN_SYNCMESH → se mantiene >= 3600 (lección MINSAL).
# Para flotas muy grandes (~28k agentes) subir wmi/disks/agentinfo vía local_settings.py
# (el rol Ansible los parametriza todos).
CHECKIN_HELLO = (30, 60)
CHECKIN_AGENTINFO = (200, 400)
CHECKIN_WINSVC = (2400, 3000)
CHECKIN_PUBIP = (300, 500)
CHECKIN_DISKS = (1000, 2000)
CHECKIN_SW = (2800, 3500)
CHECKIN_WMI = (3000, 4000)
CHECKIN_SYNCMESH = (3600, 7200)
# Feature 023: captura de geolocalización de baja frecuencia (~25-35 min). Solo se
# usa cuando el interruptor global CoreSettings.geo_tracking_enabled está activo; el
# agente también captura al detectar cambio de red, así que este intervalo es un piso
# conservador, no la única fuente de puntos. Subir vía local_settings.py si se quiere.
CHECKIN_GEO = (1500, 2100)
# Feature 023 · F4: resolución WiFi→coordenadas (modelo Prey, key server-side).
# El endpoint /api/v3/geolocate/ reenvía las antenas WiFi que reporta el agente a
# Google Geolocation API usando esta key, que vive SOLO en el backend (nunca en la
# flota). Vacía = resolución WiFi apagada → el agente degrada a IP. Setear la key
# real vía local_settings.py o la env var GOOGLE_GEOLOCATION_API_KEY; NO versionar
# la key en git. Precio Google: 10.000 consultas/mes gratis, luego US$5/1.000.
GOOGLE_GEOLOCATION_API_KEY = os.getenv("GOOGLE_GEOLOCATION_API_KEY", "")
GOOGLE_GEOLOCATION_URL = "https://www.googleapis.com/geolocation/v1/geolocate"
# Caché del resolver (Redis): el mismo conjunto de antenas se resuelve UNA vez y
# sirve a toda la flota que las ve (una oficina con N máquinas = 1 consulta a
# Google). Protege la cuota/costo. TTL del fix y TTL negativo (antenas que Google
# no ubica) separados; el negativo es corto por si es transitorio.
GOOGLE_GEOLOCATION_CACHE_TTL = int(os.getenv("GOOGLE_GEOLOCATION_CACHE_TTL", "3600"))
GOOGLE_GEOLOCATION_CACHE_MISS_TTL = int(
    os.getenv("GOOGLE_GEOLOCATION_CACHE_MISS_TTL", "600")
)
CHECK_INTERVAL_JITTER = (3, 120)

# Desinstalación manual del agente (endpoint /api/v3/uninstalled/).
#
# La alerta sale de inmediato; el borrado del agente se difiere estos minutos y
# se CANCELA si el mismo agent_id vuelve a dar señales dentro de la ventana. Eso
# es lo que separa una desinstalación de una REINSTALACIÓN: reinstalar sobre un
# equipo existente corre el mismo `uninstall`, y sin la ventana el registro se
# perdería por el camino.
#
# En 0 el borrado corre de inmediato (sin ventana). Overridable en
# local_settings.py.
MANUAL_UNINSTALL_GRACE_MINUTES = 10
# Puesto en False, el aviso sólo genera la alerta y el registro de auditoría, y
# el agente queda en la consola para que alguien lo borre a mano. La alerta y la
# auditoría NO dependen de esta bandera: se escriben siempre.
MANUAL_UNINSTALL_AUTO_DELETE = True
NATS_MAX_CONNECTIONS = 50000
ORMM_LOG_LEVEL = "ERROR"
ORMM_LOG_TO = "file"
ORMM_PROTO = "https"
ORMM_BACKEND_PORT = None
# Rate limiting de los endpoints de login (configurable por env; defaults propios)
ORMM_CHECK_CREDS_MIN_THROTTLE = int(os.getenv("ORMM_CHECK_CREDS_MIN_THROTTLE", 50))
ORMM_CHECK_CREDS_DAY_THROTTLE = int(os.getenv("ORMM_CHECK_CREDS_DAY_THROTTLE", 1000))
ORMM_LOGIN_MIN_THROTTLE = int(os.getenv("ORMM_LOGIN_MIN_THROTTLE", 50))
ORMM_LOGIN_DAY_THROTTLE = int(os.getenv("ORMM_LOGIN_DAY_THROTTLE", 1000))

if not DOCKER_BUILD:
    ALLOWED_HOSTS = []
    CORS_ORIGIN_WHITELIST = []

with suppress(ImportError):
    from ee.sso.sso_settings import *  # noqa

with suppress(ImportError):
    from .local_settings import *  # noqa

if "GHACTIONS" in os.environ:
    print("-----------------------GHACTIONS----------------------------")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "pipeline",
            "USER": "pipeline",
            "PASSWORD": "pipeline123456",
            "HOST": "127.0.0.1",
            "PORT": "",
        }
    }
    SECRET_KEY = "abcdefghijklmnoptravis123456789"
    ALLOWED_HOSTS = ["api.example.com"]
    ADMIN_URL = "abc123456/"
    CORS_ORIGIN_WHITELIST = ["https://rmm.example.com"]
    MESH_USERNAME = "pipeline"
    MESH_SITE = "https://example.com"
    MESH_TOKEN_KEY = "bd65e957a1e70c622d32523f61508400d6cd0937001a7ac12042227eba0b9ed625233851a316d4f489f02994145f74537a331415d00047dbbf13d940f556806dffe7a8ce1de216dc49edbad0c1a7399c"
    REDIS_HOST = "localhost"

if not DOCKER_BUILD:

    ORMM_ROOT_DOMAIN = get_root_domain(ALLOWED_HOSTS[0])
    frontend_domain = get_webdomain(CORS_ORIGIN_WHITELIST[0]).split(":")[0]

    ALLOWED_HOSTS.append(frontend_domain)

    if DEBUG:
        ALLOWED_HOSTS.append("*")

    backend_url = get_backend_url(ALLOWED_HOSTS[0], ORMM_PROTO, ORMM_BACKEND_PORT)

    SESSION_COOKIE_DOMAIN = ORMM_ROOT_DOMAIN
    CSRF_COOKIE_DOMAIN = ORMM_ROOT_DOMAIN
    CSRF_TRUSTED_ORIGINS = [CORS_ORIGIN_WHITELIST[0], backend_url]
    HEADLESS_FRONTEND_URLS = {
        "socialaccount_login_error": f"{CORS_ORIGIN_WHITELIST[0]}/account/provider/callback"
    }

CHECK_TOKEN_URL = f"{AGENT_BASE_URL}/api/v2/checktoken"
AGENTS_URL = f"{AGENT_BASE_URL}/api/v2/agents/?"
EXE_GEN_URL = f"{AGENT_BASE_URL}/api/v2/exe"
WEBTAR_DL_URL = f"{AGENT_BASE_URL}/api/v2/webtar/?"

if "GHACTIONS" in os.environ:
    DEBUG = False
    ADMIN_ENABLED = False
    DEMO = False

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "knox.auth.TokenAuthentication",
        "observerrmm.auth.APIAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "check_creds_min": f"{ORMM_CHECK_CREDS_MIN_THROTTLE}/minute",
        "login_min": f"{ORMM_LOGIN_MIN_THROTTLE}/minute",
        "check_creds_day": f"{ORMM_CHECK_CREDS_DAY_THROTTLE}/day",
        "login_day": f"{ORMM_LOGIN_DAY_THROTTLE}/day",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Observer RMM API",
    "DESCRIPTION": "Simple and Fast remote monitoring and management tool",
    "VERSION": ORMM_VERSION,
    "AUTHENTICATION_WHITELIST": ["observerrmm.auth.APIAuthentication"],
}


if not DEBUG:
    REST_FRAMEWORK.update(
        {"DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",)}
    )

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "rest_framework.authtoken",
    "knox",
    "corsheaders",
    "accounts",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.headless",
    "apiv3",
    "apiv4",
    "clients",
    "agents",
    "checks",
    "services",
    "winupdate",
    "software",
    "core",
    "automation",
    "autotasks",
    "logs",
    "scripts",
    "alerts",
    "ee.sso",
]

if not DEMO:
    INSTALLED_APPS += ("ee.reporting",)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, 6379)],
        },
    },
}


# silence cache key length warnings
import warnings  # noqa

from django.core.cache import CacheKeyWarning  # noqa

warnings.simplefilter("ignore", CacheKeyWarning)

CACHES = {
    "default": {
        "BACKEND": "observerrmm.cache.ObserverRedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379",
        "OPTIONS": {
            "parser_class": "redis.connection._HiredisParser",
            "pool_class": "redis.BlockingConnectionPool",
            "db": "10",
        },
    }
}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "observerrmm.middleware.LogIPMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "observerrmm.middleware.AuditMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "ee.sso.middleware.SSOIconMiddleware",
]

if SWAGGER_ENABLED:
    INSTALLED_APPS += ("drf_spectacular",)

if DEBUG and not DEMO:
    INSTALLED_APPS.insert(0, "daphne")
    INSTALLED_APPS += (
        "django_extensions",
        "silk",
    )

    MIDDLEWARE.insert(0, "silk.middleware.SilkyMiddleware")

if ADMIN_ENABLED:
    MIDDLEWARE += ("django.contrib.messages.middleware.MessageMiddleware",)
    INSTALLED_APPS += (
        "django.contrib.admin",
        "django.contrib.messages",
    )

if DEMO:
    MIDDLEWARE += ("observerrmm.middleware.DemoMiddleware",)


ROOT_URLCONF = "observerrmm.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "observerrmm.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


def get_log_level() -> str:
    if "ORMM_LOG_LEVEL" in os.environ:
        return os.getenv("ORMM_LOG_LEVEL")  # type: ignore

    return ORMM_LOG_LEVEL


def configure_logging_handler():
    cfg = {
        "level": get_log_level(),
        "formatter": "verbose",
    }

    log_to = os.getenv("ORMM_LOG_TO", ORMM_LOG_TO)

    if log_to == "stdout":
        cfg["class"] = "logging.StreamHandler"
        cfg["stream"] = sys.stdout
    else:
        cfg["class"] = "logging.FileHandler"
        cfg["filename"] = os.path.join(LOG_DIR, "ormm_debug.log")

    return cfg


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
    },
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "django_debug.log"),
            "formatter": "verbose",
        },
        "ormm": configure_logging_handler(),
    },
    "loggers": {
        "django.request": {"handlers": ["file"], "level": "ERROR", "propagate": True},
        "ormm": {"handlers": ["ormm"], "level": get_log_level(), "propagate": False},
    },
}
