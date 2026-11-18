-- question: Як змінилася частка негативу між 2025 і 2026 роками загалом і по класах тем?
-- construct: GROUPING SETS
SELECT
    t.class_label,
    dd.year,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct
FROM fact_feedback_mention f
JOIN dim_topic t ON t.topic_key = f.topic_key
JOIN dim_date dd ON dd.date_key = f.date_key
GROUP BY GROUPING SETS ((t.class_label, dd.year), (dd.year), ())
ORDER BY dd.year NULLS LAST, t.class_label NULLS FIRST;
