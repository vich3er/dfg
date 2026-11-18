-- question: DRILL-DOWN, рівень 2 (підклас): які підкласи «найгіршого» класу дають найбільше негативу?
-- construct: DRILL-DOWN по ієрархії таксономії (клас -> підклас)
WITH worst AS (
    SELECT t.class_iri
    FROM fact_feedback_mention f
    JOIN dim_topic t ON t.topic_key = f.topic_key
    GROUP BY t.class_iri
    ORDER BY SUM(f.is_negative) * 1.0 / COUNT(*) DESC
    LIMIT 1
)
SELECT
    t.class_label,
    t.topic_iri,
    t.topic_label,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment
FROM fact_feedback_mention f
JOIN dim_topic t ON t.topic_key = f.topic_key
WHERE t.class_iri IN (SELECT class_iri FROM worst)
GROUP BY t.class_label, t.topic_iri, t.topic_label
ORDER BY negative_pct DESC;
