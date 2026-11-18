"""Перевірки якості даних (≥5). Кожна — SQL, що повертає кількість порушень (очікується 0)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

F = "fact_feedback_mention"
CHECKS = [
    ("Q01", "Унікальність mention_key", f"SELECT COUNT(*) - COUNT(DISTINCT mention_key) FROM {F}"),
    ("Q02", "Унікальність пари (feedback_id, topic_key)", f"SELECT COUNT(*) - COUNT(DISTINCT (feedback_id, topic_key)) FROM {F}"),
    ("Q03", "NOT NULL для ключів і обов'язкових мір",
     f"SELECT COUNT(*) FROM {F} WHERE feedback_id IS NULL OR date_key IS NULL OR department_key IS NULL OR patient_key IS NULL OR topic_key IS NULL OR channel_key IS NULL OR sentiment_score IS NULL OR overall_rating IS NULL"),
    ("Q04", "Діапазон sentiment_score ∈ [-1; 1]", f"SELECT COUNT(*) FROM {F} WHERE sentiment_score < -1 OR sentiment_score > 1"),
    ("Q05", "Діапазон overall_rating ∈ [1; 5]", f"SELECT COUNT(*) FROM {F} WHERE overall_rating < 1 OR overall_rating > 5"),
    ("Q06", "wait_minutes ∈ [0; 1440] або NULL", f"SELECT COUNT(*) FROM {F} WHERE wait_minutes < 0 OR wait_minutes > 1440"),
    ("Q07", "Узгодженість is_negative з sentiment_score (< -0.2)",
     f"SELECT COUNT(*) FROM {F} WHERE is_negative <> CASE WHEN sentiment_score < -0.2 THEN 1 ELSE 0 END"),
    ("Q08", "is_critical ⇒ is_negative", f"SELECT COUNT(*) FROM {F} WHERE is_critical = 1 AND is_negative = 0"),
    ("Q09", "Дати факту у межах періоду 2025-01-01..2026-09-30",
     f"SELECT COUNT(*) FROM {F} f JOIN dim_date d USING (date_key) WHERE d.full_date < DATE '2025-01-01' OR d.full_date > DATE '2026-09-30'"),
    ("Q10", "SCD2: версія пацієнта діє на дату відгуку",
     f"SELECT COUNT(*) FROM {F} f JOIN dim_patient p USING (patient_key) JOIN dim_date d USING (date_key) WHERE d.full_date < p.valid_from OR d.full_date > p.valid_to"),
    ("Q11", "SCD2: у кожного patient_id рівно одна поточна версія",
     "SELECT COUNT(*) FROM (SELECT patient_id, SUM(CASE WHEN is_current THEN 1 ELSE 0 END) AS c FROM dim_patient GROUP BY 1) WHERE c <> 1"),
    ("Q12", "Критичні/негативні: wait_minutes заповнено лише для тем очікування",
     f"SELECT COUNT(*) FROM {F} f JOIN dim_topic t USING (topic_key) WHERE f.wait_minutes IS NOT NULL AND t.class_code <> 'WaitingOrganization'"),
]


def run_checks(con, orphans_sql: str, min_rows: int = 1000) -> list[dict]:
    res = []
    n = con.execute(f"SELECT COUNT(*) FROM {F}").fetchone()[0]
    res.append({"id": "Q00", "name": f"Кількість рядків факту ≥ {min_rows}", "violations": 0 if n >= min_rows else 1, "detail": f"rows={n}"})
    for cid, name, sql in CHECKS:
        v = int(con.execute(sql).fetchone()[0])
        res.append({"id": cid, "name": name, "violations": v, "detail": ""})
    orph = con.execute(orphans_sql).fetchall()
    total = sum(r[1] for r in orph)
    res.append({"id": "Q13", "name": "Немає «сиріт» (sql/checks/orphans.sql)", "violations": int(total),
                "detail": ", ".join(f"{a}={b}" for a, b in orph)})
    for r in res:
        r["passed"] = r["violations"] == 0
    return res


def save_report(results: list[dict], json_path: Path, md_path: Path) -> None:
    passed = sum(r["passed"] for r in results)
    json_path.write_text(json.dumps({"created_at": datetime.now().isoformat(timespec="seconds"),
                                     "passed": passed, "total": len(results), "checks": results},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Звіт якості даних", "", f"Пройдено: **{passed}/{len(results)}**", "",
             "| ID | Перевірка | Порушень | Статус | Деталі |", "|---|---|---:|---|---|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['name']} | {r['violations']} | {'✅' if r['passed'] else '❌'} | {r['detail']} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
