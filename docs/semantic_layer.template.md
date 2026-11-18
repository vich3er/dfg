# Результат 4. Семантичний шар

**Артефакти:** `semantic/metrics.yml`, `docs/semantic_layer.md`; код — `semantic/semantic.py`.

## Що дає семантичний шар

Єдине місце, де *один раз* визначено, що таке «частка негативу», «середня тональність», «критична згадка», з формулою, одиницею, власником і обмеженнями.
Наслідки: (1) однакові результати в OLAP-запитах, панелі та text-to-SQL; (2) text-to-SQL бере не довільні формули, а затверджені метрики — менше галюцинацій;
(3) зміна визначення робиться в одному файлі; (4) видно власника й статус метрики (governance).

## Метрики

{{METRICS}}

## Виміри

{{DIMENSIONS}}

## Генерація SQL за назвою метрики

```python
from semantic.semantic import metric_sql
print(metric_sql("negative_share", group_by=["department"], filters={"year": 2026},
                 order_by=[("negative_share", "DESC")], limit=3))
```
CLI: `python semantic/semantic.py negative_share --by department --filter year=2026 --limit 3`

Функція `metric_sql` підключає лише потрібні виміри (JOIN), підставляє формулу метрики, округлення, фільтри (значення екрануються) і сортування.

## Узгодженість результатів

`python semantic/check_consistency.py` порівнює 4 питання трьома шляхами (семантичний SQL, ручний SQL, pandas); результат — `docs/consistency_report.md`.
