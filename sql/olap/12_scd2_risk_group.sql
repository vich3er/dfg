-- question: Чи відрізняється тональність відгуків пацієнтів різних груп ризику (група береться на дату відгуку — SCD тип 2)?
-- construct: JOIN до SCD2-виміру
SELECT
    p.risk_group,
    COUNT(*) AS mentions,
    COUNT(DISTINCT f.feedback_id) AS feedbacks,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment
FROM fact_feedback_mention f
JOIN dim_patient p ON p.patient_key = f.patient_key
GROUP BY p.risk_group
ORDER BY CASE p.risk_group WHEN 'низький' THEN 1 WHEN 'середній' THEN 2 ELSE 3 END;
