WITH users_no as (SELECT tenant_gid,
                         round(avg(mau),0)    AS mau_avg,
                         min(total_users)     AS total_users_min,
                         max(total_users)     AS total_users_max,
                         min(activated_users) AS activated_users_min,
                         max(activated_users) AS activated_users_max
                  FROM user_metrics
                  WHERE day >= '2026-01-01'
                    AND day < today()
                  GROUP BY tenant_gid),
     tenants_stats AS (SELECT tenants.tenant_gid,
                              tenants.subdomain,
                              tenants.name,
                              tenants.state,
                              tenants.active_subscription_plan_id,
                              if(active_subscription_plan_id in ('PLA-COR-2024','PLA-COR','PLA-PRE-2024','enterprise-2021','PLA-PRE','enterprise' ), 1, 0) as is_right_plan,
                              users_no.mau_avg,
                              users_no.total_users_min,
                              users_no.total_users_max,
                              users_no.activated_users_min,
                              users_no.activated_users_max
                       FROM tenants
                                LEFT JOIN users_no
                                          ON users_no.tenant_gid = tenants.tenant_gid
                       WHERE bkpr_tenant_selector('commercial_all', tenants.tenant_type) = 1),
forms_submitted AS (
    SELECT
        tenant_gid,
        actor_id,
        user_type,
        JSONExtractString(event_properties_raw, 'id') as form_id
    FROM beekeeper_events
    WHERE event_type = 'form-submitted'
    AND day >= '2026-01-01'
    AND day < today()
),
tenant_forms AS (
    SELECT tenant_gid,
           count(distinct actor_id) as users_submitting_forms,
           count(distinct form_id) as unique_forms_submitted,
           count(*) as forms_submissions_no
    FROM forms_submitted
    GROUP BY tenant_gid),
chats_dim as (
select tenant_gid,
       count(case when chat_type = 'GROUP' then 1 end) as group_chats,
       count(case when chat_type = 'SMART' then 1 end) as smart_chats,
       count(*) as all_group_chats
FROM beekeeper_dimensions_chats_current_final
WHERE created_at >= '2026-01-01'
AND created_at < today()
AND chat_type in ('GROUP', 'SMART')
GROUP BY tenant_gid),
    workflow_events AS (
      SELECT
          tenant_gid,
          JSONExtractString(event_properties_raw, 'workflow_id') AS workflow_id,
          count(*)                                               AS workflow_executions_no
      FROM beekeeper_events
      WHERE event_type = 'workflow-finished'
        AND day >= '2026-04-01'
        AND day < today()
      GROUP BY tenant_gid, workflow_id
  ),
tenant_workflows as (
  SELECT
      w.tenant_gid,
      countIf(JSONExtractString(JSONExtractArrayRaw(w.triggers)[1], 'id')   ILIKE '%form%')                               AS triggered_by_form_no,
      countIf(JSONExtractString(JSONExtractArrayRaw(w.triggers)[1], 'type') ILIKE '%SCHEDULE%')                           AS scheduled_workflows_no,
      count(*)                                                                                                             AS workflows_no,
      sum(we.workflow_executions_no)                                                                                       AS executions_no,
      sumIf(we.workflow_executions_no, JSONExtractString(JSONExtractArrayRaw(w.triggers)[1], 'id')   ILIKE '%form%')      AS form_triggered_executions_no,
      sumIf(we.workflow_executions_no, JSONExtractString(JSONExtractArrayRaw(w.triggers)[1], 'type') ILIKE '%SCHEDULE%')  AS scheduled_executions_no
  FROM beekeeper_dimensions_workflows_current_final w
  LEFT JOIN workflow_events we
         ON w.workflow_id = we.workflow_id
        AND w.tenant_gid  = we.tenant_gid
  WHERE w.created_at >= '2026-04-01'
    AND w.deleted_at IS NULL
  GROUP BY w.tenant_gid),
    tenant_shifts as (SELECT
      tenant_gid,
      count(DISTINCT user_id)                                          AS shifts_users_no,
      count(*) AS shifts_jobs_done
  FROM beekeeper_events
  WHERE event_type = 'user-calendar-retrieved'
    AND day >= '2026-04-01'
    AND day < today()
  AND JSONExtractInt(event_properties_raw, 'total_shifts') > 0
  GROUP BY tenant_gid)
SELECT
    tenants_stats.tenant_gid,
    subdomain,
    name,
    state,
    active_subscription_plan_id,
    is_right_plan,
    mau_avg,
    total_users_min,
    total_users_max,
    activated_users_min,
    activated_users_max,
    tenant_forms.unique_forms_submitted,
    tenant_forms.forms_submissions_no,
    tenant_forms.users_submitting_forms,
    chats_dim.group_chats,
    chats_dim.smart_chats,
    chats_dim.all_group_chats,
    tenant_workflows.workflows_no,
    tenant_workflows.scheduled_workflows_no,
    tenant_workflows.triggered_by_form_no,
    tenant_workflows.executions_no,
    tenant_workflows.scheduled_executions_no,
    tenant_workflows.form_triggered_executions_no,
    tenant_shifts.shifts_users_no,
    tenant_shifts.shifts_jobs_done
FROM tenants_stats
LEFT JOIN tenant_forms ON  tenants_stats.tenant_gid = tenant_forms.tenant_gid
LEFT JOIN chats_dim on tenants_stats.tenant_gid = chats_dim.tenant_gid
LEFT JOIN tenant_workflows on tenants_stats.tenant_gid = tenant_workflows.tenant_gid
LEFT JOIN tenant_shifts on tenants_stats.tenant_gid = tenant_shifts.tenant_gid;