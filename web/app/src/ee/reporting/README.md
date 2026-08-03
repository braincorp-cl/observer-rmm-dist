# Reportes — módulo re-adoptado (Observer Reporting)

> **Estado:** re-adoptado desde nuestro propio linaje forkeado (feature `022`, 2026-07-15).
> Reemplaza el descarte de ADR-010 (2026-06-17). Ver la reconciliación en Reversa.

El módulo de Reportes fue **recuperado** desde el historial git rebrandeado (`f6a1e5a^`) —
la misma operación que los backports de código upstream que ya están en producción, **no**
una importación de contenido de terceros:

- El **motor es 100 % local** (Jinja2 sandboxed + Markdown + WeasyPrint para PDF). No hay
  llamadas HTTP salientes: la dependencia del catálogo de plantillas de la comunidad
  (`SharedTemplatesRepo` → upstream) ya fue eliminada (ADR-014) y **no** se restaura.
- El importador per-archivo (`ImportReportTemplate`) sí queda disponible: las plantillas se
  autoran localmente y sus assets caen a `/opt/observer/reporting/assets` (filesystem local).

## Toques de infra pendientes (ver roadmap de la feature 022)

- **plotly.js**: los gráficos en formato HTML referencian `include_plotlyjs="cdn"` →
  auto-hospedar (patrón `agents.observer.cl`) o pasar a `inline`.
- **chromium**: Kaleido (gráficos como imagen/SVG) requiere un runtime Chrome que Ansible
  aún no provisiona → agregar al rol `observer_api` (igual que las libs de WeasyPrint).

## Plantillas curadas

Las plantillas del proyecto de origen **no** se importan tal cual (licencia propietaria
de su autor + strings legacy). Se usan como **referencia** para autorar plantillas propias
BrainCorp (mismas queries, schema compartido), bajo licencia BrainCorp.
