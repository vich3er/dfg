# Самооцінка за критеріями (C1–C4)

| Результат | C1 | C2 | C3 | C4 | Де перевірити |
|---|---|---|---|---|---|
| 1. Зерно, питання, схема | Зерно + 7 питань | 5 вимірів, `dim_topic` з IRI | міри класифіковано | `python etl/load.py` без помилок; `star_schema.png` | `docs/star_design.md`, `sql/ddl.sql` |
| 2. ELT | 3096 рядків, генератор описано | `sql/checks/orphans.sql` = 0 | 14 перевірок, `docs/quality_report.md` | `data/*.parquet`, `VERSION.json` | `etl/`, `data/` |
| 3. OLAP | 13 запитів (ROLLUP, CUBE, GROUPING SETS, slice, dice, PIVOT, вікна ×3, drill-down, self-join) | питання + інтерпретація | `10a`/`10b` | 2 перевірки у pandas | `sql/olap/`, `docs/olap_results.md` |
| 4. Семантичний шар | 8 метрик з усіма полями | `metric_sql()` | `docs/consistency_report.md` | власник, дата, статус | `semantic/` |
| 5. Text-to-SQL і панель | AST, read-only, LIMIT, тайм-аут | 19 питань, 3 помилки проаналізовано | 5 візуалізацій з інтерпретаціями | 7 ризиків | `text2sql/`, `tests/`, `dashboard/`, `docs/risks.md` |

**Протокол «LLM-експерт»:** без заповненого `llm_log/` і `claims/claims.csv` результат, що спирається на LLM, отримує максимум 0.25 бала. Див. `llm_log/README.md`.
