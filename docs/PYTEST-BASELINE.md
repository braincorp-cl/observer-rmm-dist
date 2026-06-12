# Baseline pytest oficial del dist (D-09)

> F008 `consolidacion-dist` — actualizado 2026-06-12

El baseline se produce con el gate IaC `smoke.yml` (VM desechable Ubuntu 22.04,
PostgreSQL 15 PGDG + Redis + Python 3.11.8 compilado desde fuente, entorno
`GHACTIONS=1` / `DJANGO_SETTINGS_MODULE=observerrmm.settings`). La salida
completa de cada corrida queda en `smoke-results/F008-baseline-pytest.txt`.

## Baseline vigente

| Campo | Valor |
|-------|-------|
| Fecha | 2026-06-12 |
| Código bajo test | backend consolidado del dist con DF-03 (commit dist `4bce1b9`) |
| Resultado | **644 passed, 0 failed, 6 warnings, 21 subtests** (573.39s) |
| Smokes acompañantes | `manage.py check` OK · `makemigrations --check` OK · test R-09 1 passed + 6 subtests |

Sin tests skipped ni xfailed en la suite.

## Trazabilidad

| Hito | Fecha | Código de origen | Resultado | Registro |
|------|-------|------------------|-----------|----------|
| Baseline D-09 original (gate Fase 0 / RN-04) | 2026-06-11 | hub `099cc1a0` (pre-consolidación) | 639 passed, 0 failed, 6 subtests (531.88s) | commit dist `25b6dc9` |
| Baseline post-DF-03 (T018, Fase 2 endurecimiento) | 2026-06-12 | dist `4bce1b9` | 644 passed, 0 failed, 21 subtests | este documento + `smoke-results/` |

Delta 639 → 644: los 5 tests nuevos de `autotasks/tests/test_schedule_constraints.py`
(CheckConstraints DF-03, F008/T017). Delta de subtests 6 → 21: sub-tests
parametrizados de los tests DF-03 (6 violaciones + 9 controles) que se suman a
los 6 del test R-09.

## Incidencia registrada (primera corrida post-DF-03)

La primera corrida del gate con los constraints falló: 7 ERROR en
`test_scheduler.py` (fixture creaba tasks en dos pasos, INSERT incompleto
violaba el constraint) y 4 FAILED en `ee/reporting/test_data_queries.py`
(dependencia latente de polución del cache Redis de CoreSettings, expuesta al
cortarse la cadena por los ERROR anteriores). Ambos eran defectos de los
tests, no del producto. Fixes en hub `85c4a54a` (fuente de verdad, flujo D-08)
espejados al dist en `4bce1b9` (acciones F008 T039/T040).
