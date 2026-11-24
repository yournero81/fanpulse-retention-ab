WITH first_read AS (
 SELECT user_id,date(min(event_at)) AS cohort FROM events
 WHERE event_name='article_read' GROUP BY user_id
), days(day) AS (VALUES(1),(7),(14)), outcomes AS (
 SELECT f.user_id,d.day,EXISTS(
  SELECT 1 FROM events e WHERE e.user_id=f.user_id AND e.event_name='article_read'
  AND date(e.event_at)=date(f.cohort,'+'||d.day||' days')
 ) AS retained
 FROM first_read f CROSS JOIN days d CROSS JOIN dataset_metadata m
 WHERE date(f.cohort,'+'||d.day||' days')<=m.observation_end_date
)
SELECT day,count(*) AS eligible,sum(retained) AS retained,
 round(avg(retained),4) AS rate FROM outcomes GROUP BY day ORDER BY day;
