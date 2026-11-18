"""
Перевірка узгодженості: те саме питання різними шляхами дає однаковий результат.
  Шлях A — SQL, згенерований семантичним шаром (metric_sql);
  Шлях B — «ручний» SQL (як в OLAP-запитах);
  Шлях C — pandas по Parquet.
Запуск: python semantic/check_consistency.py   -> docs/consistency_report.md
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from common import ROOT, connect, parquet
from semantic.semantic import metric_sql


def same(a: pd.DataFrame, b: pd.DataFrame, tol=0.051) -> bool:
    a = a.reset_index(drop=True); b = b.reset_index(drop=True)
    if a.shape != b.shape:
        return False
    for ca, cb in zip(a.columns, b.columns):
        x, y = a[ca], b[cb]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            if not np.allclose(x.astype(float), y.astype(float), atol=tol, equal_nan=True):
                return False
        elif not (x.astype(str) == y.astype(str)).all():
            return False
    return True


def main() -> int:
    con = connect(True)
    f = parquet("fact_feedback_mention"); dep = parquet("dim_department"); top = parquet("dim_topic"); dt = parquet("dim_date")
    cases = []

    # Питання 1: частка негативу по відділеннях
    a = con.execute(metric_sql("negative_share", ["department"])).fetchdf()
    b = con.execute("""SELECT d.department_name, ROUND(100.0*SUM(f.is_negative)/COUNT(*),1) AS v
                       FROM fact_feedback_mention f JOIN dim_department d ON d.department_key=f.department_key
                       GROUP BY 1 ORDER BY 1""").fetchdf()
    m = f.merge(dep, on="department_key").groupby("department_name").is_negative.mean().mul(100).round(1).reset_index().sort_values("department_name")
    cases.append(("Частка негативних згадок по відділеннях", a, b, m))

    # Питання 2: середня тональність по класах у 2026 році
    a = con.execute(metric_sql("avg_sentiment", ["topic_class"], {"year": 2026})).fetchdf()
    b = con.execute("""SELECT t.class_label, ROUND(AVG(f.sentiment_score),3)
                       FROM fact_feedback_mention f JOIN dim_topic t ON t.topic_key=f.topic_key JOIN dim_date dd ON dd.date_key=f.date_key
                       WHERE dd.year=2026 GROUP BY 1 ORDER BY 1""").fetchdf()
    m = (f.merge(top, on="topic_key").merge(dt, on="date_key").query("year == 2026")
          .groupby("class_label").sentiment_score.mean().round(3).reset_index().sort_values("class_label"))
    cases.append(("Середня тональність по класах у 2026 р.", a, b, m))

    # Питання 3: середній час очікування по кварталах
    a = con.execute(metric_sql("avg_wait_minutes", ["quarter"])).fetchdf()
    b = con.execute("""SELECT dd.quarter_label, ROUND(AVG(f.wait_minutes),1)
                       FROM fact_feedback_mention f JOIN dim_date dd ON dd.date_key=f.date_key GROUP BY 1 ORDER BY 1""").fetchdf()
    m = f.merge(dt, on="date_key").groupby("quarter_label").wait_minutes.apply(lambda s: s.astype(float).mean()).round(1).reset_index().sort_values("quarter_label")
    cases.append(("Середній час очікування по кварталах", a, b, m))

    # Питання 4: кількість відгуків і згадок загалом
    a = con.execute(metric_sql(["mentions", "feedback_count"])).fetchdf()
    b = con.execute("SELECT COUNT(*), COUNT(DISTINCT feedback_id) FROM fact_feedback_mention").fetchdf()
    m = pd.DataFrame({"a": [len(f)], "b": [f.feedback_id.nunique()]})
    cases.append(("Загальна кількість згадок і відгуків", a, b, m))

    lines = ["# Перевірка узгодженості семантичного шару", "",
             "Кожне питання обчислено трьома шляхами: **A** — SQL із семантичного шару, **B** — ручний SQL, **C** — pandas.", "",
             "| Питання | A = B | A = C | Рядків |", "|---|---|---|---:|"]
    ok_all = True
    for name, a, b, c in cases:
        ab, ac = same(a, b), same(a, c)
        ok_all &= ab and ac
        lines.append(f"| {name} | {'✅' if ab else '❌'} | {'✅' if ac else '❌'} | {len(a)} |")
    lines += ["", "Приклад SQL, згенерованого семантичним шляхом:", "", "```sql",
              metric_sql("negative_share", ["department"], {"year": 2026}, [("negative_share", "DESC")], 3), "```", ""]
    (ROOT / "docs" / "consistency_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("Усі питання узгоджені" if ok_all else "Є РОЗБІЖНОСТІ — див. docs/consistency_report.md")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
