-- question: Яка динаміка тональності за темами очікування (ковзне середнє за 3 місяці)?
-- construct: ВІКОННА ФУНКЦІЯ (ковзне середнє, ROWS BETWEEN)
WITH m AS (
    SELECT dd.month_label, ROUND(AVG(f.sentiment_score), 3) AS avg_sentiment, COUNT(*) AS mentions
    FROM fact_feedback_mention f
    JOIN dim_topic t ON t.topic_key = f.topic_key
    JOIN dim_date dd ON dd.date_key = f.date_key
    WHERE t.class_code = 'WaitingOrganization'
    GROUP BY dd.month_label
)
SELECT
    month_label, mentions, avg_sentiment,
    ROUND(AVG(avg_sentiment) OVER (ORDER BY month_label ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 3) AS moving_avg_3m
FROM m
ORDER BY month_label;
