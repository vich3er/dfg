# ЛР12. OLAP-куб на основі таксономії — «Відгуки пацієнтів»

**Область:** Медицина · моніторинг стану пацієнтів · знання з відгуків пацієнтів · аналіз відгуків і моделі на основі семантичної мережі.
**Інструменти:** DuckDB, SQL, pandas, plotly. Дані — **синтетичні** (документований генератор, seed=42), реальних пацієнтів немає.

## Запуск з нуля
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./run_all.sh            # або команди з run_all.sh по черзі
```
Версії, що використовувались: Python 3.12, DuckDB 2.0, pandas 2.x (див. `data/VERSION.json`). Seed і розмір вибірки: `python etl/load.py --seed 42 --n-feedback 1500`.
Відкрити панель: `dashboard/dashboard.html` (для графіків потрібен інтернет — plotly підключається з CDN).

## Структура і відповідність результатам
| Результат | Артефакти | Команда |
|---|---|---|
| 1. Зерно, питання, схема | `docs/star_design.md`, `sql/ddl.sql`, `docs/star_schema.png` | `python docs/make_star_diagram.py` |
| 2. ELT | `etl/load.py`, `etl/generate_data.py`, `etl/quality_checks.py`, `sql/checks/orphans.sql`, `data/*.parquet`, `data/VERSION.json`, `docs/quality_report.md` | `python etl/load.py` |
| 3. OLAP | `sql/olap/*.sql` (13), `docs/olap_results.md`, `olap/run_olap.py` | `python olap/run_olap.py` |
| 4. Семантичний шар | `semantic/metrics.yml`, `semantic/semantic.py`, `docs/semantic_layer.md`, `docs/consistency_report.md` | `python semantic/check_consistency.py` |
| 5. Text-to-SQL і панель | `text2sql/`, `tests/t2sql.jsonl`, `tests/test_guard.py`, `tests/run_t2sql_eval.py`, `dashboard/`, `docs/risks.md`, `docs/t2sql_error_analysis.md` | `python tests/run_t2sql_eval.py` |
| Протокол LLM-експерта | `llm_log/`, `claims/claims.csv` | `python claims/claims_stats.py` |
| Звіт | `docs/report_template.md`, `docs/self_assessment.md` | — |

Семантична мережа: таблиця `topic_relation` та `data/feedback_semantic_network.ttl` (rdfs:subClassOf із таксономії + fb:coOccursWith із даних за lift).

## text-to-SQL
* За замовчуванням працює **rule-based baseline** (без LLM; ключ не потрібен).
* LLM-режим: `pip install anthropic`, `export ANTHROPIC_API_KEY=...` (ключ **не** зберігати в коді/репозиторії), `export CLAUDE_MODEL=<модель>`, потім `python tests/run_t2sql_eval.py --backend llm`. Виклики журналюються в `llm_log/t2sql_calls.jsonl`.
* Конвеєр: питання → бекенд → AST-перевірка (`sqlglot`: лише SELECT, whitelist таблиць, заборона `read_*`/DDL/DML) → примусовий LIMIT → виконання `read_only` з тайм-аутом.

## ⚠️ Що ви ОБОВ'ЯЗКОВО маєте зробити самі (вимоги курсу)
1. **Таксономія з ЛР5** — тут використано навчальну (6 класів / 20 підкласів). Замініть `TAXONOMY` у `etl/generate_data.py` на власну з ЛР5 (IRI, назви) і перезапустіть `./run_all.sh`; перегляньте тексти в `docs/`, де згадуються конкретні класи.
2. **Протокол «LLM-експерт»:** заповніть `llm_log/` справжніми даними (модель, версія, параметри, ваші підказки, рішення) та актуалізуйте `claims/claims.csv` (статуси `pending` перевірте самі). Без цього результат отримує максимум 0.25 бала.
3. **Декларація ШІ** у звіті (`docs/report_template.md`, розділ 0) і оформлення звіту за шаблоном кафедри.
4. **Розумійте весь код** — на захисті потрібно пояснити будь-яку частину і змінити запит/код «наживо» (наприклад: додати метрику в `metrics.yml`, новий фільтр у `RuleBasedBackend`, інший запит ROLLUP).
5. Результати text-to-SQL у `docs/t2sql_report_rule.md` — для baseline без LLM; для LLM-режиму запустіть оцінювання самостійно й проаналізуйте **свої** 3 помилки (приклад аналізу — `docs/t2sql_error_analysis.md`).
6. Коміти в гілку `lab12` репозиторію Hub; дані синтетичні — не видавайте їх за реальні.

## Відповіді на контрольні питання (шпаргалка для захисту)
1. *Зерно* — що означає один рядок факту; визначається першим, бо від нього залежать виміри, міри та коректність агрегації. Тут: одна згадка теми в одному відгуку.
2. *Таксономія як вимір* — `dim_topic` (IRI підкласу й класу, рівні клас → підклас) дає drill-down/roll-up (запити 10a/10b).
3. *ROLLUP/pivot* — запит 01 (підсумки підрозділів і загальний) і 06 (квартали як стовпці).
4. *Семантичний шар* — єдині визначення метрик → однакові результати всюди, менше помилок text-to-SQL, видно власника.
5. *Ризики text-to-SQL* — небезпечний SQL, тихі семантичні помилки, ресурсні атаки, галюцинації, приватність; зменшення — AST-guard, read-only, LIMIT, тайм-аут, семантичний шар, еталонні відповіді (`docs/risks.md`).
