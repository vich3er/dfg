-- question: Як змінюється частка негативу (%) по класах тем від кварталу до кварталу?
-- construct: PIVOT
SELECT * FROM (
    PIVOT (
        SELECT t.class_label, dd.quarter_label, f.is_negative AS neg
        FROM fact_feedback_mention f
        JOIN dim_topic t ON t.topic_key = f.topic_key
        JOIN dim_date dd ON dd.date_key = f.date_key
    )
    ON quarter_label
    USING ROUND(100.0 * AVG(neg), 1)
    GROUP BY class_label
)
ORDER BY class_label;
