-- question: Як розподіляються згадки та частка негативу за класами таксономії і каналами збору (усі комбінації підсумків)?
-- construct: CUBE
SELECT
    t.class_label,
    c.channel_name,
    GROUPING(t.class_label, c.channel_name) AS grouping_level,
    COUNT(*) AS mentions,
    ROUND(100.0 * SUM(f.is_negative) / COUNT(*), 1) AS negative_pct
FROM fact_feedback_mention f
JOIN dim_topic t   ON t.topic_key = f.topic_key
JOIN dim_channel c ON c.channel_key = f.channel_key
GROUP BY CUBE (t.class_label, c.channel_name)
ORDER BY grouping_level, t.class_label, c.channel_name;
