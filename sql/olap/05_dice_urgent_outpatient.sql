-- question: Яка ситуація з очікуванням і моніторингом у невідкладній та амбулаторній службах за 2025–2026 роки?
-- construct: DICE (підкуб за кількома вимірами одночасно)
SELECT
    dep.department_name,
    t.class_label,
    dd.year,
    COUNT(*) AS mentions,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct
FROM fact_feedback_mention f
JOIN dim_department dep ON dep.department_key = f.department_key
JOIN dim_topic t        ON t.topic_key = f.topic_key
JOIN dim_date dd        ON dd.date_key = f.date_key
WHERE dep.division_name IN ('Невідкладна допомога', 'Амбулаторний')
  AND t.class_label IN ('Очікування й організація', 'Моніторинг стану')
  AND dd.year IN (2025, 2026)
GROUP BY dep.department_name, t.class_label, dd.year
ORDER BY dep.department_name, t.class_label, dd.year;
