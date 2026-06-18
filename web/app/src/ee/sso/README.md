# SSO — módulo descartado, pendiente de reimplementación desde cero

> **Estado:** vacío a propósito. Ver `_reversa_sdd/adrs/010-descarte-modulos-reportes-sso.md`.

El módulo de Single Sign-On (heredado del upstream EE legado) fue **descartado** el 2026-06-17 (ADR-010):

- La implementación legada **no estaba completa al 100%** y presentaba **vulnerabilidades de seguridad confirmadas** — en particular el LEAK del `secret` OAuth en texto plano vía `GET /accounts/ssoproviders/` (RN-SSO-C / GAP-09).
- La feature `001-disable-sso-ui` ya había deshabilitado la UI SSO tras el flag de build `SSO_DISABLED`; ADR-010 completa el descarte del módulo entero.

**No restaurar el código legado.** La reimplementación debe hacerse **desde cero**, con un diseño seguro que nunca exponga el `secret` al frontend. Las specs del legado quedan como referencia funcional en `_reversa_sdd/sso/` (marcadas con cabecera de DESCARTE).
