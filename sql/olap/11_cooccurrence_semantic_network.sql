-- question: Які теми найчастіше згадуються разом в одному відгуку (ребра семантичної мережі) і наскільки це вище за випадкове (lift)?
-- construct: SELF-JOIN факту по відгуку + lift (основа для fb:coOccursWith)
WITH n AS (SELECT COUNT(DISTINCT feedback_id) AS N FROM fact_feedback_mention),
tc AS (SELECT topic_key, COUNT(DISTINCT feedback_id) AS c FROM fact_feedback_mention GROUP BY 1),
p AS (
    SELECT a.topic_key AS ta, b.topic_key AS tb, COUNT(*) AS together
    FROM fact_feedback_mention a
    JOIN fact_feedback_mention b ON a.feedback_id = b.feedback_id AND a.topic_key < b.topic_key
    GROUP BY 1, 2
)
SELECT
    da.topic_label AS topic_a,
    db.topic_label AS topic_b,
    p.together,
    ROUND((p.together * 1.0 * n.N) / (ca.c * cb.c), 2) AS lift
FROM p CROSS JOIN n
JOIN tc ca ON ca.topic_key = p.ta
JOIN tc cb ON cb.topic_key = p.tb
JOIN dim_topic da ON da.topic_key = p.ta
JOIN dim_topic db ON db.topic_key = p.tb
WHERE p.together >= 15
ORDER BY lift DESC
LIMIT 10;
