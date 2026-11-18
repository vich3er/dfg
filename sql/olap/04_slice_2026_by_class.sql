-- question: Які класи тем мають найбільшу частку негативу у 2026 році?
-- construct: SLICE (фіксація одного виміру: рік = 2026)
SELECT
    t.class_label,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment
FROM fact_feedback_mention f
JOIN dim_topic t ON t.topic_key = f.topic_key
JOIN dim_date dd ON dd.date_key = f.date_key
WHERE dd.year = 2026
GROUP BY t.class_label
ORDER BY negative_pct DESC;
