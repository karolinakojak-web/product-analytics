-- Tippspiel World Cup 2026 (CH cell — 141 tenants)
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
  WHERE tenant_id IN (279, 363, 416, 447, 485, 551, 585, 602, 688, 749, 809, 831, 1107, 1268, 1601, 1881, 2075, 2442, 2651, 2821, 3050, 3244, 3474, 3613, 3785, 3822, 3873, 3946, 4017, 4111, 4180, 4252, 4371, 4418, 4485, 4715)
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
  WHERE tenant_id IN (290, 378, 421, 458, 491, 554, 590, 633, 734, 751, 821, 924, 1137, 1347, 1626, 1915, 2182, 2525, 2654, 2857, 3054, 3260, 3587, 3706, 3786, 3846, 3898, 3976, 4040, 4128, 4198, 4273, 4388, 4422, 4502)
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
  WHERE tenant_id IN (308, 397, 422, 475, 492, 580, 596, 637, 735, 770, 825, 965, 1178, 1459, 1843, 1937, 2256, 2576, 2683, 2986, 3123, 3266, 3595, 3744, 3799, 3866, 3920, 3989, 4049, 4136, 4205, 4322, 4400, 4442, 4535)
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
  WHERE tenant_id IN (362, 406, 441, 477, 505, 584, 597, 686, 743, 799, 827, 1016, 1266, 1488, 1878, 1999, 2437, 2614, 2800, 3005, 3143, 3407, 3609, 3781, 3821, 3870, 3937, 4016, 4096, 4149, 4212, 4344, 4415, 4484, 4670)
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
WHERE tenant_id IN (279, 290, 308, 362, 363, 378, 397, 406, 416, 421, 422, 441, 447, 458, 475, 477, 485, 491, 492, 505, 551, 554, 580, 584, 585, 590, 596, 597, 602, 633, 637, 686, 688, 734, 735, 743, 749, 751, 770, 799, 809, 821, 825, 827, 831, 924, 965, 1016, 1107, 1137, 1178, 1266, 1268, 1347, 1459, 1488, 1601, 1626, 1843, 1878, 1881, 1915, 1937, 1999, 2075, 2182, 2256, 2437, 2442, 2525, 2576, 2614, 2651, 2654, 2683, 2800, 2821, 2857, 2986, 3005, 3050, 3054, 3123, 3143, 3244, 3260, 3266, 3407, 3474, 3587, 3595, 3609, 3613, 3706, 3744, 3781, 3785, 3786, 3799, 3821, 3822, 3846, 3866, 3870, 3873, 3898, 3920, 3937, 3946, 3976, 3989, 4016, 4017, 4040, 4049, 4096, 4111, 4128, 4136, 4149, 4180, 4198, 4205, 4212, 4252, 4273, 4322, 4344, 4371, 4388, 4400, 4415, 4418, 4422, 4442, 4484, 4485, 4502, 4535, 4670, 4715)
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
  AND tenant_id IN (279, 290, 308, 362, 363, 378, 397, 406, 416, 421, 422, 441, 447, 458, 475, 477, 485, 491, 492, 505, 551, 554, 580, 584, 585, 590, 596, 597, 602, 633, 637, 686, 688, 734, 735, 743, 749, 751, 770, 799, 809, 821, 825, 827, 831, 924, 965, 1016, 1107, 1137, 1178, 1266, 1268, 1347, 1459, 1488, 1601, 1626, 1843, 1878, 1881, 1915, 1937, 1999, 2075, 2182, 2256, 2437, 2442, 2525, 2576, 2614, 2651, 2654, 2683, 2800, 2821, 2857, 2986, 3005, 3050, 3054, 3123, 3143, 3244, 3260, 3266, 3407, 3474, 3587, 3595, 3609, 3613, 3706, 3744, 3781, 3785, 3786, 3799, 3821, 3822, 3846, 3866, 3870, 3873, 3898, 3920, 3937, 3946, 3976, 3989, 4016, 4017, 4040, 4049, 4096, 4111, 4128, 4136, 4149, 4180, 4198, 4205, 4212, 4252, 4273, 4322, 4344, 4371, 4388, 4400, 4415, 4418, 4422, 4442, 4484, 4485, 4502, 4535, 4670, 4715)
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
WHERE tenantid IN (279, 363, 416, 447, 485, 551, 585, 602, 688, 749, 809, 831, 1107, 1268, 1601, 1881, 2075, 2442, 2651, 2821, 3050, 3244, 3474, 3613, 3785, 3822, 3873, 3946, 4017, 4111, 4180, 4252, 4371, 4418, 4485, 4715)

-- EXPORT 5B — batch 2 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (290, 378, 421, 458, 491, 554, 590, 633, 734, 751, 821, 924, 1137, 1347, 1626, 1915, 2182, 2525, 2654, 2857, 3054, 3260, 3587, 3706, 3786, 3846, 3898, 3976, 4040, 4128, 4198, 4273, 4388, 4422, 4502)

-- EXPORT 5C — batch 3 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (308, 397, 422, 475, 492, 580, 596, 637, 735, 770, 825, 965, 1178, 1459, 1843, 1937, 2256, 2576, 2683, 2986, 3123, 3266, 3595, 3744, 3799, 3866, 3920, 3989, 4049, 4136, 4205, 4322, 4400, 4442, 4535)

-- EXPORT 5D — batch 4 of 4
SELECT
  id                                  AS user_id,
  tenantid                            AS tenant_id,
  toString(created_at)                AS created_at,
  toString(first_login)               AS first_login,
  is_bot
FROM `remote.monolith.mysql`.`user`
WHERE tenantid IN (362, 406, 441, 477, 505, 584, 597, 686, 743, 799, 827, 1016, 1266, 1488, 1878, 1999, 2437, 2614, 2800, 3005, 3143, 3407, 3609, 3781, 3821, 3870, 3937, 4016, 4096, 4149, 4212, 4344, 4415, 4484, 4670)