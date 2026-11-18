"""Малює діаграму зірки: docs/star_schema.png"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from common import ROOT

fig, ax = plt.subplots(figsize=(14, 9)); ax.set_xlim(0, 14); ax.set_ylim(0, 9); ax.axis("off")

def box(x, y, w, h, title, lines, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc=color, ec="#333", lw=1.4, zorder=3))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="center", fontsize=10.5, fontweight="bold", zorder=4)
    ax.text(x + 0.15, y + h - 0.6, "\n".join(lines), ha="left", va="top", fontsize=8.2, family="DejaVu Sans Mono", zorder=4)
    return (x + w / 2, y + h / 2)

c = box(5, 3.2, 4, 3.4, "fact_feedback_mention", [
    "PK mention_key", "FK feedback_id, date_key", "FK department_key, patient_key", "FK topic_key, channel_key",
    "— міри —", "mention_count     (адит.)", "is_negative       (адит.)", "is_critical       (адит.)",
    "sentiment_score   (неадит.)", "overall_rating    (неадит.)", "wait_minutes      (неадит.)"], "#ffe9a8")
dims = [
    (0.3, 6.6, 3.8, 2.0, "dim_date", ["PK date_key", "full_date, year", "quarter, quarter_label", "month, month_label", "week, is_weekend"], "#cfe8ff"),
    (5.0, 7.3, 4.0, 1.5, "dim_topic  ★ ТАКСОНОМІЯ", ["PK topic_key", "topic_iri (IRI), topic_label", "class_iri, class_label", "level (клас→підклас)"], "#c9f2c7"),
    (10.0, 6.6, 3.7, 2.0, "dim_department", ["PK department_key", "department_name", "division_name", "(SCD1; ієрархія)"], "#cfe8ff"),
    (0.3, 3.4, 3.8, 2.0, "dim_patient  (SCD2)", ["PK patient_key", "patient_id (псевдонім)", "age_group, sex", "risk_group", "valid_from/valid_to, is_current"], "#cfe8ff"),
    (10.0, 3.4, 3.7, 1.5, "dim_channel", ["PK channel_key", "channel_name", "channel_type"], "#cfe8ff"),
    (0.3, 0.4, 3.8, 1.4, "dim_feedback (вироджений)", ["PK feedback_id", "feedback_text, language"], "#e6e6e6"),
    (5.0, 0.4, 4.0, 1.5, "topic_relation (семант. мережа)", ["subject_iri, predicate, object_iri", "weight (lift), support"], "#f6d5f0"),
]
for d in dims:
    p = box(*d[:4], d[4], d[5], d[6])
    ax.annotate("", xy=c, xytext=p, arrowprops=dict(arrowstyle="-", lw=1.2, color="#555"), zorder=1)
ax.annotate("", xy=(7, 1.9), xytext=(7, 3.2), arrowprops=dict(arrowstyle="<->", lw=1, ls="--", color="#a0a"), zorder=1)
ax.text(7.1, 2.55, "IRI", fontsize=8, color="#a0a")
ax.set_title("Зіркова схема «Відгуки пацієнтів»: зерно = одна згадка однієї теми в одному відгуку", fontsize=12)
fig.savefig(ROOT / "docs" / "star_schema.png", dpi=130, bbox_inches="tight"); print("docs/star_schema.png")
