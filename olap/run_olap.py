"""
Виконує всі sql/olap/*.sql, формує docs/olap_results.md (питання, запит, результат, інтерпретація)
і підтверджує 2 результати НЕЗАЛЕЖНО в pandas (за Parquet, без SQL).
Запуск:  python olap/run_olap.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from common import ROOT, connect, parquet

SHOW_ROWS = 25


def hdr(sql: str, key: str) -> str:
    for line in sql.splitlines():
        if line.startswith(f"-- {key}:"):
            return line.split(":", 1)[1].strip()
    return ""


# ---------------- Інтерпретації: рахуються з результату, а не пишуться «з голови» ----------------
def i01(df):
    d = df[df.grouping_level == 0]; tot = df[df.grouping_level == 3].iloc[0]
    hi, lo = d.loc[d.negative_pct.idxmax()], d.loc[d.negative_pct.idxmin()]
    return (f"Усього {int(tot.mentions)} згадок, з них {tot.negative_pct}% негативні. Найбільша частка негативу — "
            f"{hi.department_name} ({hi.division_name}): {hi.negative_pct}%; найменша — {lo.department_name}: {lo.negative_pct}%. "
            f"Рядки з grouping_level=1 — підсумки підрозділів, =3 — загальний підсумок.")

def i02(df):
    d = df[(df.grouping_level == 0) & (df.mentions >= 20)]; hi = d.loc[d.negative_pct.idxmax()]
    return (f"Серед комбінацій «клас × канал» (≥20 згадок) найвища частка негативу: {hi.class_label} / {hi.channel_name} — "
            f"{hi.negative_pct}% ({int(hi.mentions)} згадок). CUBE дає всі підсумки: по класу (channel=NULL), по каналу (class=NULL), загальний.")

def i03(df):
    t = df[df.class_label.isna() & df.year.notna()].set_index("year")
    a, b = t.loc[2025, "negative_pct"], t.loc[2026, "negative_pct"]
    c = df[df.class_label.notna()].pivot(index="class_label", columns="year", values="negative_pct")
    c["delta"] = c[2026] - c[2025]; w = c.delta.idxmax()
    return (f"Загальна частка негативу: 2025 — {a}%, 2026 — {b}% (Δ {b - a:+.1f} п.п.). Найбільше зростання у класі «{w}» "
            f"({c.loc[w, 2025]}% → {c.loc[w, 2026]}%, Δ {c.loc[w, 'delta']:+.1f} п.п.).")

def i04(df):
    h = df.iloc[0]; l = df.iloc[-1]
    return (f"У 2026 році найбільше негативу у класі «{h.class_label}» ({h.negative_pct}%, тональність {h.avg_sentiment}); "
            f"найменше — «{l.class_label}» ({l.negative_pct}%).")

def i05(df):
    h = df.loc[df.negative_pct.idxmax()]
    return (f"У підкубі найгірша комбінація: {h.department_name} / {h.class_label} / {int(h.year)} — {h.negative_pct}% негативу "
            f"(згадок: {int(h.mentions)}, тональність {h.avg_sentiment}).")

def i06(df):
    q = [c for c in df.columns if c != "class_label"]; first, last = q[0], q[-1]
    d = (df.set_index("class_label")[last] - df.set_index("class_label")[first]); w = d.idxmax()
    return (f"Від {first} до {last} найбільше змінилась частка негативу у класі «{w}» ({d[w]:+.1f} п.п.). "
            f"Pivot перетворює квартали з рядків на стовпці, що зручно для порівняння динаміки класів.")

def i07(df):
    m = df.loc[df.critical_mentions.idxmax()]; last = df.iloc[-1]
    return (f"За весь період накопичено критичних згадок: {int(last.cumulative_critical)}; пік — {m.month_label} "
            f"({int(m.critical_mentions)}). Накопичувальна сума показує темп наростання ризиків безпеки.")

def i08(df):
    h = df.iloc[0]; r = df.groupby("class_label").first()
    return (f"Найвищий ранг (1 у загальному списку): «{h.topic_label}» ({h.class_label}) — {h.negative_pct}% негативу. "
            f"RANK з PARTITION BY дає лідера всередині кожного класу (rank_in_class=1) окремо від загального рейтингу.")

def i09(df):
    f, l = df.iloc[0], df.iloc[-1]; mn = df.loc[df.moving_avg_3m.idxmin()]
    return (f"Ковзне середнє тональності тем очікування: {f.moving_avg_3m} ({f.month_label}) → {l.moving_avg_3m} ({l.month_label}); "
            f"мінімум {mn.moving_avg_3m} у {mn.month_label}. Згладжування прибирає місячний шум і показує тренд.")

def i10a(df):
    h = df.iloc[0]
    return f"На рівні класів найбільший негатив у «{h.class_label}» ({h.negative_pct}%, {int(h.mentions)} згадок). Далі виконуємо drill-down у його підкласи (10b)."

def i10b(df):
    h = df.iloc[0]
    return (f"Drill-down у клас «{h.class_label}»: найбільше негативу в підкласі «{h.topic_label}» ({h.negative_pct}%). "
            f"Саме цей підклас визначає проблему класу — тут слід шукати причини.")

def i11(df):
    h = df.iloc[0]
    return (f"Найсильніший зв'язок: «{h.topic_a}» + «{h.topic_b}» (разом у {int(h.together)} відгуках, lift={h.lift}). "
            f"lift>1 означає, що теми згадуються разом частіше за випадкове; такі пари стали ребрами fb:coOccursWith у topic_relation.")

def i12(df):
    d = df.set_index("risk_group")
    return (f"Частка негативу за групами ризику: " + ", ".join(f"{k} — {v}%" for k, v in d.negative_pct.items()) +
            ". Завдяки SCD2 відгук відноситься до групи ризику, актуальної на дату відгуку (а не поточної).")


INTERP = {"01": i01, "02": i02, "03": i03, "04": i04, "05": i05, "06": i06, "07": i07,
          "08": i08, "09": i09, "10a": i10a, "10b": i10b, "11": i11, "12": i12}


# ---------------- Незалежна перевірка у pandas ----------------
def pandas_checks(con) -> list[dict]:
    f = parquet("fact_feedback_mention"); dep = parquet("dim_department"); top = parquet("dim_topic"); dt = parquet("dim_date")
    out = []
    # V1: negative_pct по відділеннях (запит 01)
    m = f.merge(dep, on="department_key")
    pdv = m.groupby("department_name").agg(mentions=("mention_key", "size"), neg=("is_negative", "mean"))
    pdv["negative_pct"] = (pdv.neg * 100).round(1)
    sql = con.execute(open(ROOT / "sql/olap/01_rollup_division_department.sql", encoding="utf-8").read()).fetchdf()
    sql = sql[sql.grouping_level == 0].set_index("department_name")
    j = sql.join(pdv, rsuffix="_pd")
    ok = bool((j.mentions == j.mentions_pd).all() and np.allclose(j.negative_pct, j.negative_pct_pd, atol=0.051))
    out.append({"query": "01 ROLLUP (відділення)", "ok": ok, "max_abs_diff": float((j.negative_pct - j.negative_pct_pd).abs().max()),
                "n": len(j)})
    # V2: pivot клас × квартал (запит 06)
    m = f.merge(top[["topic_key", "class_label"]], on="topic_key").merge(dt[["date_key", "quarter_label"]], on="date_key")
    pv = (m.pivot_table(index="class_label", columns="quarter_label", values="is_negative", aggfunc="mean") * 100).round(1)
    sql = con.execute(open(ROOT / "sql/olap/06_pivot_class_quarter.sql", encoding="utf-8").read()).fetchdf().set_index("class_label")
    sql = sql[pv.columns]
    diff = (sql.astype(float) - pv.astype(float)).abs()
    ok = bool(np.nanmax(diff.values) <= 0.051)
    out.append({"query": "06 PIVOT (клас × квартал)", "ok": ok, "max_abs_diff": float(np.nanmax(diff.values)), "n": int(diff.size)})
    return out


def main() -> int:
    con = connect(True)
    md = ["# Результати OLAP-запитів", "",
          "Усі запити — у `sql/olap/*.sql`; значення нижче отримані запуском `python olap/run_olap.py` "
          "на синтетичних даних (див. `data/VERSION.json`). Інтерпретації формуються з самих результатів. "
          f"Таблиці скорочено до перших {SHOW_ROWS} рядків.", ""]
    n_ok = 0
    for p in sorted((ROOT / "sql/olap").glob("*.sql")):
        sql = p.read_text(encoding="utf-8")
        df = con.execute(sql).fetchdf()
        key = p.stem.split("_")[0]
        md += [f"## {p.stem}", "", f"**Бізнес-питання:** {hdr(sql, 'question')}", "",
               f"**Конструкція:** {hdr(sql, 'construct')}", "", "```sql", sql.strip(), "```", "",
               "**Результат:**", "", df.head(SHOW_ROWS).to_markdown(index=False, floatfmt="g"), "",
               f"**Інтерпретація:** {INTERP[key](df)}", ""]
        n_ok += 1
    checks = pandas_checks(con)
    md += ["## Незалежне підтвердження результатів (pandas)", "",
           "Два результати перераховано у pandas безпосередньо з Parquet (без SQL):", "",
           "| Запит | Збіг | Макс. розбіжність | Порівняно значень |", "|---|---|---:|---:|"]
    for c in checks:
        md.append(f"| {c['query']} | {'✅' if c['ok'] else '❌'} | {c['max_abs_diff']:.3f} | {c['n']} |")
    (ROOT / "docs" / "olap_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Виконано запитів: {n_ok}; pandas-перевірки: {[c['ok'] for c in checks]}")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
