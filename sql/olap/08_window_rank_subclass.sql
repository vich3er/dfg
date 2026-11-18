-- question: Які підкласи тем найпроблемніші всередині свого класу та загалом (ранг за часткою негативу)?
-- construct: ВІКОННА ФУНКЦІЯ (RANK, PARTITION BY)
WITH s AS (
    SELECT t.class_label, t.topic_label, COUNT(*) AS mentions,
           ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct
    FROM fact_feedback_mention f
    JOIN dim_topic t ON t.topic_key = f.topic_key
    GROUP BY t.class_label, t.topic_label
    HAVING COUNT(*) >= 30
)
SELECT
    class_label, topic_label, mentions, negative_pct,
    RANK() OVER (PARTITION BY class_label ORDER BY negative_pct DESC) AS rank_in_class,
    RANK() OVER (ORDER BY negative_pct DESC) AS rank_overall
FROM s
ORDER BY rank_overall;
