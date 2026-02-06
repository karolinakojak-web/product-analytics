WITH users_no as (SELECT tenant_gid,
                         avg(mau)             AS mau_avg_180d,
                         min(total_users)     AS total_users_min,
                         max(total_users)     AS total_users_max,
                         min(activated_users) AS activated_users_min,
                         max(activated_users) AS activated_users_max
                  FROM user_metrics
                  WHERE day >= '2025-08-01'
                    AND day < today()
                  GROUP BY tenant_gid),
     tenants_stats AS (SELECT tenants.tenant_gid,
                              tenants.subdomain,
                              tenants.name,
                              tenants.state,
                              users_no.mau_avg_180d,
                              users_no.total_users_min,
                              users_no.total_users_max,
                              users_no.activated_users_min,
                              users_no.activated_users_max
                       FROM tenants
                                LEFT JOIN users_no
                                          ON users_no.tenant_gid = tenants.tenant_gid
                       WHERE bkpr_tenant_selector('commercial_all', tenants.tenant_type) = 1),
     user_days AS (SELECT day,
                          tenant_gid,
                          user_id,
                          min(event_timestamp) AS days_first_activity,
                          max(event_timestamp) AS days_last_activity
                   FROM production.beekeeper_events
                   WHERE day >= '2025-08-01'
                     AND day < today()
                     AND event_type NOT IN (
                                            'campaign-received', 'push-notification-received', 'push-notification-sent',
                                            'survey-received', 'unread-inbox-count-changed', 'comment-deleted',
                                            'post-deleted', 'post-reaction-deleted'
                       )
                     AND user_type = 'REGULAR'
                   GROUP BY day, tenant_gid, user_id),
     activity_gaps AS (SELECT tenant_gid,
                              user_id,
                              lagInFrame(days_last_activity) OVER (
                                  PARTITION BY user_id
                                  ORDER BY day
                                  ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
                                  )                                               prev_activity,
                              dateDiff('day', prev_activity, days_first_activity) diff
                       FROM user_days
                       QUALIFY diff > 29
                           AND diff < 10000),
     tenants_users AS (SELECT tenant_gid,
                              count(DISTINCT user_id) as inactive_users_no
                       FROM activity_gaps
                       GROUP BY tenant_gid)

SELECT ts.tenant_gid,
       ts.subdomain,
       ts.name AS customer_name,
       ts.state,
       ts.total_users_min,
       ts.total_users_max,
       ts.activated_users_min,
       ts.activated_users_max,
       ts.mau_avg_180d,
       tenants_users.inactive_users_no
from tenants_stats ts
         LEFT JOIN tenants_users on ts.tenant_gid = tenants_users.tenant_gid
;