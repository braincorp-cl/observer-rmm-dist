# Reportes — módulo descartado, pendiente de reimplementación desde cero

> **Estado:** vacío a propósito. Ver `_reversa_sdd/adrs/010-descarte-modulos-reportes-sso.md`.

El módulo de Reportes (heredado del upstream EE legado) fue **descartado** el 2026-06-17 (ADR-010):

- La implementación legada dependía de **sitios externos** (repositorios de plantillas de terceros y de la comunidad) para cargar/importar reportes — inviable como base propia.
- La feature `002-remove-shared-templates` ya había removido la importación de plantillas compartidas; ADR-010 completa el descarte del módulo entero.

**No restaurar el código legado.** La reimplementación debe hacerse **desde cero**, sin dependencias externas de repos de terceros/comunidad. Las specs del legado quedan como referencia funcional en `_reversa_sdd/reportes/` (marcadas con cabecera de DESCARTE).
