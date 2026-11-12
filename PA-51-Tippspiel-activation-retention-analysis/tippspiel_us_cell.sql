-- Tippspiel World Cup 2026 (US cell — 43 tenants)
-- Run each query as its own Metabase question on the ClickHouse "analytics" database,
-- then download the FULL result as CSV (download button — the preview stops at 2,000 rows).
--
--   1      World Cup 2026 participants                     remote Tippspiel only
--   2      World Cup 2026 bets per user                     remote Tippspiel only
--   3A–3D  dormant users who came back, 4 tenant batches   local tracking only (14 Feb – 12 Oct)
--   4a     users active in the 3-month lookback per tenant local tracking only (14 Feb – 14 May)
--   4b     total users per tenant on 14 May                local state-history only
--   5A–5D  account created / first login per user         remote monolith MySQL (id + dates only)
--
-- For another cell: run export 1 first and send it over — the tenant lists in 3 and 4 get regenerated.


-- ============================================================
-- EXPORT 1 — World Cup 2026 participants
-- ============================================================
SELECT tenant_id, user_id, score
FROM `remote.tippspiel.participants`
WHERE event_id = 'world-2026'


-- ============================================================
-- EXPORT 2 — World Cup 2026 bets per user
-- (no join: world-2026 is the only Tippspiel event in 2026, so every bet
--  created this year belongs to it; the date filter is pushed down to Postgres)
-- ============================================================
SELECT
  user_id,
  count()        AS n_bets,
  min(created)   AS first_bet,
  max(created)   AS last_bet
FROM `remote.tippspiel.bets`
WHERE created >= '2026-01-01'
GROUP BY user_id

-- ============================================================
-- EXPORT 3A — dormant users (no activity 14 Feb – 14 May) who came back 15 May – 19 Jul
-- batch 1 of 4
-- ============================================================
SELECT
  tenant_id,
  replaceRegexpOne(actor_id, '^beekeeper:users:user:(.*):$', '\\1')   AS user_id,
  minIf(d, d >= toDate('2026-05-15'))                                 AS first_return,
  max(d)                                                              AS last_active,
  countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19'))    AS active_days_window,
  countIf(d BETWEEN toDate('2026-07-20') AND toDate('2026-08-18'))    AS active_days_m1,
  countIf(d BETWEEN toDate('2026-08-19') AND toDate('2026-09-17'))    AS active_days_m2,
  countIf(d BETWEEN toDate('2026-09-18') AND toDate('2026-10-12'))    AS active_days_m3,
  countIf(d > toDate('2026-07-19'))                                   AS active_days_after_wc
FROM (
  SELECT tenant_id, actor_id, toDate(event_timestamp) AS d
  FROM `analytics.beekeeper.events.tracking`
  WHERE tenant_id IN (253, 1419, 1625, 3095, 7406, 7800, 11621, 12699, 13194, 14816, 15153)
    AND event_timestamp >= '2026-02-14' AND event_timestamp < '2026-10-13'
    AND user_type = 'REGULAR'
    AND actor_id NOT IN ('', 'beekeeper:users:user::')
    AND event_type NOT IN ('campaign-received', 'push-notification-received', 'push-notification-sent',
                           'survey-received', 'unread-inbox-count-changed',
                           'comment-deleted', 'post-deleted', 'post-reaction-deleted')
  GROUP BY tenant_id, actor_id, d
)
GROUP BY tenant_id, actor_id
HAVING countIf(d < toDate('2026-05-15')) = 0
   AND countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19')) > 0

-- ============================================================
-- EXPORT 3B — dormant users (no activity 14 Feb – 14 May) who came back 15 May – 19 Jul
-- batch 2 of 4
-- ============================================================
SELECT
  tenant_id,
  replaceRegexpOne(actor_id, '^beekeeper:users:user:(.*):$', '\\1')   AS user_id,
  minIf(d, d >= toDate('2026-05-15'))                                 AS first_return,
  max(d)                                                              AS last_active,
  countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19'))    AS active_days_window,
  countIf(d BETWEEN toDate('2026-07-20') AND toDate('2026-08-18'))    AS active_days_m1,
  countIf(d BETWEEN toDate('2026-08-19') AND toDate('2026-09-17'))    AS active_days_m2,
  countIf(d BETWEEN toDate('2026-09-18') AND toDate('2026-10-12'))    AS active_days_m3,
  countIf(d > toDate('2026-07-19'))                                   AS active_days_after_wc
FROM (
  SELECT tenant_id, actor_id, toDate(event_timestamp) AS d
  FROM `analytics.beekeeper.events.tracking`
  WHERE tenant_id IN (786, 1458, 1932, 3941, 7413, 9145, 11736, 12743, 13722, 15030, 15484)
    AND event_timestamp >= '2026-02-14' AND event_timestamp < '2026-10-13'
    AND user_type = 'REGULAR'
    AND actor_id NOT IN ('', 'beekeeper:users:user::')
    AND event_type NOT IN ('campaign-received', 'push-notification-received', 'push-notification-sent',
                           'survey-received', 'unread-inbox-count-changed',
                           'comment-deleted', 'post-deleted', 'post-reaction-deleted')
  GROUP BY tenant_id, actor_id, d
)
GROUP BY tenant_id, actor_id
HAVING countIf(d < toDate('2026-05-15')) = 0
   AND countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19')) > 0

-- ============================================================
-- EXPORT 3C — dormant users (no activity 14 Feb – 14 May) who came back 15 May – 19 Jul
-- batch 3 of 4
-- ============================================================
SELECT
  tenant_id,
  replaceRegexpOne(actor_id, '^beekeeper:users:user:(.*):$', '\\1')   AS user_id,
  minIf(d, d >= toDate('2026-05-15'))                                 AS first_return,
  max(d)                                                              AS last_active,
  countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19'))    AS active_days_window,
  countIf(d BETWEEN toDate('2026-07-20') AND toDate('2026-08-18'))    AS active_days_m1,
  countIf(d BETWEEN toDate('2026-08-19') AND toDate('2026-09-17'))    AS active_days_m2,
  countIf(d BETWEEN toDate('2026-09-18') AND toDate('2026-10-12'))    AS active_days_m3,
  countIf(d > toDate('2026-07-19'))                                   AS active_days_after_wc
FROM (
  SELECT tenant_id, actor_id, toDate(event_timestamp) AS d
  FROM `analytics.beekeeper.events.tracking`
  WHERE tenant_id IN (1279, 1460, 2242, 4483, 7543, 9257, 12132, 13058, 13741, 15044, 15552)
    AND event_timestamp >= '2026-02-14' AND event_timestamp < '2026-10-13'
    AND user_type = 'REGULAR'
    AND actor_id NOT IN ('', 'beekeeper:users:user::')
    AND event_type NOT IN ('campaign-received', 'push-notification-received', 'push-notification-sent',
                           'survey-received', 'unread-inbox-count-changed',
                           'comment-deleted', 'post-deleted', 'post-reaction-deleted')
  GROUP BY tenant_id, actor_id, d
)
GROUP BY tenant_id, actor_id
HAVING countIf(d < toDate('2026-05-15')) = 0
   AND countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19')) > 0

-- ============================================================
-- EXPORT 3D — dormant users (no activity 14 Feb – 14 May) who came back 15 May – 19 Jul
-- batch 4 of 4
-- ============================================================
SELECT
  tenant_id,
  replaceRegexpOne(actor_id, '^beekeeper:users:user:(.*):$', '\\1')   AS user_id,
  minIf(d, d >= toDate('2026-05-15'))                                 AS first_return,
  max(d)                                                              AS last_active,
  countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19'))    AS active_days_window,
  countIf(d BETWEEN toDate('2026-07-20') AND toDate('2026-08-18'))    AS active_days_m1,
  countIf(d BETWEEN toDate('2026-08-19') AND toDate('2026-09-17'))    AS active_days_m2,
  countIf(d BETWEEN toDate('2026-09-18') AND toDate('2026-10-12'))    AS active_days_m3,
  countIf(d > toDate('2026-07-19'))                                   AS active_days_after_wc
FROM (
  SELECT tenant_id, actor_id, toDate(event_timestamp) AS d
  FROM `analytics.beekeeper.events.tracking`
  WHERE tenant_id IN (1394, 1609, 2620, 6849, 7653, 10557, 12379, 13099, 13927, 15116)
    AND event_timestamp >= '2026-02-14' AND event_timestamp < '2026-10-13'
    AND user_type = 'REGULAR'
    AND actor_id NOT IN ('', 'beekeeper:users:user::')
    AND event_type NOT IN ('campaign-received', 'push-notification-received', 'push-notification-sent',
                           'survey-received', 'unread-inbox-count-changed',
                           'comment-deleted', 'post-deleted', 'post-reaction-deleted')
  GROUP BY tenant_id, actor_id, d
)
GROUP BY tenant_id, actor_id
HAVING countIf(d < toDate('2026-05-15')) = 0
   AND countIf(d BETWEEN toDate('2026-05-15') AND toDate('2026-07-19')) > 0

-- ============================================================
-- EXPORT 4a — users active in the 3-month lookback, per tenant (all tenants in the cell; scans 3 months only)
-- ============================================================
SELECT tenant_id, uniqExact(actor_id) AS active_users_14feb_14may
FROM `analytics.beekeeper.events.tracking`
WHERE tenant_id IN (253, 786, 1279, 1394, 1419, 1458, 1460, 1609, 1625, 1932, 2242, 2620, 3095, 3941, 4483, 6849, 7406, 7413, 7543, 7653, 7800, 9145, 9257, 10557, 11621, 11736, 12132, 12379, 12699, 12743, 13058, 13099, 13194, 13722, 13741, 13927, 14816, 15030, 15044, 15116, 15153, 15484, 15552)
  AND event_timestamp >= '2026-02-14' AND event_timestamp < '2026-05-15'
    AND user_type = 'REGULAR'
    AND actor_id NOT IN ('', 'beekeeper:users:user::')
    AND event_type NOT IN ('campaign-received', 'push-notification-received', 'push-notification-sent',
                           'survey-received', 'unread-inbox-count-changed',
                           'comment-deleted', 'post-deleted', 'post-reaction-deleted')
GROUP BY tenant_id


-- ============================================================
-- EXPORT 4b — total users per tenant on 14 May 2026 (same source as the Tippspiel dashboard)
-- ============================================================
SELECT tenant_id, user_state, sum(user_count) AS users
FROM `monolith.beekeeper.state-history.users`
WHERE at_date = toDate('2026-05-14')
  AND segment_type = 'tenants'
  AND tenant_id IN (253, 786, 1279, 1394, 1419, 1458, 1460, 1609, 1625, 1932, 2242, 2620, 3095, 3941, 4483, 6849, 7406, 7413, 7543, 7653, 7800, 9145, 9257, 10557, 11621, 11736, 12132, 12379, 12699, 12743, 13058, 13099, 13194, 13722, 13741, 13927, 14816, 15030, 15044, 15116, 15153, 15484, 15552)
GROUP BY tenant_id, user_state


-- ============================================================
-- EXPORT 5A–5D — account creation and first login per user (remote monolith MySQL)
--
-- Why this step is needed:
-- Export 3 defines "dormant" as no activity between 14 Feb and 14 May. That is true
-- for two very different kinds of people:
--   1. Real dormant users: they had an account before Tippspiel and weren't using it.
--      These are the people Taze and Omar are asking about.
--   2. New employees: their account didn't exist yet, so of course they had no activity.
--      They joined after 15 May and started using the app because they were onboarded,
--      not because anything reactivated them.
-- The activity data alone can't tell these two apart. This step adds the account
-- creation date (created_at) and first login (first_login), which can.
--
-- Selects ONLY id, tenant, dates and bot flag — no personal data.
-- Same 4 tenant batches as 3A–3D. Dates as strings to avoid conversion errors.
-- ============================================================

-- EXPORT 5A — batch 1 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (253, 1419, 1625, 3095, 7406, 7800, 11621, 12699, 13194, 14816, 15153)

-- EXPORT 5B — batch 2 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (786, 1458, 1932, 3941, 7413, 9145, 11736, 12743, 13722, 15030, 15484)

-- EXPORT 5C — batch 3 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (1279, 1460, 2242, 4483, 7543, 9257, 12132, 13058, 13741, 15044, 15552)

-- EXPORT 5D — batch 4 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (1394, 1609, 2620, 6849, 7653, 10557, 12379, 13099, 13927, 15116)