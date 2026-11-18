"""
Аналітична панель (plotly -> один HTML). 5 питань, 5 візуалізацій; інтерпретації рахуються з даних.
Запуск: python dashboard/build_dashboard.py   -> dashboard/dashboard.html
"""
from __future__ import annotations
import html, json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from common import ROOT, connect, DATA_DIR

con = connect(True)
ver = json.loads((DATA_DIR / "VERSION.json").read_text(encoding="utf-8"))
panels = []  # (питання, figure, інтерпретація)

# ---- Q1: тренд негативу по класах
d1 = con.execute("""
    SELECT t.class_label, dd.quarter_label, ROUND(100.0*SUM(f.is_negative)/COUNT(*),1) AS negative_pct
    FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key) JOIN dim_date dd USING (date_key)
    GROUP BY 1,2 ORDER BY 2,1""").fetchdf()
fig1 = px.line(d1, x="quarter_label", y="negative_pct", color="class_label", markers=True,
               labels={"quarter_label": "Квартал", "negative_pct": "Негатив, %", "class_label": "Клас"})
pv = d1.pivot(index="class_label", columns="quarter_label", values="negative_pct")
chg = (pv.iloc[:, -1] - pv.iloc[:, 0]).sort_values(ascending=False)
panels.append(("Як змінюється частка негативних згадок за кварталами по класах таксономії?", fig1,
               f"Найбільше зростання негативу — у класі «{chg.index[0]}» ({chg.iloc[0]:+.1f} п.п. від {pv.columns[0]} до {pv.columns[-1]}). "
               f"Найстабільніший (або з найбільшим зниженням) — «{chg.index[-1]}» ({chg.iloc[-1]:+.1f} п.п.). "
               f"Висновок: зміни концентруються в одному-двох класах, тому дії варто спрямовувати саме туди."))

# ---- Q2: проблемні підкласи
d2 = con.execute("""
    SELECT t.topic_label, t.class_label, COUNT(*) AS mentions, ROUND(100.0*SUM(f.is_negative)/COUNT(*),1) AS negative_pct
    FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key)
    GROUP BY 1,2 HAVING COUNT(*)>=30 ORDER BY negative_pct DESC LIMIT 10""").fetchdf()
fig2 = px.bar(d2.sort_values("negative_pct"), x="negative_pct", y="topic_label", color="class_label", orientation="h",
              hover_data=["mentions"], labels={"negative_pct": "Негатив, %", "topic_label": "Підклас", "class_label": "Клас"})
panels.append(("Які підкласи тем (листки таксономії) найпроблемніші?", fig2,
               f"Лідер за часткою негативу — «{d2.iloc[0].topic_label}» ({d2.iloc[0].negative_pct}%, {int(d2.iloc[0].mentions)} згадок), "
               f"далі «{d2.iloc[1].topic_label}» ({d2.iloc[1].negative_pct}%). У топ-10 присутні класи: "
               f"{', '.join(sorted(d2.class_label.unique()))}."))

# ---- Q3: теплова карта відділення × клас
d3 = con.execute("""
    SELECT dep.department_name, t.class_label, ROUND(AVG(f.sentiment_score),3) AS avg_sentiment, COUNT(*) AS mentions
    FROM fact_feedback_mention f JOIN dim_department dep USING (department_key) JOIN dim_topic t USING (topic_key)
    GROUP BY 1,2""").fetchdf()
heat = d3.pivot(index="department_name", columns="class_label", values="avg_sentiment")
fig3 = px.imshow(heat, color_continuous_scale="RdYlGn", zmin=-0.6, zmax=0.6, aspect="auto",
                 labels={"color": "Тональність"}, text_auto=".2f")
worst = d3[d3.mentions >= 15].sort_values("avg_sentiment").iloc[0]
best = d3[d3.mentions >= 15].sort_values("avg_sentiment").iloc[-1]
panels.append(("У яких відділеннях і за якими класами тональність найнижча?", fig3,
               f"Найнижча тональність (≥15 згадок): {worst.department_name} × «{worst.class_label}» = {worst.avg_sentiment}; "
               f"найвища: {best.department_name} × «{best.class_label}» = {best.avg_sentiment}. Червоні клітинки — пріоритет для втручання."))

# ---- Q4: час очікування по місяцях
d4 = con.execute("""
    SELECT dd.month_label, t.topic_label, ROUND(AVG(f.wait_minutes),1) AS avg_wait, COUNT(*) AS n
    FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key) JOIN dim_date dd USING (date_key)
    WHERE t.topic_code IN ('EmergencyWait','AppointmentScheduling') GROUP BY 1,2 ORDER BY 1""").fetchdf()
fig4 = px.line(d4, x="month_label", y="avg_wait", color="topic_label", markers=True,
               labels={"month_label": "Місяць", "avg_wait": "Сер. очікування, хв", "topic_label": "Підклас"})
b = con.execute("""
    SELECT t.topic_label,
      ROUND(AVG(CASE WHEN dd.full_date < DATE '2026-03-01' THEN f.wait_minutes END),1) AS before_,
      ROUND(AVG(CASE WHEN dd.full_date >= DATE '2026-03-01' THEN f.wait_minutes END),1) AS after_
    FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key) JOIN dim_date dd USING (date_key)
    WHERE t.topic_code IN ('EmergencyWait','AppointmentScheduling') GROUP BY 1""").fetchdf()
txt = "; ".join(f"«{r.topic_label}»: {r.before_} → {r.after_} хв" for r in b.itertuples())
panels.append(("Чи погіршився час очікування (до і після 1 березня 2026)?", fig4,
               f"Середній час очікування до та після 01.03.2026 — {txt}. Стрибок у 2026 р. узгоджується зі зростанням негативу у класі очікування (панель 1)."))

# ---- Q5: семантична мережа тем
nodes = con.execute("SELECT topic_iri, topic_label, class_label FROM dim_topic ORDER BY topic_key").fetchdf()
edges = con.execute("SELECT subject_iri, object_iri, weight, support FROM topic_relation WHERE predicate='fb:coOccursWith'").fetchdf()
n = len(nodes); pos = {r.topic_iri: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i, r in enumerate(nodes.itertuples())}
fig5 = go.Figure()
for e in edges.itertuples():
    (x0, y0), (x1, y1) = pos[e.subject_iri], pos[e.object_iri]
    fig5.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", hoverinfo="text", showlegend=False,
                              text=f"lift={e.weight}, спільних відгуків={e.support}",
                              line=dict(width=min(1 + e.weight * 0.6, 6), color="rgba(120,120,120,0.55)")))
palette = px.colors.qualitative.Set2; classes = list(nodes.class_label.unique())
for c in classes:
    sub = nodes[nodes.class_label == c]
    fig5.add_trace(go.Scatter(x=[pos[i][0] for i in sub.topic_iri], y=[pos[i][1] for i in sub.topic_iri], mode="markers+text",
                              text=sub.topic_label, textposition="top center", name=c, marker=dict(size=16, color=palette[classes.index(c) % 8]),
                              hovertext=sub.topic_iri))
fig5.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), height=620)
top = edges.sort_values("weight", ascending=False).iloc[0]
lab = dict(zip(nodes.topic_iri, nodes.topic_label))
panels.append(("Які теми зазвичай згадуються разом (семантична мережа fb:coOccursWith)?", fig5,
               f"У мережі {len(edges)} ребер (support ≥ 15, lift ≥ 1.5). Найсильніший зв'язок: «{lab[top.subject_iri]}» — «{lab[top.object_iri]}» "
               f"(lift {top.weight}, {int(top.support)} відгуків). Такі кластери підказують, що проблеми слід вирішувати комплексно."))

body = []
for i, (q, fig, interp) in enumerate(panels, 1):
    div = fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 1 else False)
    body.append(f"<section><h2>{i}. {html.escape(q)}</h2>{div}<p class='interp'><b>Інтерпретація.</b> {html.escape(interp)}</p></section>")
page = f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>Панель відгуків пацієнтів</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}}
section{{margin:32px 0;padding-bottom:16px;border-bottom:1px solid #ddd}} .interp{{background:#f4f7fb;padding:10px 14px;border-left:4px solid #3b82f6}}
.meta{{color:#666;font-size:14px}}</style></head><body>
<h1>Моніторинг стану пацієнтів: аналіз відгуків</h1>
<p class="meta">Синтетичні дані · версія даних {ver['data_version']} · seed {ver['seed']} · {ver['files']['fact_feedback_mention.parquet']['rows']} згадок у фактах</p>
{''.join(body)}</body></html>"""
(ROOT / "dashboard" / "dashboard.html").write_text(page, encoding="utf-8")
print("dashboard/dashboard.html створено;", len(panels), "візуалізацій")
for q, _, t in panels:
    print("-", t[:230])
