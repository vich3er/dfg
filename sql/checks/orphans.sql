-- Перевірка «сиріт»: кожен FK факту має існувати у виміру. Очікування: orphans = 0 у всіх рядках.
SELECT 'date_key' AS fk, COUNT(*) AS orphans FROM fact_feedback_mention f LEFT JOIN dim_date x ON x.date_key = f.date_key WHERE x.date_key IS NULL
UNION ALL
SELECT 'department_key', COUNT(*) FROM fact_feedback_mention f LEFT JOIN dim_department x ON x.department_key = f.department_key WHERE x.department_key IS NULL
UNION ALL
SELECT 'patient_key', COUNT(*) FROM fact_feedback_mention f LEFT JOIN dim_patient x ON x.patient_key = f.patient_key WHERE x.patient_key IS NULL
UNION ALL
SELECT 'topic_key', COUNT(*) FROM fact_feedback_mention f LEFT JOIN dim_topic x ON x.topic_key = f.topic_key WHERE x.topic_key IS NULL
UNION ALL
SELECT 'channel_key', COUNT(*) FROM fact_feedback_mention f LEFT JOIN dim_channel x ON x.channel_key = f.channel_key WHERE x.channel_key IS NULL
UNION ALL
SELECT 'feedback_id', COUNT(*) FROM fact_feedback_mention f LEFT JOIN dim_feedback x ON x.feedback_id = f.feedback_id WHERE x.feedback_id IS NULL;
