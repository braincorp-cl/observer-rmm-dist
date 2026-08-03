"""
Carga el set de plantillas de reportes curadas por BrainCorp para Observer RMM.

Autoradas por BrainCorp usando como REFERENCIA los tipos de reporte del
ecosistema RMM (un repo público de plantillas de terceros) — implementación
propia y original, rebrandeada, SIN importar sus archivos, sin licencia ajena
ni strings legacy ni assets externos. Cubren la totalidad de los tipos de
reporte reales, deduplicando las variantes de formato (csv/md/pdf/html del
mismo reporte: el motor rinde cualquier plantilla en HTML/PDF/plaintext).

Incluye dashboards con gráficos (NOC/Alertas, chequeos, flota, parches) que
rinden plotly vía Kaleido→SVG (W005): el SVG rinde idéntico en Preview, HTML
export y PDF (WeasyPrint no ejecuta JS) y pesa ~6KB por gráfico (vs ~4.8MB del
plotly.js inline). Requiere chromium provisionado (rol observer_api, gate
observer_reporting_charts_enabled); sin él, solo esos 4 dashboards fallan al
renderizar — las 15 plantillas de tabla no dependen de gráficos.

"Cobertura de Antivirus" deriva el AV instalado del inventario de software
(installedsoftware.software, JSONB; solo Windows): heurística por lista editable
de firmas de vendors + detección PARCIAL de Defender integrado (aparte). Refleja
el AV instalado, no su estado activo. KPIs+tabla, no requiere chromium.

Fuera de alcance (a propósito):
  - "All Fields *": volcados de schema para autores de plantillas, no reportes.
  - Bitlocker / Custom Fields: dependen de custom fields inexistentes en fresh.

Idempotente: re-ejecutar actualiza en su lugar (--overwrite, por defecto True).
Uso:  python manage.py load_curated_reports [--no-overwrite]
"""

import yaml
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
  /* --- Dashboards con graficos (W005) — clases aditivas, no tocan lo anterior --- */
  .kpi-row { display: flex; gap: 10px; margin: 14px 0; flex-wrap: wrap; }
  .kpi { flex: 1; min-width: 130px; background: #f3f9fb; border: 1px solid #dbe6ea;
    border-left: 4px solid #0E8FA8; border-radius: 6px; padding: 10px 14px; }
  .kpi-num { font-size: 26px; font-weight: bold; color: #0b6b7f; line-height: 1.1;
    font-variant-numeric: tabular-nums; }
  .kpi-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
    color: #7a929b; margin-top: 2px; }
  .kpi-crit { border-left-color: #c0392b; } .kpi-crit .kpi-num { color: #c0392b; }
  .kpi-warn { border-left-color: #e08e0b; } .kpi-warn .kpi-num { color: #e08e0b; }
  .kpi-ok { border-left-color: #2e9e6b; } .kpi-ok .kpi-num { color: #2e9e6b; }
  .chart-grid { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0; }
  .chart-card { border: 1px solid #dbe6ea; border-radius: 6px; padding: 6px; background: #fff; }
  .chart-card svg { display: block; max-width: 100%; height: auto; }
  .section-title { color: #0b6b7f; border-bottom: 2px solid #0E8FA8; margin: 18px 0 4px; font-size: 14px; }
  .ok { color: #2e9e6b; }
  .sev-error, .sev-failing, .st-offline { background: #c0392b; }
  .sev-warning, .sev-pending, .st-overdue { background: #e08e0b; }
  .sev-info { background: #0E8FA8; }
  .sev-passing, .st-online { background: #2e9e6b; }
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
        "  <div class=\"report-meta\">Generado: {{ now.strftime('%d-%m-%Y %H:%M') }}"
        "<br>" + extra + "</div>\n"
        "</div>\n"
    )


END = "\n{% endblock %}\n"


# ===========================================================================
# AGENTES
# ===========================================================================

# 1) Inventario de Agentes
INV_AGENTES = (
    _header("Inventario de Agentes", "Equipos: {{ data_sources.agents | length }}")
    + """
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
</table>"""
    + END
)
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
SPECS = (
    _header(
        "Especificaciones de Equipos", "Equipos: {{ data_sources.agents | length }}"
    )
    + """
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
</table>"""
    + END
)
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
AGENTES_CLIENTE_SITIO = (
    _header(
        "Agentes por Cliente y Sitio", "Equipos: {{ data_sources.agents | length }}"
    )
    + """
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
{% endfor %}"""
    + END
)
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
UPTIME = (
    _header(
        "Tiempo de Actividad de Equipos", "Equipos: {{ data_sources.agents | length }}"
    )
    + """
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
</table>"""
    + END
)
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
PENDING_REBOOT = (
    _header(
        "Equipos con Reinicio Pendiente",
        "Pendientes: {{ data_sources.agents | length }}",
    )
    + """
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
{% if data_sources.agents | length == 0 %}<p class="muted">Ning&uacute;n equipo requiere reinicio.</p>{% endif %}"""
    + END
)
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
INSTALL_DATE = (
    _header(
        "Fecha de Instalaci&oacute;n del Agente",
        "Equipos: {{ data_sources.agents | length }}",
    )
    + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Sistema Operativo</th><th>Instalado</th></tr></thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='created_time') %}
    <tr><td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      {% if a.created_time %}<td>{{ a.created_time.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y') }}</td>{% else %}<td class="muted">—</td>{% endif %}</tr>
  {% endfor %}
  </tbody>
</table>"""
    + END
)
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
OS_REPORT = (
    _header(
        "Distribuci&oacute;n de Sistemas Operativos",
        "Equipos: {{ data_sources.agents | length }}",
    )
    + """
<table class="report-table" style="max-width: 640px;">
  <thead><tr><th>Sistema Operativo</th><th>Cantidad</th></tr></thead>
  <tbody>
  {% for os, group in data_sources.agents | sort(attribute='operating_system') | groupby('operating_system') %}
    <tr><td>{{ os or '(desconocido)' }}</td><td class="num">{{ group | length }}</td></tr>
  {% endfor %}
  </tbody>
</table>"""
    + END
)
OS_REPORT_VARS = """data_sources:
  agents:
    model: agent
    only:
    - operating_system
"""

# 8) Reporte Integral de Equipos
INTEGRAL = (
    _header(
        "Reporte Integral de Equipos", "Equipos: {{ data_sources.agents | length }}"
    )
    + """
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
</table>"""
    + END
)
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
SOFTWARE = (
    _header("Inventario de Software", "Equipos: {{ data_sources.inv | length }}") + """
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
)
SOFTWARE_VARS = """data_sources:
  inv:
    model: installedsoftware
    only:
    - software
    - agent__hostname
    - agent__site__name
"""

# 10) Software por Cliente
SOFTWARE_CLIENTE = (
    _header("Software por Cliente", "Equipos: {{ data_sources.inv | length }}") + """
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
)
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
WU_PENDIENTES = (
    _header(
        "Actualizaciones de Windows Pendientes",
        "Pendientes: {{ data_sources.updates | length }}",
    )
    + """
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
</table>"""
    + END
)
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
WU_SITIO = (
    _header(
        "Actualizaciones Pendientes por Sitio",
        "Pendientes: {{ data_sources.updates | length }}",
    )
    + """
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
{% endfor %}"""
    + END
)
WU_SITIO_VARS = WU_PENDIENTES_VARS

# 13) Últimas Actualizaciones Instaladas
WU_INSTALADAS = (
    _header(
        "&Uacute;ltimas Actualizaciones Instaladas",
        "Registros: {{ data_sources.updates | length }}",
    )
    + """
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Equipo</th><th>KB</th><th>T&iacute;tulo</th><th>Instalada</th></tr></thead>
  <tbody>
  {% for u in data_sources.updates | sort(attribute='date_installed', reverse=True) %}
    <tr><td>{{ u.agent__site__client__name }}</td><td>{{ u.agent__hostname }}</td>
      <td>{{ u.kb or '—' }}</td><td>{{ u.title }}</td>
      <td>{% if u.date_installed %}{{ u.date_installed.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y') }}{% else %}—{% endif %}</td></tr>
  {% endfor %}
  </tbody>
</table>"""
    + END
)
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
AUDITORIA = (
    _header(
        "Registro de Auditor&iacute;a", "Registros: {{ data_sources.logs | length }}"
    )
    + """
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
</table>"""
    + END
)
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


# ===========================================================================
# DASHBOARDS CON GRÁFICOS (W005 — plotly/Kaleido → SVG)
# ---------------------------------------------------------------------------
# Los template_variables de estos dashboards llevan, además de data_sources, un
# bloque `charts:` que el motor (process_chart_variables) resuelve a SVG ANTES
# de renderizar la plantilla; en la plantilla se inyecta con {{ charts.<clave> }}.
# Se construyen con yaml.dump desde dicts Python: garantiza YAML válido y evita
# el escape manual de los colores "#hex" (en YAML crudo, # inicia comentario).
#
# outputType: image (SVG) — a propósito, NO "html":
#   · el SVG rinde idéntico en Preview, HTML export y PDF (WeasyPrint no ejecuta JS),
#   · pesa ~6KB vs ~4.8MB por gráfico del plotly.js inline (un dashboard = varios).
# Conteos: pie(names) e histogram(x) AGREGAN por categoría al renderizar (validado
# E2E contra Kaleido+chromium). Colores semánticos vía color_discrete_map donde la
# categoría es conocida (severidad, estado); paleta cian on-brand en el resto.
# ===========================================================================

_FONT = {"family": "Helvetica Neue, Arial", "size": 12}
_CYAN_SEQ = ["#0E8FA8", "#5AB4C5", "#0b6b7f", "#8fd0dc", "#7a929b"]
_SEV_MAP = {"error": "#c0392b", "warning": "#e08e0b", "info": "#0E8FA8"}
_CHK_MAP = {"passing": "#2e9e6b", "failing": "#c0392b", "pending": "#e08e0b"}
_AGENT_MAP = {"online": "#2e9e6b", "offline": "#c0392b", "overdue": "#e08e0b"}


def _pie(df, names, title, cmap=None):
    options = {"data_frame": df, "names": names}
    if cmap:
        # color semántico: color=<campo> + mapa categoría→hex
        options["color"] = names
        options["color_discrete_map"] = cmap
    else:
        options["color_discrete_sequence"] = _CYAN_SEQ
    return {
        "chartType": "pie",
        "outputType": "image",
        "options": options,
        "traces": {"textinfo": "value+percent", "textposition": "inside"},
        "layout": {
            "title": {"text": title},
            "width": 430,
            "height": 300,
            "margin": {"t": 40, "b": 10, "l": 10, "r": 10},
            "paper_bgcolor": "white",
            "font": _FONT,
        },
    }


def _hist(df, x, title, tickangle=0):
    layout = {
        "title": {"text": title},
        "width": 430,
        "height": 300,
        "margin": {"t": 40, "b": 80 if tickangle else 45, "l": 45, "r": 15},
        "yaxis_title": "Cantidad",
        "xaxis_title": "",
        "showlegend": False,
        "bargap": 0.3,
        "paper_bgcolor": "white",
        "plot_bgcolor": "#f8fbfc",
        "font": _FONT,
    }
    if tickangle:
        layout["xaxis"] = {"tickangle": tickangle}
    return {
        "chartType": "histogram",
        "outputType": "image",
        "options": {"data_frame": df, "x": x, "color_discrete_sequence": ["#0E8FA8"]},
        "layout": layout,
    }


def _dash_vars(data_sources, charts):
    return yaml.dump(
        {"data_sources": data_sources, "charts": charts},
        sort_keys=False,
        allow_unicode=True,
    )


# 15) Panel de Alertas (NOC) — alertas activas
ALERTAS = (
    _header("Panel de Alertas", "Activas: {{ data_sources.alerts | length }}") + """
{% set al = data_sources.alerts %}
<div class="kpi-row">
  <div class="kpi"><div class="kpi-num">{{ al | length }}</div><div class="kpi-lbl">Alertas activas</div></div>
  <div class="kpi kpi-crit"><div class="kpi-num">{{ al | selectattr('severity','equalto','error') | list | length }}</div><div class="kpi-lbl">Errores</div></div>
  <div class="kpi kpi-warn"><div class="kpi-num">{{ al | selectattr('severity','equalto','warning') | list | length }}</div><div class="kpi-lbl">Advertencias</div></div>
  <div class="kpi"><div class="kpi-num">{{ al | selectattr('severity','equalto','info') | list | length }}</div><div class="kpi-lbl">Informativas</div></div>
</div>
{% if al | length %}
<div class="chart-grid">
  {% if charts.sev %}<div class="chart-card">{{ charts.sev }}</div>{% endif %}
  {% if charts.tipo %}<div class="chart-card">{{ charts.tipo }}</div>{% endif %}
  {% if charts.cliente %}<div class="chart-card">{{ charts.cliente }}</div>{% endif %}
</div>
<div class="section-title">Detalle de alertas activas</div>
<table class="report-table">
  <thead><tr><th>Severidad</th><th>Tipo</th><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Mensaje</th><th>Fecha</th></tr></thead>
  <tbody>
  {% for a in al %}
    <tr>
      <td><span class="badge sev-{{ (a.severity or '')|lower }}">{{ a.severity or 'N/D' }}</span></td>
      <td>{{ a.alert_type }}</td>
      <td>{{ a.agent__site__client__name or '—' }}</td><td>{{ a.agent__site__name or '—' }}</td>
      <td><b>{{ a.agent__hostname or '—' }}</b></td>
      <td>{{ (a.message or '—') | truncate(80) }}</td>
      <td>{% if a.alert_time %}{{ a.alert_time.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}{% else %}—{% endif %}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p class="ok" style="font-size:14px;margin-top:16px;">Sin alertas activas. Toda la flota est&aacute; en verde.</p>
{% endif %}""" + END
)
ALERTAS_VARS = _dash_vars(
    {
        "alerts": {
            "model": "alert",
            "filter": {"resolved": False, "hidden": False},
            "only": [
                "severity",
                "alert_type",
                "message",
                "alert_time",
                "agent__hostname",
                "agent__site__name",
                "agent__site__client__name",
            ],
        }
    },
    {
        "sev": _pie(
            "data_sources.alerts", "severity", "Alertas por severidad", _SEV_MAP
        ),
        "tipo": _hist("data_sources.alerts", "alert_type", "Alertas por tipo"),
        "cliente": _hist(
            "data_sources.alerts",
            "agent__site__client__name",
            "Alertas por cliente",
            -30,
        ),
    },
)

# 16) Estado de Chequeos (NOC) — salud de monitoreo
CHEQUEOS = (
    _header("Estado de Chequeos", "Resultados: {{ data_sources.checks | length }}")
    + """
{% set ch = data_sources.checks %}
<div class="kpi-row">
  <div class="kpi"><div class="kpi-num">{{ ch | length }}</div><div class="kpi-lbl">Chequeos</div></div>
  <div class="kpi kpi-ok"><div class="kpi-num">{{ ch | selectattr('status','equalto','passing') | list | length }}</div><div class="kpi-lbl">OK</div></div>
  <div class="kpi kpi-crit"><div class="kpi-num">{{ ch | selectattr('status','equalto','failing') | list | length }}</div><div class="kpi-lbl">Fallando</div></div>
  <div class="kpi kpi-warn"><div class="kpi-num">{{ ch | selectattr('status','equalto','pending') | list | length }}</div><div class="kpi-lbl">Pendientes</div></div>
</div>
{% if ch | length %}
<div class="chart-grid">
  {% if charts.estado %}<div class="chart-card">{{ charts.estado }}</div>{% endif %}
  {% if charts.fallos %}<div class="chart-card">{{ charts.fallos }}</div>{% endif %}
</div>
<div class="section-title">Chequeos fallando ({{ data_sources.fallando | length }})</div>
{% if data_sources.fallando | length %}
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Tipo</th><th>Detalle</th><th>&Uacute;ltima ejecuci&oacute;n</th></tr></thead>
  <tbody>
  {% for c in data_sources.fallando %}
    <tr><td>{{ c.agent__site__client__name or '—' }}</td><td>{{ c.agent__site__name or '—' }}</td>
      <td><b>{{ c.agent__hostname or '—' }}</b></td><td>{{ c.assigned_check__check_type or '—' }}</td>
      <td>{{ (c.more_info or '—') | truncate(70) }}</td>
      <td>{% if c.last_run %}{{ c.last_run.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}{% else %}—{% endif %}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p class="ok">Ning&uacute;n chequeo est&aacute; fallando.</p>{% endif %}
{% else %}
<p class="muted" style="margin-top:16px;">No hay resultados de chequeos registrados.</p>
{% endif %}"""
    + END
)
CHEQUEOS_VARS = _dash_vars(
    {
        "checks": {
            "model": "checkresult",
            "only": [
                "status",
                "assigned_check__check_type",
                "last_run",
                "agent__hostname",
                "agent__site__name",
                "agent__site__client__name",
            ],
        },
        "fallando": {
            "model": "checkresult",
            "filter": {"status": "failing"},
            "only": [
                "status",
                "assigned_check__check_type",
                "more_info",
                "last_run",
                "agent__hostname",
                "agent__site__name",
                "agent__site__client__name",
            ],
        },
    },
    {
        "estado": _pie(
            "data_sources.checks", "status", "Chequeos por estado", _CHK_MAP
        ),
        "fallos": _hist(
            "data_sources.fallando",
            "assigned_check__check_type",
            "Fallos por tipo de chequeo",
            -30,
        ),
    },
)

# 17) Estado de la Flota — panorama de agentes
FLOTA = (
    _header("Estado de la Flota", "Equipos: {{ data_sources.agents | length }}") + """
{% set ag = data_sources.agents %}
<div class="kpi-row">
  <div class="kpi"><div class="kpi-num">{{ ag | length }}</div><div class="kpi-lbl">Equipos</div></div>
  <div class="kpi kpi-ok"><div class="kpi-num">{{ ag | selectattr('status','equalto','online') | list | length }}</div><div class="kpi-lbl">En l&iacute;nea</div></div>
  <div class="kpi kpi-crit"><div class="kpi-num">{{ ag | selectattr('status','equalto','offline') | list | length }}</div><div class="kpi-lbl">Fuera de l&iacute;nea</div></div>
  <div class="kpi kpi-warn"><div class="kpi-num">{{ ag | selectattr('status','equalto','overdue') | list | length }}</div><div class="kpi-lbl">Atrasados</div></div>
</div>
{% if ag | length %}
<div class="chart-grid">
  {% if charts.estado %}<div class="chart-card">{{ charts.estado }}</div>{% endif %}
  {% if charts.plataforma %}<div class="chart-card">{{ charts.plataforma }}</div>{% endif %}
  {% if charts.so %}<div class="chart-card">{{ charts.so }}</div>{% endif %}
  {% if charts.cliente %}<div class="chart-card">{{ charts.cliente }}</div>{% endif %}
</div>
{% set attention = ag | rejectattr('status','equalto','online') | list %}
<div class="section-title">Equipos que requieren atenci&oacute;n ({{ attention | length }})</div>
{% if attention | length %}
<table class="report-table">
  <thead><tr><th>Estado</th><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Sistema Operativo</th><th>&Uacute;ltima conexi&oacute;n</th></tr></thead>
  <tbody>
  {% for a in attention | sort(attribute='status') %}
    <tr><td><span class="badge st-{{ (a.status or '')|lower }}">{{ a.status or 'N/D' }}</span></td>
      <td>{{ a.site__client__name }}</td><td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td><td>{{ a.operating_system }}</td>
      {% if a.last_seen %}<td class="stale">{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>{% else %}<td class="muted">—</td>{% endif %}</tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p class="ok">Toda la flota est&aacute; en l&iacute;nea.</p>{% endif %}
{% else %}
<p class="muted" style="margin-top:16px;">No hay equipos registrados.</p>
{% endif %}""" + END
)
FLOTA_VARS = _dash_vars(
    {
        "agents": {
            "model": "agent",
            "only": [
                "hostname",
                "operating_system",
                "plat",
                "last_seen",
                "site__name",
                "site__client__name",
            ],
            "properties": ["status"],
        }
    },
    {
        "estado": _pie(
            "data_sources.agents", "status", "Estado de la flota", _AGENT_MAP
        ),
        "plataforma": _pie("data_sources.agents", "plat", "Por plataforma"),
        "so": _hist(
            "data_sources.agents", "operating_system", "Por sistema operativo", -30
        ),
        "cliente": _hist(
            "data_sources.agents", "site__client__name", "Por cliente", -30
        ),
    },
)

# 18) Panorama de Parches — Windows Updates pendientes
PARCHES = (
    _header("Panorama de Parches", "Pendientes: {{ data_sources.updates | length }}")
    + """
{% set up = data_sources.updates %}
<div class="kpi-row">
  <div class="kpi kpi-warn"><div class="kpi-num">{{ up | length }}</div><div class="kpi-lbl">Parches pendientes</div></div>
  <div class="kpi"><div class="kpi-num">{{ up | map(attribute='agent__hostname') | select | unique | list | length }}</div><div class="kpi-lbl">Equipos afectados</div></div>
  <div class="kpi"><div class="kpi-num">{{ up | map(attribute='agent__site__client__name') | select | unique | list | length }}</div><div class="kpi-lbl">Clientes afectados</div></div>
</div>
{% if up | length %}
<div class="chart-grid">
  {% if charts.sev %}<div class="chart-card">{{ charts.sev }}</div>{% endif %}
  {% if charts.cliente %}<div class="chart-card">{{ charts.cliente }}</div>{% endif %}
</div>
<div class="section-title">Pendientes por cliente</div>
<table class="report-table" style="max-width: 560px;">
  <thead><tr><th>Cliente</th><th>Pendientes</th><th>Equipos</th></tr></thead>
  <tbody>
  {% for client, rows in up | sort(attribute='agent__site__client__name') | groupby('agent__site__client__name') %}
    <tr><td>{{ client or '(sin cliente)' }}</td><td class="num">{{ rows | length }}</td>
      <td class="num">{{ rows | map(attribute='agent__hostname') | select | unique | list | length }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p class="ok" style="font-size:14px;margin-top:16px;">No hay actualizaciones pendientes.</p>
{% endif %}"""
    + END
)
PARCHES_VARS = _dash_vars(
    {
        "updates": {
            "model": "winupdate",
            "filter": {"installed": False},
            "only": [
                "severity",
                "kb",
                "title",
                "agent__hostname",
                "agent__site__name",
                "agent__site__client__name",
            ],
        }
    },
    {
        "sev": _pie("data_sources.updates", "severity", "Pendientes por severidad"),
        "cliente": _hist(
            "data_sources.updates",
            "agent__site__client__name",
            "Pendientes por cliente",
            -30,
        ),
    },
)


# ===========================================================================
# SEGURIDAD
# ---------------------------------------------------------------------------
# 19) Cobertura de Antivirus. Deriva el AV instalado del inventario de software
# (installedsoftware.software, JSONB), acotado a Windows. NO usa gráficos W005:
# la clasificación con/sin AV se computa en la PLANTILLA (namespace + do), y el
# resolver de charts navega data_sources ANTES del render, así que no podría
# consumir un campo derivado. Al ser KPIs+tabla, tampoco depende de chromium.
# Salvedades (documentadas en la nota del propio reporte): refleja AV
# INSTALADO, no su estado activo/firmas; Defender integrado se detecta APARTE
# (decisión 1a) y de forma PARCIAL —por ser componente del SO no siempre figura
# como programa instalado—; la lista de firmas es EDITABLE en la plantilla.
# ===========================================================================
ANTIVIRUS = (
    _header(
        "Cobertura de Antivirus", "Equipos Windows: {{ data_sources.avinv | length }}"
    )
    + """
{= ===================================================================== =}
{=  FIRMAS DE AV DE TERCEROS — LISTA EDITABLE                            =}
{=  Formato: [subcadena_en_minusculas, etiqueta]. El match es por        =}
{=  subcadena sobre (name + publisher) en minusculas. Para agregar o     =}
{=  quitar un producto, edita esta lista.                                =}
{= ===================================================================== =}
{% set av_signatures = [
  ["eset", "ESET"], ["kaspersky", "Kaspersky"], ["bitdefender", "Bitdefender"],
  ["sophos", "Sophos"], ["crowdstrike", "CrowdStrike"], ["sentinelone", "SentinelOne"],
  ["norton", "Norton"], ["symantec", "Symantec"], ["mcafee", "McAfee"],
  ["trellix", "Trellix"], ["trend micro", "Trend Micro"], ["avast", "Avast"],
  ["avg ", "AVG"], ["webroot", "Webroot"], ["malwarebytes", "Malwarebytes"]
] %}
{= Defender integrado se detecta APARTE (deteccion parcial: por ser        =}
{= componente del SO no siempre figura como programa instalado).          =}
{% set defender_signatures = ["windows defender", "microsoft defender"] %}
{% set rows = [] %}
{% for r in data_sources.avinv %}
  {% set ns = namespace(third=[], defender=false) %}
  {% for sw in r.software or [] %}
    {% set hay = ((sw.name or '') ~ ' ' ~ (sw.publisher or '')) | lower %}
    {% for sig, label in av_signatures %}
      {% if sig in hay and label not in ns.third %}{% do ns.third.append(label) %}{% endif %}
    {% endfor %}
    {% for dsig in defender_signatures %}
      {% if dsig in hay %}{% set ns.defender = true %}{% endif %}
    {% endfor %}
  {% endfor %}
  {% do rows.append({
    "hostname": r.agent__hostname, "site": r.agent__site__name,
    "client": r.agent__site__client__name, "third": ns.third, "defender": ns.defender,
    "status": ("third" if ns.third else ("defender" if ns.defender else "none"))
  }) %}
{% endfor %}
{% set con3 = rows | selectattr("status","equalto","third") | list %}
{% set solod = rows | selectattr("status","equalto","defender") | list %}
{% set sinav = rows | selectattr("status","equalto","none") | list %}
<div class="kpi-row">
  <div class="kpi"><div class="kpi-num">{{ rows | length }}</div><div class="kpi-lbl">Equipos Windows</div></div>
  <div class="kpi kpi-ok"><div class="kpi-num">{{ con3 | length }}</div><div class="kpi-lbl">Con AV de terceros</div></div>
  <div class="kpi kpi-warn"><div class="kpi-num">{{ solod | length }}</div><div class="kpi-lbl">Solo Defender detectado</div></div>
  <div class="kpi kpi-crit"><div class="kpi-num">{{ sinav | length }}</div><div class="kpi-lbl">Sin AV detectado</div></div>
</div>
<p class="muted" style="font-size:10px; margin:6px 0 14px;">
  Detecci&oacute;n por <b>inventario de software</b> (solo Windows): refleja el AV <b>instalado</b>,
  no su estado activo ni sus firmas al d&iacute;a. Microsoft Defender integrado puede no figurar como
  programa instalado, por lo que su detecci&oacute;n aqu&iacute; es parcial. Lista de productos editable en la plantilla.
</p>
{% if sinav | length %}
<div class="section-title">Equipos sin AV detectado ({{ sinav | length }})</div>
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th></tr></thead>
  <tbody>
  {% for a in sinav | sort(attribute="hostname") %}
    <tr><td>{{ a.client or '—' }}</td><td>{{ a.site or '—' }}</td><td><b>{{ a.hostname }}</b></td></tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p class="ok" style="margin-top:12px;">Todos los equipos Windows tienen un AV detectado.</p>
{% endif %}
<div class="section-title">Equipos con AV de terceros ({{ con3 | length }})</div>
{% if con3 | length %}
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Equipo</th><th>Producto(s) detectado(s)</th></tr></thead>
  <tbody>
  {% for a in con3 | sort(attribute="hostname") %}
    <tr><td>{{ a.client or '—' }}</td><td><b>{{ a.hostname }}</b></td>
      <td>{{ a.third | join(', ') }}{% if a.third | length > 1 %} <span class="badge sev-moderate">m&uacute;ltiples</span>{% endif %}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p class="muted">Ning&uacute;n equipo con AV de terceros detectado.</p>{% endif %}
{% if solod | length %}
<div class="section-title">Solo Microsoft Defender detectado ({{ solod | length }})</div>
<table class="report-table">
  <thead><tr><th>Cliente</th><th>Sitio</th><th>Equipo</th></tr></thead>
  <tbody>
  {% for a in solod | sort(attribute="hostname") %}
    <tr><td>{{ a.client or '—' }}</td><td>{{ a.site or '—' }}</td><td><b>{{ a.hostname }}</b></td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}"""
    + END
)
ANTIVIRUS_VARS = """data_sources:
  avinv:
    model: installedsoftware
    filter:
      agent__plat: windows
    only:
    - software
    - agent__hostname
    - agent__site__name
    - agent__site__client__name
"""


CURATED = [
    {
        "name": "Inventario de Agentes",
        "type": "html",
        "template_md": INV_AGENTES,
        "template_variables": INV_AGENTES_VARS,
    },
    {
        "name": "Especificaciones de Equipos",
        "type": "html",
        "template_md": SPECS,
        "template_variables": SPECS_VARS,
    },
    {
        "name": "Agentes por Cliente y Sitio",
        "type": "html",
        "template_md": AGENTES_CLIENTE_SITIO,
        "template_variables": AGENTES_CLIENTE_SITIO_VARS,
    },
    {
        "name": "Tiempo de Actividad de Equipos",
        "type": "html",
        "template_md": UPTIME,
        "template_variables": UPTIME_VARS,
    },
    {
        "name": "Equipos con Reinicio Pendiente",
        "type": "html",
        "template_md": PENDING_REBOOT,
        "template_variables": PENDING_REBOOT_VARS,
    },
    {
        "name": "Fecha de Instalacion del Agente",
        "type": "html",
        "template_md": INSTALL_DATE,
        "template_variables": INSTALL_DATE_VARS,
    },
    {
        "name": "Distribucion de Sistemas Operativos",
        "type": "html",
        "template_md": OS_REPORT,
        "template_variables": OS_REPORT_VARS,
    },
    {
        "name": "Reporte Integral de Equipos",
        "type": "html",
        "template_md": INTEGRAL,
        "template_variables": INTEGRAL_VARS,
    },
    {
        "name": "Inventario de Software",
        "type": "html",
        "template_md": SOFTWARE,
        "template_variables": SOFTWARE_VARS,
    },
    {
        "name": "Software por Cliente",
        "type": "html",
        "template_md": SOFTWARE_CLIENTE,
        "template_variables": SOFTWARE_CLIENTE_VARS,
    },
    {
        "name": "Actualizaciones de Windows Pendientes",
        "type": "html",
        "template_md": WU_PENDIENTES,
        "template_variables": WU_PENDIENTES_VARS,
    },
    {
        "name": "Actualizaciones Pendientes por Sitio",
        "type": "html",
        "template_md": WU_SITIO,
        "template_variables": WU_SITIO_VARS,
    },
    {
        "name": "Ultimas Actualizaciones Instaladas",
        "type": "html",
        "template_md": WU_INSTALADAS,
        "template_variables": WU_INSTALADAS_VARS,
    },
    {
        "name": "Registro de Auditoria",
        "type": "html",
        "template_md": AUDITORIA,
        "template_variables": AUDITORIA_VARS,
    },
    {
        "name": "Cobertura de Antivirus",
        "type": "html",
        "template_md": ANTIVIRUS,
        "template_variables": ANTIVIRUS_VARS,
    },
    # --- Dashboards con gráficos (W005 — requieren chromium provisionado) ---
    {
        "name": "Panel de Alertas",
        "type": "html",
        "template_md": ALERTAS,
        "template_variables": ALERTAS_VARS,
    },
    {
        "name": "Estado de Chequeos",
        "type": "html",
        "template_md": CHEQUEOS,
        "template_variables": CHEQUEOS_VARS,
    },
    {
        "name": "Estado de la Flota",
        "type": "html",
        "template_md": FLOTA,
        "template_variables": FLOTA_VARS,
    },
    {
        "name": "Panorama de Parches",
        "type": "html",
        "template_md": PARCHES,
        "template_variables": PARCHES_VARS,
    },
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
