"""
Carga el set de plantillas de reportes curadas por BrainCorp para Observer RMM.

Autoradas por BrainCorp usando como REFERENCIA los tipos de reporte del
ecosistema RMM (repo público amidaware/reporting-templates) — implementación
propia y original, rebrandeada, SIN importar sus archivos, sin licencia ajena
ni strings legacy ni assets externos. Cubren la totalidad de los tipos de
reporte reales, deduplicando las variantes de formato (csv/md/pdf/html del
mismo reporte: el motor rinde cualquier plantilla en HTML/PDF/plaintext).

Fuera de alcance (a propósito):
  - "All Fields *": volcados de schema para autores de plantillas, no reportes.
  - Antivirus: no hay fuente de datos AV confiable en el modelo.
  - Bitlocker / Custom Fields: dependen de custom fields inexistentes en fresh.
  - Dashboards con gráficos (NOC/Alerts): dependen de plotly/chromium (W005).

Idempotente: re-ejecutar actualiza en su lugar (--overwrite, por defecto True).
Uso:  python manage.py load_curated_reports [--no-overwrite]
"""

from django.core.management.base import BaseCommand

from ee.reporting.utils import _import_base_template, _import_report_template


# ---------------------------------------------------------------------------
# Base HTML compartida (tema "Observation Deck", cian #0E8FA8). PDF-friendly.
# ---------------------------------------------------------------------------
BASE_NAME = "Observer Base v1"
BASE_HTML = """<html>
<head>
<style>
  @page { margin: 0.6in; size: letter landscape; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #243b44; font-size: 11px; }
  .report-header { background: #0E8FA8; color: #fff; padding: 16px 20px; border-radius: 6px;
    display: flex; align-items: center; justify-content: space-between; }
  .report-header h1 { font-size: 20px; margin: 0; }
  .report-header .brand { font-size: 11px; opacity: 0.85; letter-spacing: 0.08em; text-transform: uppercase; }
  .report-meta { text-align: right; font-size: 11px; line-height: 1.5; }
  .report-table { border-collapse: collapse; width: 100%; margin-top: 10px; }
  .report-table th { background: #0E8FA8; color: #fff; text-align: left; padding: 6px 8px;
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.03em; }
  .report-table td { border-bottom: 1px solid #dbe6ea; padding: 5px 8px; vertical-align: top; }
  .report-table tr:nth-child(even) td { background: #f3f9fb; }
  .muted { color: #7a929b; }
  .stale { color: #c0392b; font-weight: bold; }
  .client-title { color: #0b6b7f; border-bottom: 2px solid #0E8FA8; margin: 18px 0 2px; font-size: 15px; }
  .site-title { color: #0E8FA8; margin: 10px 0 2px; font-size: 12px; font-weight: bold; }
  .agent-title { color: #0E8FA8; margin: 14px 0 4px; font-size: 13px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px;
    font-weight: bold; color: #fff; }
  .sev-critical, .sev-important { background: #c0392b; }
  .sev-moderate { background: #e08e0b; }
  .sev-low, .sev-optional, .sev- { background: #5a7d8a; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>"""


def _header(title, extra):
    return (
        "{% block content %}\n"
        "{% set now = datetime.datetime.now(ZoneInfo('America/Santiago')) %}\n"
        '<div class="report-header">\n'
        '  <div><div class="brand">Observer RMM</div><h1>' + title + "</h1></div>\n"
        '  <div class="report-meta">Generado: {{ now.strftime(\'%d-%m-%Y %H:%M\') }}'
        "<br>" + extra + "</div>\n"
        "</div>\n"
    )


END = "\n{% endblock %}\n"


# ===========================================================================
# AGENTES
# ===========================================================================

# 1) Inventario de Agentes
INV_AGENTES = _header("Inventario de Agentes", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Usuario</th>
    <th>Sistema Operativo</th><th>RAM (GB)</th><th>IP p&uacute;blica</th><th>&Uacute;ltima conexi&oacute;n</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='hostname') %}
    <tr>
      <td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.last_logged_in_user or '—' }}</td>
      <td>{{ a.operating_system }}</td><td class="num">{{ a.total_ram or '—' }}</td>
      <td>{{ a.public_ip or '—' }}</td>
      {% if a.last_seen %}<td {% if (now - a.last_seen.astimezone(ZoneInfo('America/Santiago'))).days > 7 %}class="stale"{% endif %}>{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>{% else %}<td class="muted">—</td>{% endif %}
    </tr>
  {% endfor %}
  </tbody>
</table>""" + END
INV_AGENTES_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - last_logged_in_user
    - public_ip
    - total_ram
    - last_seen
    - site__name
    - site__client__name
"""

# 2) Especificaciones de Equipos
SPECS = _header("Especificaciones de Equipos", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Equipo</th><th>Marca / Modelo</th><th>CPU</th>
    <th>Arq.</th><th>RAM (GB)</th><th>N&ordm; Serie</th><th>Sistema Operativo</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='hostname') %}
    <tr>
      <td>{{ a.site__client__name }}</td><td><b>{{ a.hostname }}</b></td>
      <td>{{ a.make_model or '—' }}</td>
      <td>{{ (a.cpu_model | join(', ')) if a.cpu_model else '—' }}</td>
      <td>{{ a.arch or '—' }}</td><td class="num">{{ a.total_ram or '—' }}</td>
      <td>{{ a.serial_number or '—' }}</td><td>{{ a.operating_system }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>""" + END
SPECS_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - total_ram
    - site__name
    - site__client__name
    properties:
    - cpu_model
    - make_model
    - serial_number
    - arch
"""

# 3) Agentes por Cliente y Sitio
AGENTES_CLIENTE_SITIO = _header("Agentes por Cliente y Sitio", "Equipos: {{ data_sources.agents | length }}") + """
{% for client, cagents in data_sources.agents | sort(attribute='site__client__name') | groupby('site__client__name') %}
<div class="client-title">{{ client }} <span class="muted">({{ cagents | length }} equipos)</span></div>
{% for site, sagents in cagents | sort(attribute='site__name') | groupby('site__name') %}
<div class="site-title">{{ site }}</div>
<table class="report-table">
  <thead><tr><th>Equipo</th><th>Sistema Operativo</th><th>Usuario</th><th>&Uacute;ltima conexi&oacute;n</th></tr></thead>
  <tbody>
  {% for a in sagents | sort(attribute='hostname') %}
    <tr><td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      <td>{{ a.last_logged_in_user or '—' }}</td>
      {% if a.last_seen %}<td>{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>{% else %}<td class="muted">—</td>{% endif %}</tr>
  {% endfor %}
  </tbody>
</table>
{% endfor %}
{% endfor %}""" + END
AGENTES_CLIENTE_SITIO_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - last_logged_in_user
    - last_seen
    - site__name
    - site__client__name
"""

# 4) Tiempo de Actividad (Uptime)
UPTIME = _header("Tiempo de Actividad de Equipos", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Sistema Operativo</th><th>Encendido desde</th><th>Tiempo activo</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='hostname') %}
    <tr>
      <td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      {% if a.boot_time %}{% set bt = datetime.datetime.fromtimestamp(a.boot_time, ZoneInfo('America/Santiago')) %}{% set up = now - bt %}
      <td>{{ bt.strftime('%d-%m-%Y %H:%M') }}</td><td class="num">{{ up.days }}d {{ up.seconds // 3600 }}h</td>
      {% else %}<td class="muted">—</td><td class="muted">—</td>{% endif %}
    </tr>
  {% endfor %}
  </tbody>
</table>""" + END
UPTIME_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - boot_time
    - site__name
    - site__client__name
"""

# 5) Agentes con Reinicio Pendiente
PENDING_REBOOT = _header("Equipos con Reinicio Pendiente", "Pendientes: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Sistema Operativo</th><th>&Uacute;ltima conexi&oacute;n</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='hostname') %}
    <tr><td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      {% if a.last_seen %}<td>{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>{% else %}<td class="muted">—</td>{% endif %}</tr>
  {% endfor %}
  </tbody>
</table>
{% if data_sources.agents | length == 0 %}<p class="muted">Ning&uacute;n equipo requiere reinicio.</p>{% endif %}""" + END
PENDING_REBOOT_VARS = """data_sources:
  agents:
    model: agent
    filter:
      needs_reboot: true
    only:
    - hostname
    - operating_system
    - last_seen
    - site__name
    - site__client__name
"""

# 6) Fecha de Instalación del Agente
INSTALL_DATE = _header("Fecha de Instalaci&oacute;n del Agente", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Sistema Operativo</th><th>Instalado</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='created_time') %}
    <tr><td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      {% if a.created_time %}<td>{{ a.created_time.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y') }}</td>{% else %}<td class="muted">—</td>{% endif %}</tr>
  {% endfor %}
  </tbody>
</table>""" + END
INSTALL_DATE_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - created_time
    - site__name
    - site__client__name
"""

# 7) Reporte de Sistemas Operativos (resumen)
OS_REPORT = _header("Distribuci&oacute;n de Sistemas Operativos", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table" style="max-width: 640px;">
  <thead><tr><th>Sistema Operativo</th><th>Cantidad</th></tr></thead>
  <tbody>
  {% for os, group in data_sources.agents | sort(attribute='operating_system') | groupby('operating_system') %}
    <tr><td>{{ os or '(desconocido)' }}</td><td class="num">{{ group | length }}</td></tr>
  {% endfor %}
  </tbody>
</table>""" + END
OS_REPORT_VARS = """data_sources:
  agents:
    model: agent
    only:
    - operating_system
"""

# 8) Reporte Integral de Equipos
INTEGRAL = _header("Reporte Integral de Equipos", "Equipos: {{ data_sources.agents | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Equipo</th><th>Marca / Modelo</th><th>SO</th><th>RAM</th>
    <th>Reinicio pend.</th><th>&Uacute;lt. parche</th><th>&Uacute;ltima conexi&oacute;n</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='site__client__name') %}
    <tr>
      <td>{{ a.site__client__name }}</td><td><b>{{ a.hostname }}</b></td>
      <td>{{ a.make_model or '—' }}</td><td>{{ a.operating_system }}</td>
      <td class="num">{{ a.total_ram or '—' }}</td>
      <td>{% if a.needs_reboot %}<span class="badge sev-important">S&iacute;</span>{% else %}No{% endif %}</td>
      <td>{% if a.patches_last_installed %}{{ a.patches_last_installed.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y') }}{% else %}—{% endif %}</td>
      {% if a.last_seen %}<td {% if (now - a.last_seen.astimezone(ZoneInfo('America/Santiago'))).days > 7 %}class="stale"{% endif %}>{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>{% else %}<td class="muted">—</td>{% endif %}
    </tr>
  {% endfor %}
  </tbody>
</table>""" + END
INTEGRAL_VARS = """data_sources:
  agents:
    model: agent
    only:
    - hostname
    - operating_system
    - total_ram
    - needs_reboot
    - patches_last_installed
    - last_seen
    - site__name
    - site__client__name
    properties:
    - make_model
"""

# ===========================================================================
# SOFTWARE
# ===========================================================================

# 9) Inventario de Software (por equipo)
SOFTWARE = _header("Inventario de Software", "Equipos: {{ data_sources.inv | length }}") + """
{% for row in data_sources.inv | sort(attribute='agent__hostname') %}
<div class="agent-title">{{ row.agent__hostname }} <span class="muted">— {{ row.agent__site__name }} ({{ row.software | length }} programas)</span></div>
<table class="report-table">
  <thead><tr><th>Nombre</th><th>Versi&oacute;n</th><th>Editor</th><th>Fecha instalaci&oacute;n</th></tr></thead>
  <tbody>
  {% for sw in row.software %}
    <tr><td>{{ sw.name }}</td><td>{{ sw.version or '—' }}</td><td>{{ sw.publisher or '—' }}</td><td>{{ sw.install_date or '—' }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endfor %}""" + END
SOFTWARE_VARS = """data_sources:
  inv:
    model: installedsoftware
    only:
    - software
    - agent__hostname
    - agent__site__name
"""

# 10) Software por Cliente
SOFTWARE_CLIENTE = _header("Software por Cliente", "Equipos: {{ data_sources.inv | length }}") + """
{% for client, rows in data_sources.inv | sort(attribute='agent__site__client__name') | groupby('agent__site__client__name') %}
<div class="client-title">{{ client }}</div>
{% for row in rows | sort(attribute='agent__hostname') %}
<div class="agent-title">{{ row.agent__hostname }} <span class="muted">({{ row.software | length }} programas)</span></div>
<table class="report-table">
  <thead><tr><th>Nombre</th><th>Versi&oacute;n</th><th>Editor</th></tr></thead>
  <tbody>
  {% for sw in row.software %}<tr><td>{{ sw.name }}</td><td>{{ sw.version or '—' }}</td><td>{{ sw.publisher or '—' }}</td></tr>{% endfor %}
  </tbody>
</table>
{% endfor %}
{% endfor %}""" + END
SOFTWARE_CLIENTE_VARS = """data_sources:
  inv:
    model: installedsoftware
    only:
    - software
    - agent__hostname
    - agent__site__name
    - agent__site__client__name
"""

# ===========================================================================
# WINDOWS UPDATES
# ===========================================================================

# 11) Actualizaciones de Windows Pendientes (por cliente)
WU_PENDIENTES = _header("Actualizaciones de Windows Pendientes", "Pendientes: {{ data_sources.updates | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>KB</th><th>Severidad</th><th>T&iacute;tulo</th></tr></thead>
  <tbody>
  {% for u in data_sources.updates | sort(attribute='agent__hostname') %}
    <tr><td>{{ u.agent__site__client__name }}</td><td>{{ u.agent__site__name }}</td>
      <td><b>{{ u.agent__hostname }}</b></td><td>{{ u.kb or '—' }}</td>
      <td><span class="badge sev-{{ (u.severity or '')|lower }}">{{ u.severity or 'N/D' }}</span></td>
      <td>{{ u.title }}</td></tr>
  {% endfor %}
  </tbody>
</table>""" + END
WU_PENDIENTES_VARS = """data_sources:
  updates:
    model: winupdate
    filter:
      installed: false
    only:
    - kb
    - title
    - severity
    - agent__hostname
    - agent__site__name
    - agent__site__client__name
"""

# 12) Actualizaciones Pendientes por Sitio
WU_SITIO = _header("Actualizaciones Pendientes por Sitio", "Pendientes: {{ data_sources.updates | length }}") + """
{% for site, rows in data_sources.updates | sort(attribute='agent__site__name') | groupby('agent__site__name') %}
<div class="site-title">{{ site }} <span class="muted">({{ rows | length }} pendientes)</span></div>
<table class="report-table">
  <thead><tr><th>Equipo</th><th>KB</th><th>Severidad</th><th>T&iacute;tulo</th></tr></thead>
  <tbody>
  {% for u in rows | sort(attribute='agent__hostname') %}
    <tr><td>{{ u.agent__hostname }}</td><td>{{ u.kb or '—' }}</td>
      <td><span class="badge sev-{{ (u.severity or '')|lower }}">{{ u.severity or 'N/D' }}</span></td><td>{{ u.title }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endfor %}""" + END
WU_SITIO_VARS = WU_PENDIENTES_VARS

# 13) Últimas Actualizaciones Instaladas
WU_INSTALADAS = _header("&Uacute;ltimas Actualizaciones Instaladas", "Registros: {{ data_sources.updates | length }}") + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Equipo</th><th>KB</th><th>T&iacute;tulo</th><th>Instalada</th></tr></thead>
  <tbody>
  {% for u in data_sources.updates | sort(attribute='date_installed', reverse=True) %}
    <tr><td>{{ u.agent__site__client__name }}</td><td>{{ u.agent__hostname }}</td>
      <td>{{ u.kb or '—' }}</td><td>{{ u.title }}</td>
      <td>{% if u.date_installed %}{{ u.date_installed.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y') }}{% else %}—{% endif %}</td></tr>
  {% endfor %}
  </tbody>
</table>""" + END
WU_INSTALADAS_VARS = """data_sources:
  updates:
    model: winupdate
    filter:
      installed: true
    limit: 1000
    only:
    - kb
    - title
    - date_installed
    - agent__hostname
    - agent__site__client__name
"""

# ===========================================================================
# AUDITORÍA
# ===========================================================================

# 14) Registro de Auditoría
AUDITORIA = _header("Registro de Auditor&iacute;a", "Registros: {{ data_sources.logs | length }}") + """
<table class="report-table">
  <thead><tr><th>Fecha</th><th>Usuario</th><th>Equipo</th><th>Acci&oacute;n</th><th>Objeto</th><th>Mensaje</th></tr></thead>
  <tbody>
  {% for l in data_sources.logs | sort(attribute='entry_time', reverse=True) %}
    <tr>
      <td>{% if l.entry_time %}{{ l.entry_time.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}{% else %}—{% endif %}</td>
      <td>{{ l.username or '—' }}</td><td>{{ l.agent or '—' }}</td>
      <td>{{ l.action or '—' }}</td><td>{{ l.object_type or '—' }}</td><td>{{ l.message or '—' }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>""" + END
AUDITORIA_VARS = """data_sources:
  logs:
    model: auditlog
    limit: 500
    only:
    - entry_time
    - username
    - agent
    - action
    - object_type
    - message
"""


CURATED = [
    {"name": "Inventario de Agentes", "type": "html", "template_md": INV_AGENTES, "template_variables": INV_AGENTES_VARS},
    {"name": "Especificaciones de Equipos", "type": "html", "template_md": SPECS, "template_variables": SPECS_VARS},
    {"name": "Agentes por Cliente y Sitio", "type": "html", "template_md": AGENTES_CLIENTE_SITIO, "template_variables": AGENTES_CLIENTE_SITIO_VARS},
    {"name": "Tiempo de Actividad de Equipos", "type": "html", "template_md": UPTIME, "template_variables": UPTIME_VARS},
    {"name": "Equipos con Reinicio Pendiente", "type": "html", "template_md": PENDING_REBOOT, "template_variables": PENDING_REBOOT_VARS},
    {"name": "Fecha de Instalacion del Agente", "type": "html", "template_md": INSTALL_DATE, "template_variables": INSTALL_DATE_VARS},
    {"name": "Distribucion de Sistemas Operativos", "type": "html", "template_md": OS_REPORT, "template_variables": OS_REPORT_VARS},
    {"name": "Reporte Integral de Equipos", "type": "html", "template_md": INTEGRAL, "template_variables": INTEGRAL_VARS},
    {"name": "Inventario de Software", "type": "html", "template_md": SOFTWARE, "template_variables": SOFTWARE_VARS},
    {"name": "Software por Cliente", "type": "html", "template_md": SOFTWARE_CLIENTE, "template_variables": SOFTWARE_CLIENTE_VARS},
    {"name": "Actualizaciones de Windows Pendientes", "type": "html", "template_md": WU_PENDIENTES, "template_variables": WU_PENDIENTES_VARS},
    {"name": "Actualizaciones Pendientes por Sitio", "type": "html", "template_md": WU_SITIO, "template_variables": WU_SITIO_VARS},
    {"name": "Ultimas Actualizaciones Instaladas", "type": "html", "template_md": WU_INSTALADAS, "template_variables": WU_INSTALADAS_VARS},
    {"name": "Registro de Auditoria", "type": "html", "template_md": AUDITORIA, "template_variables": AUDITORIA_VARS},
]


class Command(BaseCommand):
    help = "Carga las plantillas de reportes curadas por BrainCorp (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-overwrite",
            action="store_true",
            help="No sobrescribir plantillas existentes con el mismo nombre.",
        )

    def handle(self, *args, **options):
        overwrite = not options["no_overwrite"]

        base_id = _import_base_template(
            {"name": BASE_NAME, "html": BASE_HTML}, overwrite
        )
        self.stdout.write(self.style.SUCCESS(f"Base template OK: {BASE_NAME}"))

        for tpl in CURATED:
            data = dict(tpl)
            # template_css NUNCA null: el serializer de Preview lo valida como
            # CharField(allow_blank=True) sin allow_null → null da 400. Los
            # estilos viven en la base "Observer Base v1", así que "" es correcto.
            data.setdefault("template_css", "")
            _import_report_template(data, base_id, overwrite)
            self.stdout.write(self.style.SUCCESS(f"Plantilla OK: {tpl['name']}"))

        self.stdout.write(
            self.style.SUCCESS(f"Listo: {len(CURATED)} plantillas curadas cargadas.")
        )
