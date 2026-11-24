WITH ranked AS (
 SELECT user_id,event_at,row_number() OVER(PARTITION BY user_id ORDER BY event_at,event_id) AS rn
 FROM events WHERE event_name='article_read'
), cohorts AS (
 SELECT user_id,date(event_at) AS first_date,substr(event_at,1,7) AS cohort FROM ranked WHERE rn=1
), days(day) AS (VALUES(1),(7),(14)), outcomes AS (
 SELECT c.*,d.day,EXISTS(SELECT 1 FROM events e WHERE e.user_id=c.user_id
 AND e.event_name='article_read' AND date(e.event_at)=date(c.first_date,'+'||d.day||' days')) AS retained
 FROM cohorts c CROSS JOIN days d CROSS JOIN dataset_metadata m
 WHERE date(c.first_date,'+'||d.day||' days')<=m.observation_end_date
)
SELECT cohort,day,count(*) AS eligible,sum(retained) AS retained,round(avg(retained),4) AS rate
FROM outcomes GROUP BY cohort,day ORDER BY cohort,day;
