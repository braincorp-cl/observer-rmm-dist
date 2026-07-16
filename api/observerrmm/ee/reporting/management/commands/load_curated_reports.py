"""
Carga un set de plantillas de reportes curadas por BrainCorp para Observer RMM.

Una instalación fresca arranca con 0 ReportTemplate; esto siembra plantillas
propias, listas para usar y clonar. Son autoradas por BrainCorp (referencia
funcional: patrones públicos de RMM), rebrandeadas, sin dependencias externas
ni strings legacy, y ancladas a los modelos reales del producto.

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
  .report-table { border-collapse: collapse; width: 100%; margin-top: 14px; }
  .report-table th { background: #0E8FA8; color: #fff; text-align: left; padding: 6px 8px;
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.03em; }
  .report-table td { border-bottom: 1px solid #dbe6ea; padding: 5px 8px; vertical-align: top; }
  .report-table tr:nth-child(even) td { background: #f3f9fb; }
  .muted { color: #7a929b; }
  .stale { color: #c0392b; font-weight: bold; }
  .agent-title { color: #0E8FA8; margin: 16px 0 4px; font-size: 13px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px;
    font-weight: bold; color: #fff; }
  .sev-critical, .sev-important { background: #c0392b; }
  .sev-moderate { background: #e08e0b; }
  .sev-low, .sev-optional, .sev- { background: #5a7d8a; }
</style>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Cabecera reutilizable (se inserta por-plantilla; Jinja no comparte set()).
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 1) Inventario de Agentes
# ---------------------------------------------------------------------------
INVENTARIO_AGENTES_MD = _header(
    "Inventario de Agentes", "Equipos: {{ data_sources.agents | length }}"
) + """
<table class="report-table">
  <thead>
    <tr>
      <th>Cliente</th><th>Sitio</th><th>Equipo</th><th>Usuario</th>
      <th>Sistema Operativo</th><th>RAM (GB)</th><th>IP p&uacute;blica</th><th>&Uacute;ltima conexi&oacute;n</th>
    </tr>
  </thead>
  <tbody>
  {% for a in data_sources.agents | sort(attribute='hostname') %}
    <tr>
      <td>{{ a.site__client__name }}</td>
      <td>{{ a.site__name }}</td>
      <td><b>{{ a.hostname }}</b></td>
      <td>{{ a.last_logged_in_user or '—' }}</td>
      <td>{{ a.operating_system }}</td>
      <td>{{ a.total_ram or '—' }}</td>
      <td>{{ a.public_ip or '—' }}</td>
      {% if a.last_seen %}
      <td {% if (now - a.last_seen.astimezone(ZoneInfo('America/Santiago'))).days > 7 %}class="stale"{% endif %}>{{ a.last_seen.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M') }}</td>
      {% else %}<td class="muted">—</td>{% endif %}
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
"""

INVENTARIO_AGENTES_VARS = """data_sources:
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


# ---------------------------------------------------------------------------
# 2) Actualizaciones de Windows Pendientes
# ---------------------------------------------------------------------------
WINUPDATES_MD = _header(
    "Actualizaciones de Windows Pendientes",
    "Pendientes: {{ data_sources.updates | length }}",
) + """
<table class="report-table">
  <thead>
    <tr><th>Cliente</th><th>Sitio</th><th>Equipo</th><th>KB</th><th>Severidad</th><th>T&iacute;tulo</th></tr>
  </thead>
  <tbody>
  {% for u in data_sources.updates | sort(attribute='agent__hostname') %}
    <tr>
      <td>{{ u.agent__site__client__name }}</td>
      <td>{{ u.agent__site__name }}</td>
      <td><b>{{ u.agent__hostname }}</b></td>
      <td>{{ u.kb or '—' }}</td>
      <td><span class="badge sev-{{ (u.severity or '')|lower }}">{{ u.severity or 'N/D' }}</span></td>
      <td>{{ u.title }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
"""

WINUPDATES_VARS = """data_sources:
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


# ---------------------------------------------------------------------------
# 3) Inventario de Software (por equipo)
# ---------------------------------------------------------------------------
SOFTWARE_MD = _header(
    "Inventario de Software", "Equipos: {{ data_sources.inv | length }}"
) + """
{% for row in data_sources.inv | sort(attribute='agent__hostname') %}
<h3 class="agent-title">{{ row.agent__hostname }}
  <span class="muted">— {{ row.agent__site__name }}</span>
  <span class="muted">({{ row.software | length }} programas)</span>
</h3>
<table class="report-table">
  <thead><tr><th>Nombre</th><th>Versi&oacute;n</th><th>Editor</th><th>Fecha instalaci&oacute;n</th></tr></thead>
  <tbody>
  {% for sw in row.software %}
    <tr>
      <td>{{ sw.name }}</td>
      <td>{{ sw.version or '—' }}</td>
      <td>{{ sw.publisher or '—' }}</td>
      <td>{{ sw.install_date or '—' }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endfor %}
{% endblock %}
"""

SOFTWARE_VARS = """data_sources:
  inv:
    model: installedsoftware
    only:
    - software
    - agent__hostname
    - agent__site__name
"""


CURATED = [
    {
        "name": "Inventario de Agentes",
        "type": "html",
        "template_md": INVENTARIO_AGENTES_MD,
        "template_variables": INVENTARIO_AGENTES_VARS,
    },
    {
        "name": "Actualizaciones de Windows Pendientes",
        "type": "html",
        "template_md": WINUPDATES_MD,
        "template_variables": WINUPDATES_VARS,
    },
    {
        "name": "Inventario de Software",
        "type": "html",
        "template_md": SOFTWARE_MD,
        "template_variables": SOFTWARE_VARS,
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
