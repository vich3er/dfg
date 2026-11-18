-- question: DRILL-DOWN, рівень 1 (клас): який клас таксономії має найбільшу частку негативу?
-- construct: DRILL-DOWN по ієрархії таксономії (клас)
SELECT
    t.class_iri,
    t.class_label,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment
FROM fact_feedback_mention f
JOIN dim_topic t ON t.topic_key = f.topic_key
GROUP BY t.class_iri, t.class_label
ORDER BY negative_pct DESC;
