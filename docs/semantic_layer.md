# Результат 4. Семантичний шар

**Артефакти:** `semantic/metrics.yml`, `docs/semantic_layer.md`; код — `semantic/semantic.py`.

## Що дає семантичний шар

Єдине місце, де *один раз* визначено, що таке «частка негативу», «середня тональність», «критична згадка», з формулою, одиницею, власником і обмеженнями.
Наслідки: (1) однакові результати в OLAP-запитах, панелі та text-to-SQL; (2) text-to-SQL бере не довільні формули, а затверджені метрики — менше галюцинацій;
(3) зміна визначення робиться в одному файлі; (4) видно власника й статус метрики (governance).

## Метрики

| Метрика | Визначення | Формула | Одиниця | Адитивність | Власник | Джерела | Обмеження | Статус | Перегляд |
|---|---|---|---|---|---|---|---|---|---|
| `mentions` (Кількість згадок) | Кількість згадок тем у відгуках (рядків факту). | `SUM(f.mention_count)` | згадок | адитивна | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.mention_count | Один відгук із n темами дає n згадок; не дорівнює кількості відгуків. | approved | 2026-11-19 |
| `feedback_count` (Кількість відгуків) | Кількість унікальних відгуків пацієнтів. | `COUNT(DISTINCT f.feedback_id)` | відгуків | неадитивна (distinct) | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.feedback_id | Не можна сумувати за темами/класами — відгук з кількома темами рахується в кожній (подвійний облік). | approved | 2026-11-19 |
| `negative_mentions` (Кількість негативних згадок) | Згадки з sentiment_score < -0.2. | `SUM(f.is_negative)` | згадок | адитивна | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.is_negative | Поріг -0.2 фіксований у ETL; зміна порогу потребує перезавантаження даних. | approved | 2026-11-19 |
| `negative_share` (Частка негативних згадок) | Відсоток негативних згадок від усіх згадок у вибраному зрізі. | `100.0 * SUM(f.is_negative) / SUM(f.mention_count)` | % | неадитивна (відношення) | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.is_negative, fact_feedback_mention.mention_count | Для підсумків рахується як відношення сум, а не середнє часток; надійно при ≥30 згадок у групі. | approved | 2026-11-19 |
| `avg_sentiment` (Середня тональність) | Середнє значення sentiment_score по згадках (шкала від -1 до +1). | `AVG(f.sentiment_score)` | бали [-1; 1] | неадитивна | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.sentiment_score | Оцінка тональності синтетична; середнє зважене кількістю згадок (відгуки з багатьма темами мають більшу вагу). | approved | 2026-11-19 |
| `critical_mentions` (Критичні згадки (безпека пацієнта)) | Негативні згадки з тем безпеки/моніторингу (MedicationSafety, AlarmResponse, VitalsMonitoring) із тональністю < -0.5. | `SUM(f.is_critical)` | згадок | адитивна | Відповідальний за безпеку пацієнтів | fact_feedback_mention.is_critical | Є сигналом для ручної перевірки, а не клінічним висновком. | approved | 2026-11-19 |
| `avg_wait_minutes` (Середній час очікування) | Середня заявлена тривалість очікування (хв) у відгуках на теми очікування. | `AVG(f.wait_minutes)` | хв | неадитивна | Начальник відділу організації медичної допомоги | fact_feedback_mention.wait_minutes | wait_minutes заповнено лише для підкласів EmergencyWait, AppointmentScheduling, DischargeProcess; для інших тем NULL ігнорується. | approved | 2026-11-19 |
| `avg_rating` (Середня загальна оцінка) | Середня загальна оцінка відгуку (1–5), усереднена по згадках. | `AVG(f.overall_rating)` | бали [1; 5] | неадитивна | Керівник аналітики якості (Quality Analytics) | fact_feedback_mention.overall_rating | Оцінка належить відгуку і повторюється для кожної його згадки, тому середнє зважене кількістю тем; для оцінки на рівні відгуку використовуйте окремий запит. | draft | 2026-11-19 |

## Виміри

| Вимір | Колонка | Опис |
|---|---|---|
| `department` | `dep.department_name` | Відділення (SCD1) |
| `division` | `dep.division_name` | Підрозділ (рівень вище відділення) |
| `topic_class` | `t.class_label` | Клас таксономії (рівень 1) |
| `topic` | `t.topic_label` | Підклас таксономії (рівень 2) |
| `topic_iri` | `t.topic_iri` | IRI підкласу таксономії |
| `channel` | `c.channel_name` | Канал збору відгуку |
| `year` | `dd.year` | Рік |
| `quarter` | `dd.quarter_label` | Квартал (напр. 2026-Q3) |
| `month` | `dd.month_label` | Місяць (напр. 2026-09) |
| `risk_group` | `p.risk_group` | Група ризику пацієнта на дату відгуку (SCD2) |
| `age_group` | `p.age_group` | Вікова група |

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
