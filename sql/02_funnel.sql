-- Unique users in each stage. Experiment stages are not sequential product funnel steps.
SELECT 'registered' AS stage,count(*) AS users FROM users
UNION ALL
SELECT 'opened',count(DISTINCT user_id) FROM events WHERE event_name='article_opened'
UNION ALL
SELECT 'activated',count(DISTINCT user_id) FROM events WHERE event_name='article_read'
UNION ALL
SELECT 'experiment_eligible',count(*) FROM experiment_assignments;
