WITH outcomes AS (
 SELECT a.*,date(a.assigned_at,'+7 days')<=m.observation_end_date AS mature,
 EXISTS(SELECT 1 FROM events e WHERE e.user_id=a.user_id AND event_name='article_read'
  AND date(e.event_at)=date(a.assigned_at,'+7 days')) AS retained,
 EXISTS(SELECT 1 FROM events e WHERE e.user_id=a.user_id AND event_name='article_read'
  AND date(e.event_at) BETWEEN date(a.assigned_at,'+1 day') AND date(a.assigned_at,'+7 days')) AS week_return,
 EXISTS(SELECT 1 FROM events e WHERE e.user_id=a.user_id AND event_name='communication_opted_out'
  AND e.event_at BETWEEN a.assigned_at AND datetime(a.assigned_at,'+7 days')) AS opted_out
 FROM experiment_assignments a CROSS JOIN dataset_metadata m
)
SELECT variant,count(*) AS assigned_total,sum(mature) AS n,
 sum(CASE WHEN mature THEN retained ELSE 0 END) AS retained,
 sum(CASE WHEN mature THEN opted_out ELSE 0 END) AS opted_out_n,
 round(1.0*sum(CASE WHEN mature THEN retained ELSE 0 END)/sum(mature),4) AS d7,
 round(1.0*sum(CASE WHEN mature THEN week_return ELSE 0 END)/sum(mature),4) AS week_return,
 round(1.0*sum(CASE WHEN mature THEN opted_out ELSE 0 END)/sum(mature),4) AS opt_out
FROM outcomes GROUP BY variant;
