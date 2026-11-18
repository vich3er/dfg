# Перевірка узгодженості семантичного шару

Кожне питання обчислено трьома шляхами: **A** — SQL із семантичного шару, **B** — ручний SQL, **C** — pandas.

| Питання | A = B | A = C | Рядків |
|---|---|---|---:|
| Частка негативних згадок по відділеннях | ✅ | ✅ | 10 |
| Середня тональність по класах у 2026 р. | ✅ | ✅ | 6 |
| Середній час очікування по кварталах | ✅ | ✅ | 7 |
| Загальна кількість згадок і відгуків | ✅ | ✅ | 1 |

Приклад SQL, згенерованого семантичним шляхом:

```sql
SELECT dep.department_name AS "department", ROUND(100.0 * SUM(f.is_negative) / SUM(f.mention_count), 1) AS negative_share
FROM fact_feedback_mention f
JOIN dim_department dep ON dep.department_key = f.department_key
JOIN dim_date dd ON dd.date_key = f.date_key
WHERE dd.year = 2026
GROUP BY dep.department_name
ORDER BY "negative_share" DESC
LIMIT 3
```
