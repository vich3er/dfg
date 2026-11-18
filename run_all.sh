#!/usr/bin/env bash
# Повний запуск з нуля: python 3.10+, залежності з requirements.txt
set -euo pipefail
cd "$(dirname "$0")"
python etl/load.py --seed 42 --n-feedback 1500   # Результат 2: ELT, перевірки, Parquet
python docs/make_star_diagram.py                  # Результат 1: діаграма зірки
python olap/run_olap.py                           # Результат 3: OLAP + pandas-перевірка
python semantic/build_docs.py                     # Результат 4: документація метрик
python semantic/check_consistency.py              # Результат 4: узгодженість
python tests/test_guard.py                        # Результат 5: тести AST-захисту
python tests/run_t2sql_eval.py                    # Результат 5: оцінювання text-to-SQL (baseline)
python dashboard/build_dashboard.py               # Результат 5: панель
python claims/claims_stats.py                     # Протокол LLM-експерта: частка підтверджених
