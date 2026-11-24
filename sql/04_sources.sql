WITH activated AS (
 SELECT DISTINCT user_id FROM events WHERE event_name='article_read'
), stats AS (
 SELECT u.source_id,count(*) AS registered,count(a.user_id) AS activated
 FROM users u LEFT JOIN activated a USING(user_id) GROUP BY u.source_id
), costs AS (
 SELECT source_id,sum(amount) AS cost FROM acquisition_costs GROUP BY source_id
)
SELECT s.source_name, t.registered,t.activated,
 round(1.0*t.activated/t.registered,4) AS activation_rate,c.cost,
 round(c.cost/nullif(t.activated,0),2) AS cost_per_activation
FROM stats t JOIN acquisition_sources s USING(source_id) JOIN costs c USING(source_id)
ORDER BY cost_per_activation;
