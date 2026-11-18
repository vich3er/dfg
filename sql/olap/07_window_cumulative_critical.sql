-- question: Як накопичуються критичні згадки (безпека пацієнта) з місяця в місяць?
-- construct: ВІКОННА ФУНКЦІЯ (накопичувальна сума)
WITH m AS (
    SELECT dd.month_label, SUM(f.is_critical) AS critical_mentions, COUNT(*) AS mentions
    FROM fact_feedback_mention f
    JOIN dim_date dd ON dd.date_key = f.date_key
    GROUP BY dd.month_label
)
SELECT
    month_label,
    critical_mentions,
    SUM(critical_mentions) OVER (ORDER BY month_label) AS cumulative_critical,
    ROUND(100.0 * critical_mentions / mentions, 2) AS critical_pct
FROM m
ORDER BY month_label;
