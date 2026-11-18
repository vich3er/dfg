-- question: Яка частка негативних згадок на рівні підрозділів і відділень (з проміжними підсумками та загальним підсумком)?
-- construct: ROLLUP
SELECT
    d.division_name,
    d.department_name,
    GROUPING(d.division_name, d.department_name) AS grouping_level,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct,
    ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment
FROM fact_feedback_mention f
JOIN dim_department d ON d.department_key = f.department_key
GROUP BY ROLLUP (d.division_name, d.department_name)
ORDER BY d.division_name NULLS LAST, d.department_name NULLS LAST;
